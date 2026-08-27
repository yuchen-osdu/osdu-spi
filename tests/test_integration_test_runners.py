"""Behaviour tests for the language-aware live integration-test action."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
ACTION = ROOT / ".github" / "actions" / "integration-test" / "action.yml"


def _load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validator = _load_module(
    "validate_runner_inputs",
    ".github/actions/integration-test/validate_runner_inputs.py",
)
resolver = _load_module(
    "resolve_acceptance_config",
    ".github/actions/integration-test/resolve_acceptance_config.py",
)


class RunnerInputValidationTests(unittest.TestCase):
    def test_accepts_existing_maven_directory_without_a_python_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "acceptance").mkdir()

            validator.validate(
                root,
                test_type="maven",
                test_dir="acceptance",
                python_runner="",
                python_version="",
                uv_version="",
                python_test_extras="",
            )

    def test_preserves_absolute_maven_test_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            external = root.parent / f"{root.name}-external acceptance"
            external.mkdir()
            try:
                validator.validate(
                    root,
                    test_type="maven",
                    test_dir=str(external),
                    python_runner="",
                    python_version="",
                    uv_version="",
                    python_test_extras="",
                )
            finally:
                external.rmdir()

    def test_accepts_a_locked_python_runner_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests" / "acceptance").mkdir(parents=True)
            (root / ".spi").mkdir()
            (root / ".spi" / "run_acceptance.py").write_text(
                "print('ok')\n", encoding="utf-8"
            )

            validator.validate(
                root,
                test_type="python",
                test_dir="tests/acceptance",
                python_runner=".spi/run_acceptance.py",
                python_version="3.12",
                uv_version="0.12.5",
                python_test_extras="dev,az",
            )

    def test_rejects_traversal_non_python_runners_and_invalid_extras(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            (root / "runner.sh").write_text("exit 0\n", encoding="utf-8")
            (root / "runner.py").write_text("print('ok')\n", encoding="utf-8")

            cases = (
                {"test_dir": "../tests", "python_runner": "runner.sh", "extras": "dev"},
                {"test_dir": "tests", "python_runner": "runner.sh", "extras": "dev"},
                {
                    "test_dir": "tests",
                    "python_runner": "runner.py",
                    "extras": "dev,$(id)",
                },
            )
            for case in cases:
                with self.subTest(case=case), self.assertRaises(ValueError):
                    validator.validate(
                        root,
                        test_type="python",
                        test_dir=case["test_dir"],
                        python_runner=case["python_runner"],
                        python_version="3.12",
                        uv_version="0.12.5",
                        python_test_extras=case["extras"],
                    )

    def test_rejects_a_python_runner_symlink_that_escapes_the_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tests").mkdir()
            outside = root.parent / f"{root.name}-outside.py"
            outside.write_text("print('outside')\n", encoding="utf-8")
            runner = root / "runner.py"
            try:
                runner.symlink_to(outside)
            except OSError:
                self.skipTest("symlink creation is unavailable")
            try:
                with self.assertRaises(ValueError):
                    validator.validate(
                        root,
                        test_type="python",
                        test_dir="tests",
                        python_runner="runner.py",
                        python_version="3.12",
                        uv_version="0.12.5",
                        python_test_extras="dev",
                    )
            finally:
                runner.unlink(missing_ok=True)
                outside.unlink(missing_ok=True)


class AcceptanceConfigResolutionTests(unittest.TestCase):
    def test_resolves_partition_bindings_and_maven_argv(self):
        config = {
            "type": "maven",
            "path": "partition-acceptance-test",
            "runnerPath": "",
            "mavenArguments": ["verify"],
            "rootTokenEnv": "ROOT_USER_TOKEN",
            "noDataAccessTokenEnv": "",
            "bindings": {
                "PARTITION_BASE_URL": {"source": "gateway", "suffix": "/"},
                "MY_TENANT": {"source": "partition"},
            },
            "keyVaultBindings": {},
            "dependencies": {},
            "timeoutMinutes": 25,
            "maxAttempts": 2,
        }

        outputs = resolver.resolve(
            json.dumps(config),
            {
                "GATEWAY_URL": "https://gateway.example/",
                "DATA_PARTITION_ID": "opendes",
                "ENTITLEMENT_DOMAIN": "dataservices.energy",
                "STORAGE_ACCOUNT_NAME": "storage",
            },
        )

        self.assertEqual("maven", outputs["test_type"])
        self.assertEqual('["verify"]', outputs["maven_arguments"])
        self.assertEqual(
            {
                "MY_TENANT": "opendes",
                "PARTITION_BASE_URL": "https://gateway.example/",
            },
            json.loads(outputs["env_map"]),
        )

    def test_resolves_wellbore_python_contract(self):
        config = {
            "type": "python",
            "path": ".",
            "runnerPath": "tests/integration/run_containerized_acceptance.py",
            "mavenArguments": [],
            "rootTokenEnv": "ROOT_USER_TOKEN",
            "noDataAccessTokenEnv": "",
            "bindings": {
                "WDMS_BASE_URL": {
                    "source": "gateway",
                    "suffix": "/api/os-wellbore-ddms",
                },
                "WDMS_ACL_DOMAIN": {"source": "entitlementDomain"},
                "WDMS_LEGAL_TAG": {"source": "partition", "suffix": "-wdms-ci"},
                "WDMS_DATA_PARTITION": {"source": "partition"},
            },
            "keyVaultBindings": {},
            "dependencies": {},
            "timeoutMinutes": 60,
            "maxAttempts": 2,
        }

        outputs = resolver.resolve(
            json.dumps(config),
            {
                "GATEWAY_URL": "https://gateway.example",
                "DATA_PARTITION_ID": "opendes",
                "ENTITLEMENT_DOMAIN": "dataservices.energy",
                "STORAGE_ACCOUNT_NAME": "storage",
            },
        )

        self.assertEqual("python", outputs["test_type"])
        self.assertEqual("[]", outputs["maven_arguments"])
        self.assertEqual("60", outputs["timeout_minutes"])
        self.assertEqual(
            "opendes-wdms-ci",
            json.loads(outputs["env_map"])["WDMS_LEGAL_TAG"],
        )

    def test_fails_when_a_required_environment_fact_is_missing(self):
        config = {
            "type": "maven",
            "path": "testing",
            "mavenArguments": ["verify"],
            "bindings": {
                "DOMAIN": {"source": "entitlementDomain"},
            },
        }

        with self.assertRaisesRegex(ValueError, "ENTITLEMENT_DOMAIN is required"):
            resolver.resolve(json.dumps(config), {})

    def test_rejects_unsafe_or_inconsistent_contract_data(self):
        cases = [
            {
                "type": "maven",
                "path": "testing",
                "mavenArguments": ["verify;rm"],
            },
            {
                "type": "python",
                "path": ".",
                "runnerPath": "runner.py",
                "mavenArguments": ["verify"],
            },
            {
                "type": "maven",
                "path": "testing",
                "mavenArguments": ["verify"],
                "bindings": {
                    "URL": {"source": "gateway", "value": "https://other"},
                },
            },
            {
                "type": "maven",
                "path": "testing",
                "mavenArguments": ["verify"],
                "bindings": {
                    "GITHUB_ENV": {"source": "literal", "value": "overwrite"},
                },
            },
        ]

        for config in cases:
            with self.subTest(config=config), self.assertRaises(ValueError):
                resolver.resolve(json.dumps(config), {"GATEWAY_URL": "https://gateway"})


class IntegrationActionContractTests(unittest.TestCase):
    def test_python_environment_is_locked_before_azure_login(self):
        action = ACTION.read_text(encoding="utf-8")

        self.assertLess(
            action.index("Install locked Python acceptance environment"),
            action.index("Azure login (OIDC)"),
        )
        self.assertIn("args=(sync --locked)", action)
        self.assertIn("uv run --no-sync python", action)

    def test_runner_mode_is_closed_and_maven_path_is_preserved(self):
        action = ACTION.read_text(encoding="utf-8")

        self.assertIn("acceptance_config:", action)
        self.assertIn("resolve_acceptance_config.py", action)
        self.assertIn('case "$TEST_TYPE" in', action)
        self.assertIn("maven)", action)
        self.assertIn("python)", action)
        self.assertIn('mvn --batch-mode --no-transfer-progress "${maven_args[@]}"', action)
        self.assertIn('TEST_REPO_ROOT="$GITHUB_WORKSPACE"', action)
        self.assertIn('TEST_RESULTS_DIR="$report_dir"', action)
        self.assertNotIn("eval ", action)

    def test_python_runner_junit_is_uploaded_with_maven_reports(self):
        action = ACTION.read_text(encoding="utf-8")

        self.assertIn(
            "${{ steps.contract.outputs.test_dir }}/spi-integration-results/*.xml",
            action,
        )


if __name__ == "__main__":
    unittest.main()
