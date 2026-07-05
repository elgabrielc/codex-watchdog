# Copyright (c) 2026 Divergent Health, Inc. MIT License.
"""Session observation tests against a synthetic Codex home; never reads ~/.codex."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codex_watchdog import sessions as sessions_mod  # noqa: E402


class SessionsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name)

    def write_index(self, lines):
        (self.home / "session_index.jsonl").write_text("\n".join(lines) + "\n")

    def test_threads_sorted_newest_first_and_junk_tolerated(self):
        self.write_index(
            [
                '{"id":"1","thread_name":"older","updated_at":"2026-07-05T10:00:00Z"}',
                "not json at all",
                '{"id":"2","thread_name":"newer","updated_at":"2026-07-05T14:30:00Z"}',
            ]
        )
        info = sessions_mod.observe(codex_home=self.home, process_runner=lambda: "")
        self.assertEqual([t["thread_name"] for t in info["threads"]], ["newer", "older"])

    def test_newest_rollout_found_recursively(self):
        day_dir = self.home / "sessions" / "2026" / "07" / "05"
        day_dir.mkdir(parents=True)
        older = day_dir / "rollout-2026-07-05T09-00-00-aaa.jsonl"
        newer = day_dir / "rollout-2026-07-05T12-00-00-bbb.jsonl"
        older.write_text("{}\n")
        newer.write_text("{}\n{}\n")
        import os

        os.utime(older, (1000, 1000))
        os.utime(newer, (2000, 2000))

        info = sessions_mod.observe(codex_home=self.home, process_runner=lambda: "")
        self.assertTrue(info["newest_rollout"]["path"].endswith("bbb.jsonl"))

    def test_missing_home_is_graceful(self):
        info = sessions_mod.observe(
            codex_home=self.home / "does-not-exist", process_runner=lambda: ""
        )
        self.assertEqual(info["threads"], [])
        self.assertEqual(info["newest_rollout"], {})

    def test_process_filter_ignores_incidental_matches(self):
        listing = (
            "111 /Applications/Codex.app/Contents/Resources/codex app-server\n"
            "222 npm exec playwright PATH=/var/run/codex.system/bootstrap\n"
            "333 /usr/local/bin/codex exec --task x\n"
        )
        info = sessions_mod.observe(
            codex_home=self.home, process_runner=lambda: listing
        )
        pids = [p["pid"] for p in info["processes"]]
        self.assertEqual(pids, ["111", "333"])


if __name__ == "__main__":
    unittest.main()
