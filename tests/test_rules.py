# Copyright (c) 2026 Divergent Health, Inc. MIT License.
"""Rule evaluation tests using synthetic worktree observations."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from codex_watchdog.rules import evaluate, load_rules  # noqa: E402
from codex_watchdog.worktrees import WorktreeStatus  # noqa: E402


def make_worktree(**overrides):
    base = dict(
        path="/tmp/wt",
        branch="codex/test",
        head="b" * 40,
        base_ref="origin/main",
        base_sha="a" * 40,
        base_ok=True,
    )
    base.update(overrides)
    return WorktreeStatus(**base)


DIFF_TOUCHING_PUBKEY = """diff --git a/app/config.json b/app/config.json
index 111..222 100644
--- a/app/config.json
+++ b/app/config.json
@@ -1,3 +1,3 @@
-  "pubkey": "OLDKEY"
+  "pubkey": "NEWKEY"
"""

DIFF_OTHER_FILE_PUBKEY = """diff --git a/docs/notes.md b/docs/notes.md
index 111..222 100644
--- a/docs/notes.md
+++ b/docs/notes.md
@@ -1,1 +1,2 @@
 notes
+the pubkey is documented elsewhere
"""


class RulesTest(unittest.TestCase):
    def setUp(self):
        self.rules = load_rules()
        self.rules.update(
            {
                "forbidden_paths": ["package-lock.json", "docs/INDEX.md"],
                "banned_patterns": ["--grep-invert"],
                "protected_lines": [{"path": "app/config.json", "pattern": "pubkey"}],
                "watch_paths": [".github/workflows/**"],
            }
        )

    def test_clean_worktree_produces_no_findings(self):
        findings = evaluate(self.rules, make_worktree())
        self.assertEqual(findings, [])

    def test_stale_base_is_a_violation(self):
        findings = evaluate(self.rules, make_worktree(base_ok=False))
        self.assertEqual([f.kind for f in findings], ["stale-base"])
        self.assertEqual(findings[0].severity, "violation")

    def test_unresolvable_base_is_not_a_violation(self):
        findings = evaluate(self.rules, make_worktree(base_ok=None))
        self.assertEqual(findings, [])

    def test_forbidden_path_hit_on_dirty_file(self):
        findings = evaluate(
            self.rules, make_worktree(dirty_files=["package-lock.json"])
        )
        self.assertEqual([f.kind for f in findings], ["forbidden-path"])

    def test_forbidden_path_hit_on_committed_change(self):
        findings = evaluate(
            self.rules, make_worktree(changed_files=["docs/INDEX.md"])
        )
        self.assertEqual([f.kind for f in findings], ["forbidden-path"])

    def test_watch_path_reports_but_does_not_violate(self):
        findings = evaluate(
            self.rules,
            make_worktree(changed_files=[".github/workflows/release.yml"]),
        )
        self.assertEqual([f.severity for f in findings], ["watch"])

    def test_banned_pattern_in_added_line(self):
        diff = (
            "diff --git a/scripts/test.sh b/scripts/test.sh\n"
            "--- a/scripts/test.sh\n"
            "+++ b/scripts/test.sh\n"
            "+npx playwright test --grep-invert flaky\n"
        )
        findings = evaluate(self.rules, make_worktree(diff_text=diff))
        self.assertEqual([f.kind for f in findings], ["banned-pattern"])

    def test_banned_pattern_in_removed_line_is_fine(self):
        diff = (
            "diff --git a/scripts/test.sh b/scripts/test.sh\n"
            "--- a/scripts/test.sh\n"
            "+++ b/scripts/test.sh\n"
            "-npx playwright test --grep-invert flaky\n"
            "+npx playwright test\n"
        )
        findings = evaluate(self.rules, make_worktree(diff_text=diff))
        self.assertEqual(findings, [])

    def test_banned_pattern_in_new_untracked_file(self):
        findings = evaluate(
            self.rules,
            make_worktree(
                untracked_files=["ci.sh"],
                untracked_texts={"ci.sh": "test --grep-invert slow"},
            ),
        )
        self.assertEqual([f.kind for f in findings], ["banned-pattern"])

    def test_protected_line_change_in_target_file(self):
        findings = evaluate(
            self.rules,
            make_worktree(
                changed_files=["app/config.json"], diff_text=DIFF_TOUCHING_PUBKEY
            ),
        )
        self.assertEqual([f.kind for f in findings], ["protected-line"])

    def test_protected_pattern_in_other_file_is_fine(self):
        findings = evaluate(
            self.rules,
            make_worktree(
                changed_files=["docs/notes.md"], diff_text=DIFF_OTHER_FILE_PUBKEY
            ),
        )
        self.assertEqual(findings, [])

    def test_double_star_glob_matches_nested_paths(self):
        findings = evaluate(
            self.rules,
            make_worktree(changed_files=[".github/workflows/nested/deep.yml"]),
        )
        self.assertEqual([f.kind for f in findings], ["watch-path"])


if __name__ == "__main__":
    unittest.main()
