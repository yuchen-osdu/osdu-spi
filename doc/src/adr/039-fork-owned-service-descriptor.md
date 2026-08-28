# ADR-039: Fork-Owned Service Descriptor

## Context

Copied workflows need to know a repository's language, build shape, packaging inputs, and tests. Repeated runtime detection and repository variables scatter that information across unversioned surfaces, while template sync overwrites engineering-system workflow and action paths.

## Decision

Each service fork owns `.spi/service.yaml`, and template sync excludes `.spi/**`. Schema version 2 provides closed contracts for the `java-maven-azure` and `python-uv-fastapi` archetypes, their build inputs, container inputs, test suites, and acceptance contract.

Initialization generates a minimal schema-version-2 descriptor after the upstream tree is present. A Maven project selects Java; `pyproject.toml` with `uv.lock` selects Python; ambiguous or unsupported repository shapes fail instead of choosing a lane. Initialization never overwrites an existing descriptor.

The parser uses a restricted YAML subset and rejects unknown keys, unsupported archetypes, escaping paths, privileged configuration, unsafe environment names, and unsupported schema versions. Schema version 1 remains readable as a deprecated build-compatibility format, but it does not define a deploy-ready acceptance contract.

Workflows expose fixed outputs from one `read-service-config` job and gate statically declared Java and Python jobs from those outputs. An invalid descriptor fails the stable `🐳 Docker Build` required check. Without a descriptor, Maven markers retain the Java compatibility path.

Descriptor changes are build-relevant. `pull_request_target` validation restores the trusted parser and descriptor from `main`. Azure identity, subscription, cluster, namespace, Deployment, container, workflow permissions, action references, and secret values remain outside the descriptor.

- **Rejected alternative: store all service choices in repository variables.** Variables are convenient for operators, but they are not branch-versioned or reviewed with source.
- **Rejected alternative: keep a central service catalog in the template.** It gives one fleet view, but every service deviation becomes a template change and can drift from the fork.
- **Rejected alternative: generate separate Java and Python workflows.** It removes lane conditions, but copied workflows and required check names would diverge by repository.
- **Rejected alternative: parse unrestricted YAML with runtime dependencies.** It supports more YAML features, but it expands the input language and makes parsing depend on runner-installed packages.

## Consequences

- Build and test intent is reviewed with the service branch.
- Java and Python use one workflow graph and one stable required container check.
- Privileged Stack configuration remains under operator control.
- Descriptor evolution requires schema, parser, workflow, and test changes in the engineering system.
- Descriptor-less Maven forks continue to build during migration.
