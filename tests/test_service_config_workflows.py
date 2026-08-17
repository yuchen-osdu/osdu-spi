"""Regression tests for the descriptor-aware workflow contract (ADR-039).

These exercise the copied workflows' own logic: the changed-path filters are
extracted from the workflow YAML and evaluated, so a filter that stops treating
`.spi/**` as build-relevant fails here rather than silently green-lighting a
descriptor-only pull request.
"""

from __future__ import annotations

import fnmatch
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
VALIDATE = ROOT / ".github" / "template-workflows" / "validate.yml"
BUILD = ROOT / ".github" / "template-workflows" / "build.yml"
CODEQL = ROOT / ".github" / "template-workflows" / "codeql.yml"
SETTINGS_APPLY = ROOT / ".github" / "template-workflows" / "settings-apply.yml"
INIT_COMPLETE = ROOT / ".github" / "workflows" / "init-complete.yml"
DEV_CI = ROOT / ".github" / "workflows" / "dev-ci.yml"
SYNC_CONFIG = ROOT / ".github" / "sync-config.json"
CHECK_VARIABLES = ROOT / ".github" / "scripts" / "settings-apply" / "check-required-variables.sh"
DEPLOY_FORK_RESOURCES = (
    ROOT / ".github" / "local-actions" / "init-helpers" / "deploy-fork-resources.sh"
)

REQUIRED_CHECK_CONTEXT = 'name: "🐳 Docker Build"'


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_relevant(workflow_text: str, changed_file: str) -> bool:
    """Replay the workflow's own changed-path filter for a single file."""

    always_relevant = re.search(r'case "\$file" in ([^)]+)\)', workflow_text)
    ignore_pattern = re.search(r"grep -qE '([^']+)'", workflow_text)
    if not always_relevant or not ignore_pattern:
        raise AssertionError("changed-path filter not found in workflow")

    for glob in always_relevant.group(1).split("|"):
        if fnmatch.fnmatchcase(changed_file, glob.strip()):
            return True
    return not re.search(ignore_pattern.group(1), changed_file)


class ChangedPathFilterTests(unittest.TestCase):
    def test_descriptor_only_changes_run_the_required_validation(self):
        for workflow in (VALIDATE, CODEQL):
            with self.subTest(workflow=workflow.name):
                text = _read(workflow)
                self.assertTrue(_build_relevant(text, ".spi/service.yaml"))
                self.assertTrue(_build_relevant(text, ".spi/nested/extra.yaml"))

    def test_configuration_and_documentation_changes_still_skip(self):
        for workflow in (VALIDATE, CODEQL):
            with self.subTest(workflow=workflow.name):
                text = _read(workflow)
                self.assertFalse(_build_relevant(text, ".github/workflows/validate.yml"))
                self.assertFalse(_build_relevant(text, "README.md"))
                self.assertFalse(_build_relevant(text, ".gitignore"))

    def test_source_and_maven_settings_changes_remain_build_relevant(self):
        text = _read(VALIDATE)

        self.assertTrue(_build_relevant(text, "provider/partition-azure/src/main/java/App.java"))
        self.assertTrue(_build_relevant(text, ".mvn/community-maven.settings.xml"))

    def test_build_workflow_does_not_ignore_the_descriptor_path(self):
        paths_ignore = re.findall(r"paths-ignore:(.*?)(?=\n  [a-z]|\njobs:)", _read(BUILD), re.DOTALL)

        self.assertTrue(paths_ignore)
        for block in paths_ignore:
            self.assertNotIn(".spi", block)


class ServiceConfigPreludeTests(unittest.TestCase):
    def test_validate_publishes_the_fixed_output_contract(self):
        text = _read(VALIDATE)

        self.assertIn("read-service-config:", text)
        for output in (
            "descriptor_present:",
            "schema_version:",
            "archetype:",
            "service_name:",
            "dockerfile_profile:",
            "unit_test_type:",
            "has_coverage:",
            "build_lane:",
            "lane_implemented:",
            "fallback:",
        ):
            self.assertIn(output, text)
        self.assertIn("read_service_config.py", text)

    def test_language_neutral_selection_drives_the_java_lane(self):
        for workflow in (VALIDATE, BUILD):
            with self.subTest(workflow=workflow.name):
                text = _read(workflow)
                self.assertIn("needs.read-service-config.outputs.build_lane == 'java'", text)
                self.assertNotIn("needs.check-repo-state.outputs.is_java_repo == 'true' &&", text)

    def test_existing_java_behaviour_is_preserved(self):
        text = _read(VALIDATE)
        build_text = _read(BUILD)
        profile_expression = "${{ vars.MAVEN_PROFILE || 'core,azure' }}"

        self.assertIn('name: "🔨 Java Build"', text)
        self.assertIn("uses: ./.github/actions/java-build", text)
        self.assertIn(f"maven_profile: {profile_expression}", text)
        self.assertIn(f"maven_profile: {profile_expression}", build_text)

    def test_required_docker_build_context_is_unchanged(self):
        text = _read(VALIDATE)

        self.assertIn(REQUIRED_CHECK_CONTEXT, text)
        self.assertIn('name: "🐳 Docker Build (validate)"', text)

    def test_required_check_fails_closed_for_a_present_but_unsupported_archetype(self):
        text = _read(VALIDATE)
        summary = text.split("docker-build-required:", 1)[1]

        self.assertIn("needs.read-service-config.outputs.descriptor_present }}\" = \"true\"", summary)
        self.assertIn("needs.read-service-config.outputs.lane_implemented }}\" != \"true\"", summary)
        self.assertIn("has no build lane in this template version", summary)
        self.assertIn('needs.read-service-config.result }}" = "failure"', summary)

    def test_absent_descriptor_still_passes_the_required_check_for_non_java_repositories(self):
        summary = _read(VALIDATE).split("docker-build-required:", 1)[1]

        self.assertIn('needs.read-service-config.outputs.build_lane }}" = "none"', summary)
        self.assertIn("no build lane selected", summary)

    def test_pull_request_target_uses_the_trusted_main_descriptor(self):
        text = _read(VALIDATE)
        restore = text.split("Restore trusted service config", 1)[1].split("- name:", 1)[0]

        self.assertIn("github.event_name == 'pull_request_target'", restore)
        self.assertIn("git fetch origin main --depth=1", restore)
        self.assertIn("git checkout origin/main -- .spi/", restore)
        self.assertIn("git checkout origin/main -- .github/scripts/service-config/", restore)

    def test_python_build_action_is_not_referenced_yet(self):
        self.assertFalse((ROOT / ".github" / "actions" / "python-build").exists())

        for workflow in (VALIDATE, BUILD):
            with self.subTest(workflow=workflow.name):
                for line in _read(workflow).splitlines():
                    if "python-build" in line:
                        self.assertTrue(line.strip().startswith("#"), line)

    def test_integration_point_for_the_python_lane_is_documented(self):
        for workflow in (VALIDATE, BUILD):
            with self.subTest(workflow=workflow.name):
                self.assertIn("INTEGRATION POINT", _read(workflow))


class SettingsAndOwnershipTests(unittest.TestCase):
    def test_settings_apply_validates_the_descriptor_through_the_existing_issue(self):
        script = _read(CHECK_VARIABLES)

        self.assertEqual(1, script.count("ISSUE_TITLE="))
        self.assertIn("service-config/read_service_config.py", script)
        self.assertIn('--root . --format json --redact', script)
        self.assertIn("generate_codeowners.py", script)
        self.assertIn("missing+=(\"service descriptor", script)
        self.assertIn("CODEOWNERS rule for", script)

    def test_settings_apply_never_echoes_descriptor_or_secret_values(self):
        script = _read(CHECK_VARIABLES)

        self.assertIn("--redact", script)
        self.assertIn("no descriptor, secret or variable value is reproduced here", script)

    def test_settings_apply_runs_when_the_descriptor_changes(self):
        text = _read(SETTINGS_APPLY)

        self.assertIn("'.spi/**'", text)
        self.assertIn("'.github/scripts/service-config/**'", text)

    def test_initialization_generates_the_descriptor_and_seeds_ownership(self):
        init_text = _read(INIT_COMPLETE)
        deploy_text = _read(DEPLOY_FORK_RESOURCES)

        self.assertIn("generate_descriptor.py", init_text)
        self.assertIn("SPI_ENGINEERING_OWNERS", init_text)
        self.assertIn("generate_codeowners.py", deploy_text)
        self.assertIn("SPI_ENGINEERING_OWNERS", deploy_text)

    def test_sync_configuration_keeps_the_descriptor_service_owned(self):
        config = json.loads(_read(SYNC_CONFIG))
        directories = [entry["path"] for entry in config["sync_rules"]["directories"]]
        files = [entry["path"] for entry in config["sync_rules"]["files"]]
        service_owned = [entry["path"] for entry in config["service_owned"]["paths"]]

        self.assertIn(".github/scripts/service-config", directories)
        self.assertIn(".spi", config["exclusions"])
        self.assertIn(".spi/service.yaml", service_owned)
        self.assertIn("CODEOWNERS", service_owned)
        for path in directories + files:
            self.assertFalse(path.startswith(".spi"), path)

    def test_codeowners_cleanup_rule_documents_the_reseeding(self):
        config = json.loads(_read(SYNC_CONFIG))
        reasons = {
            entry["path"]: entry["reason"] for entry in config["cleanup_rules"]["files"]
        }

        self.assertIn("CODEOWNERS", reasons)
        self.assertIn("re-seeded", reasons["CODEOWNERS"])

    def test_dev_ci_validates_the_service_config_assets(self):
        text = _read(DEV_CI)

        self.assertIn("python -m unittest discover -s tests -p 'test_*.py' -v", text)
        self.assertIn(".github/scripts/service-config/schema.json", text)


if __name__ == "__main__":
    unittest.main()
