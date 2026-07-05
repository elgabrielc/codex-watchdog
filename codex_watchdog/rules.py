"""Rule loading and evaluation against observed worktree state.

Part of codex-watchdog, a product of Divergent Health, Inc. MIT License.
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_RULES = {
    "agent_branch_prefixes": ["codex/", "cc/"],
    "forbidden_paths": [],
    "banned_patterns": [],
    "protected_lines": [],
    "watch_paths": [],
}

SEVERITY_VIOLATION = "violation"
SEVERITY_WATCH = "watch"


@dataclass
class Finding:
    severity: str
    kind: str
    worktree: str
    detail: str


def load_rules(path=None):
    """Load rules JSON merged over defaults. Missing file -> defaults only."""
    rules = dict(DEFAULT_RULES)
    if path:
        loaded = json.loads(Path(path).read_text())
        for key in DEFAULT_RULES:
            if key in loaded:
                rules[key] = loaded[key]
    return rules


def _glob_match(path, patterns):
    for pattern in patterns:
        # fnmatch's `*` already crosses `/` (it is not filesystem-aware), so a
        # `**` spelled for readability collapses to the same behavior.
        normalized = pattern.replace("**/", "*").replace("**", "*")
        if fnmatch.fnmatch(path, normalized):
            return pattern
    return None


def _split_diff_by_file(diff_text):
    """Map changed-file path -> its section of a unified diff."""
    sections = {}
    current_path = None
    current_lines = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            if current_path:
                sections[current_path] = "\n".join(current_lines)
            # `diff --git a/x b/x` -- take the b/ side, the post-change path
            parts = line.split(" b/", 1)
            current_path = parts[1] if len(parts) == 2 else line
            current_lines = []
        elif current_path:
            current_lines.append(line)
    if current_path:
        sections[current_path] = "\n".join(current_lines)
    return sections


def _added_lines(diff_section):
    return [
        line[1:]
        for line in diff_section.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def _touched_lines(diff_section):
    return [
        line[1:]
        for line in diff_section.splitlines()
        if (line.startswith("+") and not line.startswith("+++"))
        or (line.startswith("-") and not line.startswith("---"))
    ]


def evaluate(rules, worktree):
    """Evaluate one WorktreeStatus against rules. Returns a list of Findings."""
    findings = []
    all_paths = sorted(
        set(worktree.changed_files)
        | set(worktree.dirty_files)
        | set(worktree.untracked_files)
    )

    if worktree.base_ok is False:
        findings.append(
            Finding(
                SEVERITY_VIOLATION,
                "stale-base",
                worktree.branch,
                f"{worktree.base_ref} ({worktree.base_sha[:9]}) is NOT an ancestor of "
                f"HEAD ({worktree.head[:9]}) -- agent is working from a stale base",
            )
        )

    for path in all_paths:
        pattern = _glob_match(path, rules["forbidden_paths"])
        if pattern:
            findings.append(
                Finding(
                    SEVERITY_VIOLATION,
                    "forbidden-path",
                    worktree.branch,
                    f"{path} (matches forbidden pattern '{pattern}')",
                )
            )
            continue
        pattern = _glob_match(path, rules["watch_paths"])
        if pattern:
            findings.append(
                Finding(
                    SEVERITY_WATCH,
                    "watch-path",
                    worktree.branch,
                    f"{path} (matches watch pattern '{pattern}')",
                )
            )

    sections = _split_diff_by_file(worktree.diff_text)

    for banned in rules["banned_patterns"]:
        regex = re.compile(banned)
        for path, section in sections.items():
            for line in _added_lines(section):
                if regex.search(line):
                    findings.append(
                        Finding(
                            SEVERITY_VIOLATION,
                            "banned-pattern",
                            worktree.branch,
                            f"'{banned}' added in {path}: {line.strip()[:120]}",
                        )
                    )
                    break
        for path, content in worktree.untracked_texts.items():
            if regex.search(content):
                findings.append(
                    Finding(
                        SEVERITY_VIOLATION,
                        "banned-pattern",
                        worktree.branch,
                        f"'{banned}' present in new file {path}",
                    )
                )

    for protected in rules["protected_lines"]:
        target, pattern = protected.get("path", ""), protected.get("pattern", "")
        if not target or not pattern:
            continue
        section = sections.get(target)
        if not section:
            continue
        regex = re.compile(pattern)
        for line in _touched_lines(section):
            if regex.search(line):
                findings.append(
                    Finding(
                        SEVERITY_VIOLATION,
                        "protected-line",
                        worktree.branch,
                        f"protected line matching '{pattern}' changed in {target}: "
                        f"{line.strip()[:120]}",
                    )
                )
                break

    return findings
