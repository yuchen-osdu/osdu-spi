"""Tests for explicit upstream history filtering."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "filter_upstream_history.py"

SPEC = importlib.util.spec_from_file_location("filter_upstream_history", SCRIPT)
assert SPEC and SPEC.loader
FILTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FILTER)


class ExcludedPathTests(unittest.TestCase):
    def test_loads_comments_spaces_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "paths.txt"
            path.write_text(
                "\n# reviewed exception\nmedia/Wellbore DDMS kickoff with R3 team.mp4\n"
                "media/Wellbore DDMS kickoff with R3 team.mp4\n",
                encoding="utf-8",
            )

            self.assertEqual(
                ["media/Wellbore DDMS kickoff with R3 team.mp4"],
                FILTER.load_excluded_paths(path),
            )

    def test_rejects_absolute_and_parent_paths(self):
        for value in ("/absolute/file", "../outside", "folder/../../outside"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "paths.txt"
                path.write_text(value + "\n", encoding="utf-8")
                with self.assertRaises(ValueError):
                    FILTER.load_excluded_paths(path)

    def test_rejects_empty_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "paths.txt"
            path.write_text("# comments only\n\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                FILTER.load_excluded_paths(path)

    def test_filter_command_passes_paths_as_distinct_arguments(self):
        command = FILTER.filter_command(
            Path("/tmp/repo"),
            ["media/file with spaces.mp4", "docs/old.bin"],
        )

        self.assertEqual(
            [
                "git",
                "-C",
                str(Path("/tmp/repo")),
                "filter-repo",
                "--force",
                "--invert-paths",
                "--path",
                "media/file with spaces.mp4",
                "--path",
                "docs/old.bin",
            ],
            command,
        )


class WorkflowWiringTests(unittest.TestCase):
    def test_initialization_and_sync_use_the_same_explicit_filter(self):
        init = (ROOT / ".github" / "workflows" / "init-complete.yml").read_text(
            encoding="utf-8"
        )
        sync = (ROOT / ".github" / "template-workflows" / "sync.yml").read_text(
            encoding="utf-8"
        )
        sync_config = (ROOT / ".github" / "sync-config.json").read_text(encoding="utf-8")

        for workflow in (init, sync):
            self.assertIn("UPSTREAM_HISTORY_EXCLUDE_PATHS", workflow)
            self.assertIn("filter_upstream_history.py", workflow)
            self.assertIn("git-filter-repo==2.47.0", workflow)
            self.assertIn("history-filter-venv", workflow)

        self.assertIn(".github/scripts/filter_upstream_history.py", sync_config)
        self.assertIn("tests/test_upstream_history_filter.py", sync_config)
        self.assertIn('git merge "$UPSTREAM_SYNC_REF"', sync)
        self.assertNotIn("git merge upstream/$DEFAULT_BRANCH -X theirs", sync)

    def test_push_failure_handler_is_restored_after_upstream_checkout(self):
        init = (ROOT / ".github" / "workflows" / "init-complete.yml").read_text(
            encoding="utf-8"
        )
        restore = "git checkout main -- .github/local-actions/secret-push-handler"
        handler = "- name: Handle fork_upstream push protection"

        self.assertIn(restore, init)
        self.assertLess(init.index(restore), init.index(handler))

    def test_descriptor_remediation_retry_updates_integration_with_a_lease(self):
        init = (ROOT / ".github" / "workflows" / "init-complete.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("git ls-remote --heads origin fork_integration", init)
        self.assertIn(
            '--force-with-lease="refs/heads/fork_integration:$REMOTE_INTEGRATION_SHA"',
            init,
        )
        self.assertNotIn("git push -f origin fork_integration", init)


if __name__ == "__main__":
    unittest.main()
