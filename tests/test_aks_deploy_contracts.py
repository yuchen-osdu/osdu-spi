"""Contracts for transactional AKS deploy and restore workflows."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
ACTION = ROOT / ".github" / "actions" / "aks-deploy" / "action.yml"
PARSER = ROOT / ".github" / "actions" / "aks-deploy" / "parse_image_reference.py"
RESTORE = ROOT / ".github" / "template-workflows" / "restore-deployment.yml"


def _load_parser():
    spec = importlib.util.spec_from_file_location("parse_image_reference", PARSER)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load immutable image parser")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


parser = _load_parser()


class ImmutableImageParserTests(unittest.TestCase):
    def test_parses_registry_repository_and_digest(self):
        digest = "sha256:" + "a" * 64
        image = f"community.opengroup.org:5555/osdu/partition@{digest}"

        repository, parsed_digest = parser.parse_image_reference(image)

        self.assertEqual(
            "community.opengroup.org:5555/osdu/partition",
            repository,
        )
        self.assertEqual(digest, parsed_digest)

    def test_rejects_tags_missing_repositories_and_malformed_digests(self):
        invalid = (
            "ghcr.io/example/service:main",
            "sha256:" + "a" * 64,
            "ghcr.io/example/service@sha256:abc",
            "ghcr.io/example/service@sha256:" + "A" * 64,
            "ghcr.io/example/service @sha256:" + "a" * 64,
        )

        for image in invalid:
            with self.subTest(image=image):
                with self.assertRaisesRegex(
                    ValueError,
                    "image must match <repository>@sha256:<64-hex>",
                ):
                    parser.parse_image_reference(image)


class DeployRestoreContractTests(unittest.TestCase):
    def test_deploy_action_exposes_the_complete_previous_image(self):
        action = ACTION.read_text(encoding="utf-8")

        self.assertIn("previous_image:", action)
        self.assertIn("previous_repository:", action)
        self.assertIn("previous_digest:", action)
        self.assertIn(
            'python "$GITHUB_ACTION_PATH/parse_image_reference.py" "$IMAGE"',
            action,
        )
        self.assertIn("aks-${{ inputs.operation }}-diagnostics", action)

    def test_break_glass_restore_requires_a_complete_image(self):
        workflow = RESTORE.read_text(encoding="utf-8")

        self.assertIn("inputs.image", workflow)
        self.assertIn("steps.image.outputs.repository", workflow)
        self.assertIn("steps.image.outputs.digest", workflow)
        self.assertIn("operation: restore", workflow)
        self.assertIn("parse_image_reference.py", workflow)
        self.assertNotIn("inputs.digest", workflow)
        self.assertNotIn("compute-metadata.sh", workflow)


if __name__ == "__main__":
    unittest.main()
