"""Report-by-exception state: remember the last observation, emit only deltas.

Part of codex-watch, a product of Divergent Health, Inc. MIT License.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path


def default_state_path(repo):
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    repo = Path(repo).resolve()
    slug = repo.name + "-" + hashlib.sha1(str(repo).encode()).hexdigest()[:8]
    return cache_root / "codex-watch" / (slug + ".json")


def load(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def save(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def fingerprint(worktrees, session_info):
    """Reduce an observation to the comparable facts that define 'activity'."""
    return {
        "worktrees": {
            wt.branch: {
                "head": wt.head,
                "dirty": sorted(wt.dirty_files),
                "untracked": sorted(wt.untracked_files),
                "changed": sorted(wt.changed_files),
            }
            for wt in worktrees
        },
        "session": {
            "newest_rollout_mtime": session_info.get("newest_rollout", {}).get("mtime", 0),
            "newest_rollout_size": session_info.get("newest_rollout", {}).get("size", 0),
        },
    }


def diff(previous_fingerprint, current_fingerprint):
    """Describe what changed between two fingerprints. Empty dict = quiet tick."""
    changes = {}
    prev_wts = previous_fingerprint.get("worktrees", {})
    curr_wts = current_fingerprint.get("worktrees", {})

    for branch, curr in curr_wts.items():
        prev = prev_wts.get(branch)
        if prev is None:
            changes.setdefault("new_worktrees", []).append(branch)
            continue
        branch_changes = []
        if prev["head"] != curr["head"]:
            branch_changes.append("new commits")
        if prev["dirty"] != curr["dirty"] or prev["untracked"] != curr["untracked"]:
            branch_changes.append("working-tree files changed")
        if prev["changed"] != curr["changed"]:
            branch_changes.append("changed-file set vs base moved")
        if branch_changes:
            changes.setdefault("worktree_activity", {})[branch] = branch_changes

    for branch in prev_wts:
        if branch not in curr_wts:
            changes.setdefault("removed_worktrees", []).append(branch)

    if previous_fingerprint.get("session") != current_fingerprint.get("session"):
        changes["session_activity"] = True

    return changes


def update_stall_clock(state, changes, now=None):
    """Track the last-activity timestamp across runs; returns seconds since activity."""
    now = now if now is not None else time.time()
    if changes or "last_activity_ts" not in state:
        state["last_activity_ts"] = now
    return now - state["last_activity_ts"]
