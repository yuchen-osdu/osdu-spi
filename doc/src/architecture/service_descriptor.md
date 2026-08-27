# Service Descriptor (`.spi/service.yaml`)

The service descriptor is the one file a fork owns that tells the copied workflows *what this
repository is*. It is created during initialization, validated by a template-owned schema, and
never overwritten by template-sync ([ADR-039](../adr/039-fork-owned-service-descriptor.md)).

## What it looks like

A Java service declares its build and live acceptance contract:

```yaml
schemaVersion: 2

service:
  name: partition
  archetype: java-maven-azure

build:
  mavenProfiles: [core, azure]

tests:
  acceptance:
    type: maven
    path: partition-acceptance-test
    mavenArguments: [verify]
    bindings:
      PARTITION_BASE_URL:
        source: gateway
        suffix: /
      MY_TENANT:
        source: partition
```

A Python service records the facts the Python lane needs:

```yaml
schemaVersion: 2

service:
  name: wellbore-ddms-worker
  archetype: python-uv-fastapi

build:
  python:
    runtimeVersion: "3.12"
    compatibilityVersions: ["3.13"]
    packageManager: uv
    lockfile: uv.lock
    distribution: osdu-wbddms-worker
    importPackage: wdmsworker
    testExtras: [dev]
    runtimeExtras: [az]

tests:
  unit:
    type: pytest
    path: tests/unit
    coverage: true
  serviceInProcess:
    type: pytest
    path: tests/service
  serviceSubprocess:
    type: pytest
    path: tests/service
  acceptance:
    type: python
    path: .
    runnerPath: tests/run_acceptance.py
    timeoutMinutes: 60
    bindings:
      WDMS_BASE_URL:
        source: gateway
        suffix: /api/os-wellbore-ddms
      WDMS_DATA_PARTITION:
        source: partition

container:
  appModule: wdmsworker.app:app
```

`container.appModule` is the ASGI target baked into the canonical Python image, because the Stack
chart cannot override a container command. Its pattern is deliberately narrow —
`<dotted.module>:<attribute>` — so the value can never carry a space, an option or a shell
metacharacter into a build argument. It is required for `python-uv-fastapi` and rejected for a Java
service.

The full field list is the template-owned schema at
`.github/scripts/service-config/schema.json`.

## Supported archetypes

| Archetype | Selected when | Build lane installed |
| --- | --- | --- |
| `java-maven-azure` | `pom.xml` is present at initialization | Yes — build, test, image, push, deploy, integration tests |
| `python-uv-fastapi` | `pyproject.toml` and `uv.lock` are present | Yes — build, test, image, push, deploy, pytest integration tests |

Anything else halts initialization with an actionable message instead of guessing a build lane. For
a Python service the ASGI module is detected the same way: an unambiguous `src/<package>/app.py`
defining a top-level `app` becomes `container.appModule`; anything less clear halts and asks for a
reviewed, hand-written descriptor.

## What it may never contain

The descriptor is edited by ordinary pull requests, so it is restricted to closed-enum, path,
name and structured test data. Azure identity, subscription/tenant, cluster, namespace,
Deployment/container target, permissions, workflow/action references and secret values are
rejected. Those values stay in repository variables and secrets written by `spi onboard`.

Both lanes use `tests.acceptance`. Java declares Maven arguments as individual argv tokens;
Python declares a repository-relative `.py` runner. Symbolic bindings such as `gateway`,
`partition`, `entitlementDomain` and `storageAccount` are resolved against environment facts
written by `spi onboard`. Optional Key Vault bindings may name a secret but never carry its value.
Reserved process and GitHub Actions environment names are rejected.

## How the workflows use it

`build.yml` and `validate.yml` start with a `read-service-config` job that emits a fixed output set:

```text
descriptor_present  schema_version  archetype     service_name  dockerfile_profile
unit_test_type      has_coverage    build_lane    lane_implemented  fallback
python_runtime_version  python_distribution  python_import_package
python_compatibility_versions  python_compatibility_matrix
python_test_extras  python_runtime_extras  python_unit_test_path
python_service_in_process_test_path  python_service_subprocess_test_path
python_acceptance_test_path  python_acceptance_runner_path  app_module
java_maven_profiles  service_target_jar  acceptance_config
```

`build_lane` selects the statically declared language job (`🔨 Java Build` or `🐍 Python Build`)
and the image profile: the Java lane keeps artifact mode with `build/Dockerfile`, the Python lane
builds `build/python/Dockerfile` from source plus `uv.lock` with `app_module` and
`python_runtime_extras` as build arguments. The Python outputs are also the python-build action's
inputs, so a fork parameterises its build by editing the descriptor, never the workflow.
Descriptor-declared compatibility versions run as a separate required matrix with uniquely named
artifacts; the canonical 3.12 runtime still owns the image build.

The required check keeps its exact context name, `🐳 Docker Build`, and fails closed when the
descriptor is invalid, when it declares an archetype whose lane is not installed in the fork's
template version, or when the selected lane did not actually build.

Deployment is shared because both lanes publish an immutable OCI digest. The integration action
resolves the common acceptance contract before Azure login and invokes either Maven argv or the
Python runner. An incomplete contract fails before credentials or Deployment mutation.

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

Schema version 1 and descriptor-less Java repositories remain build-compatible, but they are not
deploy-ready. Deploy and integration checks stay disabled until schema version 2 carries a complete
acceptance contract and `spi onboard --verify` records a successful first canary.
