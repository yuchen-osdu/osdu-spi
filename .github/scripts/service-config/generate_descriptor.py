#!/usr/bin/env python3
"""Detect the service shape during initialization and generate `.spi/service.yaml`.

Detection is deliberately narrow (ADR-039 §"halt instead of guessing"):

  pom.xml                      -> java-maven-azure
  pyproject.toml + uv.lock     -> python-uv-fastapi
  anything else / both / neither -> halt with an actionable error

An existing descriptor is never overwritten: the descriptor is fork-owned.

Usage:
  generate_descriptor.py --root . --service-name partition
  generate_descriptor.py --root . --check      # detect only, write nothing

Exit codes:
  0  descriptor generated, or already present
  2  service shape is ambiguous or unsupported — initialization must halt
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import descriptor as descriptor_module  # noqa: E402  (path set above for standalone use)


SUPPORTED_PYTHON_VERSIONS = ("3.11", "3.12", "3.13")
_NAME_RE = re.compile(r"[^a-z0-9-]+")


class DetectionError(Exception):
    """Raised when the repository shape cannot be classified safely."""

    def __init__(self, message: str, remediation: str) -> None:
        self.remediation = remediation
        super().__init__(message)


def normalize_service_name(raw: str) -> str:
    name = _NAME_RE.sub("-", raw.strip().lower()).strip("-")[:63]
    if not name or not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
        raise DetectionError(
            f"Cannot derive a valid service name from '{raw}'.",
            "Pass --service-name with a lowercase name such as 'partition'.",
        )
    return name


def _maven_markers(root: Path) -> List[Path]:
    found = [path for path in [root / "pom.xml"] if path.is_file()]
    found.extend(sorted(root.glob("*/pom.xml")))
    found.extend(sorted(root.glob("*/*/pom.xml")))
    return found


def detect_archetype(root: Path) -> Tuple[str, List[str]]:
    """Return `(archetype, evidence)` or raise `DetectionError`."""

    maven = _maven_markers(root)
    pyproject = (root / "pyproject.toml").is_file()
    uv_lock = (root / "uv.lock").is_file()

    if maven and pyproject:
        raise DetectionError(
            "Both Maven (pom.xml) and Python (pyproject.toml) build files were found.",
            "Commit a hand-written .spi/service.yaml that names the intended archetype, "
            "then re-run initialization.",
        )
    if maven:
        return "java-maven-azure", [str(path.relative_to(root)).replace("\\", "/") for path in maven[:3]]
    if pyproject and uv_lock:
        return "python-uv-fastapi", ["pyproject.toml", "uv.lock"]
    if pyproject and not uv_lock:
        raise DetectionError(
            "pyproject.toml was found but uv.lock is missing.",
            "Only uv-managed Python services are supported; commit uv.lock upstream or "
            "add a hand-written .spi/service.yaml.",
        )
    raise DetectionError(
        "No supported build file was found (expected pom.xml, or pyproject.toml with uv.lock).",
        "Add a hand-written .spi/service.yaml declaring a supported archetype, or onboard the "
        "service once its build system is supported by the template.",
    )


def _detect_python_runtime(root: Path) -> Optional[str]:
    try:
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    match = re.search(r"^\s*requires-python\s*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE)
    if not match:
        return None
    versions = re.findall(r"3\.\d+", match.group(1))
    for version in versions:
        if version in SUPPORTED_PYTHON_VERSIONS:
            return version
    return None


def _detect_python_distribution(root: Path) -> Optional[str]:
    try:
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    match = re.search(r"^\s*name\s*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE)
    if not match:
        return None
    distribution = match.group(1)
    return distribution if re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$", distribution) else None


HEADER = """# Service descriptor — owned by this repository, not by the template.
#
# Template-sync never overwrites `.spi/**`. Changes here are normal reviewed
# pull requests and select only unprivileged build/test behaviour: no Azure
# identity, cluster, namespace, environment, secret or workflow reference may
# appear in this file (ADR-039).
#
# Schema: .github/scripts/service-config/schema.json
# Generated during repository initialization; edit as the service evolves.
"""


def render_descriptor(archetype: str, service_name: str, root: Path) -> str:
    lines = [
        HEADER,
        "schemaVersion: 1",
        "",
        "service:",
        f"  name: {service_name}",
        f"  archetype: {archetype}",
    ]
    if archetype == "python-uv-fastapi":
        lines.extend(["", "build:", "  python:", "    packageManager: uv", "    lockfile: uv.lock"])
        runtime = _detect_python_runtime(root)
        if runtime:
            lines.append(f'    runtimeVersion: "{runtime}"')
        distribution = _detect_python_distribution(root)
        if distribution:
            lines.append(f"    distribution: {distribution}")
    lines.append("")
    return "\n".join(lines)


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root to inspect")
    parser.add_argument("--service-name", default="", help="Service name (defaults to the repository directory name)")
    parser.add_argument("--check", action="store_true", help="Detect only; do not write a descriptor")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    descriptor_module.configure_stdio()
    root = Path(args.root).resolve()
    target = root / descriptor_module.DESCRIPTOR_PATH

    if target.is_file():
        print(f"✅ {descriptor_module.DESCRIPTOR_PATH} already exists — leaving the fork-owned descriptor untouched.")
        return 0

    try:
        archetype, evidence = detect_archetype(root)
        service_name = normalize_service_name(args.service_name or root.name)
    except DetectionError as error:
        print(f"::error::Service descriptor generation halted: {error}")
        print(f"::error::{error.remediation}")
        return 2

    print(f"Detected archetype '{archetype}' from: {', '.join(evidence)}")
    if args.check:
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_descriptor(archetype, service_name, root), encoding="utf-8")

    config = descriptor_module.resolve(root, service_name=service_name)
    if not config.valid:
        for error in config.errors:
            print(f"::error::Generated descriptor failed validation: {error.render()}")
        return 2

    print(f"✅ Generated {descriptor_module.DESCRIPTOR_PATH} (archetype: {archetype}, service: {service_name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
