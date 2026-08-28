# ADR-043: Descriptor-Owned Acceptance Contract

## Context

Acceptance behavior was split between service descriptors, free-form Maven strings, and JSON repository variables. Those values were not branch-versioned and retained environment-specific URLs after a Stack move. Azure identity, cluster coordinates, Deployment targets, and secret values still require a privileged configuration boundary.

## Decision

Schema version 2 makes `tests.acceptance` the Java and Python acceptance contract. It declares the suite type, working directory, Python runner, Maven argument tokens, token environment names, bounded timeout and retry values, dependency health paths, named Stack-fact bindings, literal non-secret bindings, and optional environment-variable-to-Key-Vault-secret-name bindings.

The descriptor parser emits deterministic `acceptance_config` JSON. The integration action validates it again and resolves named facts from repository variables written by `spi onboard`: gateway URL, data partition, entitlement domain, and storage account. Maven arguments remain an array and are passed as argv. Python runners are validated repository-relative `.py` paths.

The descriptor is permitted to name a Key Vault secret but cannot contain its value. It cannot select Azure identity, subscription, cluster, namespace, Deployment, container, Flux namespace, workflow permissions, or action references. Reserved process and GitHub Actions environment identifiers are rejected.

`spi onboard --verify` supplies the privileged environment contract and performs the first transactional canary. Rulesets require the stable deploy and integration checks only when the descriptor has an acceptance contract, all referenced environment bindings exist, and `DEPLOY_VALIDATED=true`. A forced manual full-pipeline run provides the bootstrap path before that marker is set.

Schema version 1 remains readable for build compatibility but is not deploy-ready.

- **Rejected alternative: keep acceptance configuration in repository variables.** Variables are easy to rehome, but they are not branch-versioned and cannot be reviewed with test changes.
- **Rejected alternative: keep one free-form Maven command string.** It is compact and familiar, but shell splitting mixes goals, profiles, properties, and exclusions without a closed data contract.
- **Rejected alternative: place environment credentials or secret values in the descriptor.** It would make each branch self-contained, but pull requests would control privileged Stack access.

## Consequences

- Acceptance changes are reviewed and validated with the branch that uses them.
- Java and Python resolve one normalized contract through the same integration action.
- Rehoming changes Stack facts without rewriting service test metadata.
- Invalid contracts fail before Azure login or Deployment mutation.
- Deploy readiness depends on both service-owned descriptor data and operator-owned environment configuration.
