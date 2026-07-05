# Copyright (c) 2026 Divergent Health, Inc. MIT License.
"""State fingerprinting, delta detection, and stall-clock tests."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codex_watchdog import state as state_mod  # noqa: E402
from codex_watchdog.worktrees import WorktreeStatus  # noqa: E402


def make_worktree(branch="codex/test", head="a" * 40, dirty=None, untracked=None):
    return WorktreeStatus(
        path="/tmp/wt",
        branch=branch,
        head=head,
        base_ref="origin/main",
        base_sha="b" * 40,
        base_ok=True,
        dirty_files=dirty or [],
        untracked_files=untracked or [],
    )


SESSION = {"newest_rollout": {"mtime": 100.0, "size": 5}}


class StateTest(unittest.TestCase):
    def test_identical_fingerprints_are_quiet(self):
        fp1 = state_mod.fingerprint([make_worktree()], SESSION)
        fp2 = state_mod.fingerprint([make_worktree()], SESSION)
        self.assertEqual(state_mod.diff(fp1, fp2), {})

    def test_new_worktree_detected(self):
        before = state_mod.fingerprint([], SESSION)
        after = state_mod.fingerprint([make_worktree()], SESSION)
        self.assertEqual(state_mod.diff(before, after)["new_worktrees"], ["codex/test"])

    def test_new_commit_detected(self):
        before = state_mod.fingerprint([make_worktree(head="a" * 40)], SESSION)
        after = state_mod.fingerprint([make_worktree(head="c" * 40)], SESSION)
        changes = state_mod.diff(before, after)
        self.assertIn("new commits", changes["worktree_activity"]["codex/test"])

    def test_dirty_file_change_detected(self):
        before = state_mod.fingerprint([make_worktree()], SESSION)
        after = state_mod.fingerprint([make_worktree(untracked=["new.md"])], SESSION)
        changes = state_mod.diff(before, after)
        self.assertIn(
            "working-tree files changed", changes["worktree_activity"]["codex/test"]
        )

    def test_session_activity_detected(self):
        before = state_mod.fingerprint([], SESSION)
        after = state_mod.fingerprint(
            [], {"newest_rollout": {"mtime": 200.0, "size": 9}}
        )
        self.assertTrue(state_mod.diff(before, after)["session_activity"])

    def test_stall_clock_resets_on_activity(self):
        state = {}
        idle = state_mod.update_stall_clock(state, changes={"x": 1}, now=1000.0)
        self.assertEqual(idle, 0.0)
        idle = state_mod.update_stall_clock(state, changes={}, now=1600.0)
        self.assertEqual(idle, 600.0)
        idle = state_mod.update_stall_clock(state, changes={"y": 1}, now=1700.0)
        self.assertEqual(idle, 0.0)

    def test_state_roundtrip(self):
        with_tmp = Path(self.enterContext(_tempdir())) / "state.json"
        state_mod.save(with_tmp, {"fingerprint": {"worktrees": {}}, "last_activity_ts": 5})
        self.assertEqual(state_mod.load(with_tmp)["last_activity_ts"], 5)

    def test_load_missing_file_returns_empty(self):
        self.assertEqual(state_mod.load("/nonexistent/state.json"), {})


def _tempdir():
    import tempfile

    return tempfile.TemporaryDirectory()


if __name__ == "__main__":
    unittest.main()
