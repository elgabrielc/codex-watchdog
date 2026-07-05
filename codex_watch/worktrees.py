"""Git worktree observation: enumeration, base ancestry, dirt, and diffs.

Part of codex-watch, a product of Divergent Health, Inc. MIT License.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

GIT_TIMEOUT_SECONDS = 60
MAX_COMMITS_REPORTED = 20
# New (untracked) files are scanned for banned patterns; bound the read so a
# stray binary or huge artifact cannot balloon a tick.
MAX_UNTRACKED_SCAN_BYTES = 512 * 1024


def run_git(args, cwd):
    """Run git, returning (exit_code, stdout, stderr). Never raises for git failures."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, "", str(error)
    return proc.returncode, proc.stdout, proc.stderr


@dataclass
class WorktreeStatus:
    path: str
    branch: str
    head: str
    base_ref: str
    base_sha: str
    # None means the base ref could not be resolved (e.g. no remote in a fixture repo)
    base_ok: bool | None
    dirty_files: list = field(default_factory=list)
    untracked_files: list = field(default_factory=list)
    commits_ahead: list = field(default_factory=list)
    changed_files: list = field(default_factory=list)
    diff_text: str = ""
    untracked_texts: dict = field(default_factory=dict)


def parse_worktree_list(porcelain_output):
    """Parse `git worktree list --porcelain` into a list of entry dicts."""
    entries = []
    current = {}
    for line in porcelain_output.splitlines():
        if not line.strip():
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        entries.append(current)
    return entries


def _branch_name(entry):
    ref = entry.get("branch", "")
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]
    return "(detached)" if "detached" in entry else ref


def _dirty_paths(porcelain_status):
    """Extract paths from `git status --porcelain`, splitting tracked vs untracked."""
    tracked, untracked = [], []
    for line in porcelain_status.splitlines():
        if len(line) < 4:
            continue
        status, path = line[:2], line[3:]
        # Renames report "old -> new"; the new path is the one the agent touched
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if status == "??":
            untracked.append(path)
        else:
            tracked.append(path)
    return tracked, untracked


def inspect(repo, base_ref="origin/main", agent_prefixes=("codex/", "cc/"), fetch=True):
    """Observe all agent worktrees of `repo`. Returns (base_sha, [WorktreeStatus])."""
    repo = Path(repo)

    if fetch and "/" in base_ref:
        remote, _, branch = base_ref.partition("/")
        run_git(["fetch", remote, branch, "--quiet"], repo)

    code, out, _ = run_git(["rev-parse", "--verify", base_ref + "^{commit}"], repo)
    base_sha = out.strip() if code == 0 else ""

    code, out, _ = run_git(["worktree", "list", "--porcelain"], repo)
    if code != 0:
        return base_sha, []

    results = []
    for entry in parse_worktree_list(out):
        branch = _branch_name(entry)
        if not any(branch.startswith(prefix) for prefix in agent_prefixes):
            continue
        path = entry.get("worktree", "")
        head = entry.get("HEAD", "")

        base_ok = None
        if base_sha and head:
            ancestor_code, _, _ = run_git(
                ["merge-base", "--is-ancestor", base_sha, head], repo
            )
            base_ok = ancestor_code == 0

        _, status_out, _ = run_git(["status", "--porcelain"], path)
        dirty, untracked = _dirty_paths(status_out)

        commits_ahead = []
        changed_files = []
        diff_text = ""
        if base_sha and head:
            _, log_out, _ = run_git(
                ["log", "--oneline", f"{base_sha}..{head}"], repo
            )
            commits_ahead = log_out.splitlines()[:MAX_COMMITS_REPORTED]
            _, names_out, _ = run_git(
                ["diff", "--name-only", f"{base_sha}...{head}"], repo
            )
            changed_files = [n for n in names_out.splitlines() if n]
            _, committed_diff, _ = run_git(["diff", f"{base_sha}...{head}"], repo)
            diff_text = committed_diff

        # Uncommitted (staged + unstaged) edits live only in the worktree itself
        _, local_diff, _ = run_git(["diff", "HEAD"], path)
        diff_text += "\n" + local_diff

        untracked_texts = {}
        for name in untracked:
            file_path = Path(path) / name
            try:
                if file_path.is_file() and file_path.stat().st_size <= MAX_UNTRACKED_SCAN_BYTES:
                    untracked_texts[name] = file_path.read_text(errors="replace")
            except OSError:
                continue

        results.append(
            WorktreeStatus(
                path=path,
                branch=branch,
                head=head,
                base_ref=base_ref,
                base_sha=base_sha,
                base_ok=base_ok,
                dirty_files=dirty,
                untracked_files=untracked,
                commits_ahead=commits_ahead,
                changed_files=changed_files,
                diff_text=diff_text,
                untracked_texts=untracked_texts,
            )
        )
    return base_sha, results
