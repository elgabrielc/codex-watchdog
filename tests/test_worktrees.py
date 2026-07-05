# Copyright (c) 2026 Divergent Health, Inc. MIT License.
"""Worktree inspection tests against real fixture git repositories in tempdirs."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codex_watch import worktrees as wt_mod  # noqa: E402


def git(args, cwd):
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
    )


class WorktreeFixture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(["init", "-b", "main"], self.repo)
        git(["config", "user.name", "Fixture"], self.repo)
        git(["config", "user.email", "fixture@example.com"], self.repo)
        (self.repo / "README.md").write_text("fixture\n")
        git(["add", "."], self.repo)
        git(["commit", "-m", "initial"], self.repo)

    def add_commit(self, repo, name, content="x\n"):
        (Path(repo) / name).write_text(content)
        git(["add", name], repo)
        git(["commit", "-m", f"add {name}"], repo)

    def test_agent_worktree_on_current_base_is_ok(self):
        wt_path = self.root / "wt-good"
        git(["worktree", "add", "-b", "codex/good", str(wt_path), "main"], self.repo)
        self.add_commit(wt_path, "feature.txt")

        base_sha, observed = wt_mod.inspect(self.repo, base_ref="main", fetch=False)
        self.assertEqual(len(observed), 1)
        wt = observed[0]
        self.assertEqual(wt.branch, "codex/good")
        self.assertTrue(wt.base_ok)
        self.assertEqual(len(wt.commits_ahead), 1)
        self.assertEqual(wt.changed_files, ["feature.txt"])

    def test_stale_base_detected_when_main_advances(self):
        wt_path = self.root / "wt-stale"
        git(["worktree", "add", "-b", "codex/stale", str(wt_path), "main"], self.repo)
        # main moves on AFTER the worktree branched: its HEAD no longer contains base
        self.add_commit(self.repo, "mainline.txt")

        _, observed = wt_mod.inspect(self.repo, base_ref="main", fetch=False)
        self.assertEqual(len(observed), 1)
        self.assertFalse(observed[0].base_ok)

    def test_dirty_and_untracked_files_reported(self):
        wt_path = self.root / "wt-dirty"
        git(["worktree", "add", "-b", "cc/dirty", str(wt_path), "main"], self.repo)
        (wt_path / "README.md").write_text("edited\n")
        (wt_path / "new-doc.md").write_text("brand new\n")

        _, observed = wt_mod.inspect(self.repo, base_ref="main", fetch=False)
        wt = observed[0]
        self.assertEqual(wt.dirty_files, ["README.md"])
        self.assertEqual(wt.untracked_files, ["new-doc.md"])
        self.assertIn("new-doc.md", wt.untracked_texts)

    def test_non_agent_branches_are_ignored(self):
        wt_path = self.root / "wt-human"
        git(["worktree", "add", "-b", "feature/human", str(wt_path), "main"], self.repo)

        _, observed = wt_mod.inspect(self.repo, base_ref="main", fetch=False)
        self.assertEqual(observed, [])

    def test_unresolvable_base_yields_none(self):
        wt_path = self.root / "wt-nobase"
        git(["worktree", "add", "-b", "codex/nobase", str(wt_path), "main"], self.repo)

        base_sha, observed = wt_mod.inspect(
            self.repo, base_ref="origin/main", fetch=False
        )
        self.assertEqual(base_sha, "")
        self.assertIsNone(observed[0].base_ok)


if __name__ == "__main__":
    unittest.main()
