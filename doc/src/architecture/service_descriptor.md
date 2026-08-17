# Service Descriptor (`.spi/service.yaml`)

The service descriptor is the one file a fork owns that tells the copied workflows *what this
repository is*. It is created during initialization, validated by a template-owned schema, and
never overwritten by template-sync ([ADR-039](../adr/039-fork-owned-service-descriptor.md)).

## What it looks like

A conventional Java service needs almost nothing:

```yaml
schemaVersion: 1

service:
  name: partition
  archetype: java-maven-azure
```

A Python service records the facts the Python lane needs:

```yaml
schemaVersion: 1

service:
  name: wellbore-ddms-worker
  archetype: python-uv-fastapi

build:
  python:
    runtimeVersion: "3.12"
    packageManager: uv
    lockfile: uv.lock

tests:
  unit:
    type: pytest
    path: tests/unit
    coverage: true
```

The full field list is the template-owned schema at
`.github/scripts/service-config/schema.json`.

## Supported archetypes

| Archetype | Selected when | Build lane installed |
| --- | --- | --- |
| `java-maven-azure` | `pom.xml` is present at initialization | Yes |
| `python-uv-fastapi` | `pyproject.toml` and `uv.lock` are present | Not yet — declaring it fails the required check closed |

Anything else halts initialization with an actionable message instead of guessing a build lane.

## What it may never contain

The descriptor is edited by ordinary pull requests, so it is restricted to closed-enum, path and
name data. Azure identity, subscription/tenant, cluster, namespace, Deployment/container target,
GitHub Environment, secrets, permissions, workflow or action references and arbitrary commands are
rejected by the validator. Those values stay in repository/environment variables written by
`spi onboard` and in Stack-side configuration.

## How the workflows use it

`build.yml` and `validate.yml` start with a `read-service-config` job that emits a fixed output set:

```text
descriptor_present  schema_version  archetype     service_name  dockerfile_profile
unit_test_type      has_coverage    build_lane    lane_implemented  fallback
```

`build_lane` selects the statically declared language job. The required check keeps its exact
context name, `🐳 Docker Build`, and fails closed when the descriptor is invalid or declares an
archetype whose lane is not installed in the fork's template version.

For `pull_request_target` runs the descriptor and its parser are restored from `origin/main`, so an
untrusted branch can never influence a privileged run.

## Changing the descriptor

1. Edit `.spi/service.yaml` in a normal pull request.
2. The change is build-relevant: `.spi/**` always runs the selected build lane and CodeQL.
3. `/.spi/` is owned in `CODEOWNERS`. If your organization has not configured
   `SPI_ENGINEERING_OWNERS`, the seeded rule is a documented placeholder and `settings-apply`
   tracks it in the onboarding issue until a real team is set.

## Local validation

```bash
# Resolve the descriptor exactly as the workflows do
python3 .github/scripts/service-config/read_service_config.py --root . --format json

# Regenerate a missing descriptor (never overwrites an existing one)
python3 .github/scripts/service-config/generate_descriptor.py --root . --service-name partition

# Seed or refresh the /.spi/ ownership rule
python3 .github/scripts/service-config/generate_codeowners.py \
  --path CODEOWNERS --owners "@my-org/engineering-system"
```

No third-party packages are required: the parser is a strict, checked-in YAML subset reader that
runs on the standard library available on every GitHub-hosted runner. Keep descriptors simple —
anchors, aliases, tags, block scalars and multiple documents are rejected by design.

## Forks without a descriptor

Existing forks keep working. With no descriptor and a `pom.xml` present, the workflows fall back to
the legacy Java inference and log a warning; with no descriptor and no Maven markers the required
check passes as it always did.
