"""Report assembly and rendering (human text and JSON), plus exit-code policy.

Part of codex-watchdog, a product of Divergent Health, Inc. MIT License.
"""

from __future__ import annotations

import datetime
import json

EXIT_QUIET = 0
EXIT_NOTABLE = 1
EXIT_ALERT = 2


def build(repo, base_ref, base_sha, worktrees, session_info, findings, changes, stalled_seconds, stall_threshold_seconds):
    violations = [f for f in findings if f.severity == "violation"]
    watches = [f for f in findings if f.severity == "watch"]
    stalled = (
        stalled_seconds > stall_threshold_seconds
        and any(wt.dirty_files or wt.untracked_files for wt in worktrees)
    )
    return {
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "repo": str(repo),
        "base": {"ref": base_ref, "sha": base_sha},
        "session": session_info,
        "worktrees": [
            {
                "branch": wt.branch,
                "path": wt.path,
                "head": wt.head,
                "base_ok": wt.base_ok,
                "dirty_files": wt.dirty_files,
                "untracked_files": wt.untracked_files,
                "commits_ahead": wt.commits_ahead,
                "changed_files": wt.changed_files,
            }
            for wt in worktrees
        ],
        "violations": [vars(f) for f in violations],
        "watch_findings": [vars(f) for f in watches],
        "changes_since_last_run": changes,
        "stalled": stalled,
        "seconds_since_activity": int(stalled_seconds),
    }


def exit_code(report):
    if report["violations"] or report["stalled"]:
        return EXIT_ALERT
    if report["changes_since_last_run"] or report["watch_findings"]:
        return EXIT_NOTABLE
    return EXIT_QUIET


def render_json(report):
    return json.dumps(report, indent=2, sort_keys=True)


def render_human(report, full=False):
    lines = []
    quiet = exit_code(report) == EXIT_QUIET
    lines.append(
        f"codex-watchdog @ {report['generated_at']}  repo={report['repo']}  "
        f"base={report['base']['ref']}@{report['base']['sha'][:9] or '?'}"
    )

    for violation in report["violations"]:
        lines.append(
            f"  VIOLATION [{violation['kind']}] {violation['worktree']}: {violation['detail']}"
        )
    if report["stalled"]:
        lines.append(
            f"  STALL: uncommitted work with no activity for "
            f"{report['seconds_since_activity'] // 60} minutes"
        )
    for watch in report["watch_findings"]:
        lines.append(
            f"  watch [{watch['kind']}] {watch['worktree']}: {watch['detail']}"
        )

    changes = report["changes_since_last_run"]
    for branch in changes.get("new_worktrees", []):
        lines.append(f"  new worktree: {branch}")
    for branch, events in changes.get("worktree_activity", {}).items():
        lines.append(f"  activity in {branch}: " + ", ".join(events))
    for branch in changes.get("removed_worktrees", []):
        lines.append(f"  worktree removed: {branch}")
    if changes.get("session_activity"):
        lines.append("  codex session log active")

    if quiet and not full:
        lines.append("  quiet: no changes since last run")

    if full or not quiet:
        for wt in report["worktrees"]:
            base_state = {True: "base OK", False: "STALE BASE", None: "base unknown"}[wt["base_ok"]]
            lines.append(
                f"  {wt['branch']} @ {wt['head'][:9]} ({base_state}) -- "
                f"{len(wt['commits_ahead'])} commit(s) ahead, "
                f"{len(wt['dirty_files'])} dirty, {len(wt['untracked_files'])} new file(s)"
            )
            for name in (wt["dirty_files"] + wt["untracked_files"])[:12]:
                lines.append(f"      {name}")

    threads = report["session"].get("threads", [])
    if threads:
        newest = threads[0]
        lines.append(
            f"  codex threads: " + ", ".join(t["thread_name"] for t in threads[:3])
            + f" (newest updated {newest.get('updated_at', '?')})"
        )
    if not report["session"].get("processes"):
        lines.append("  note: no codex process detected")

    return "\n".join(lines)
