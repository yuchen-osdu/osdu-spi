# ADR-043: Descriptor-Owned Acceptance Contract

## Status

Accepted.

## Context

Live acceptance behavior was split between `.spi/service.yaml` and repository
variables. Python already declared its working directory and runner in the
descriptor, while Java used `ACCEPTANCE_TEST_DIR` and a free-form
`MAVEN_GOAL`. Both lanes depended on JSON-valued variables for environment
injection, dependency probes and Key Vault bindings.

Those variables were not versioned with service code, could not vary by branch,
and routinely drifted when a Stack environment was re-homed. In particular,
absolute gateway URLs remained pointed at retired ingress hosts. The free-form
Maven string also mixed goals, modules, profiles, properties and exclusions in
one shell-split value.

Azure identity, cluster coordinates, Deployment targets and secret values are
different: they identify a privileged environment and must not become
pull-request-controlled service metadata.

## Decision

Schema version 2 makes `tests.acceptance` the complete, branch-versioned test
contract for both Java and Python services.

The descriptor owns:

- acceptance type, working directory and Python runner;
- Maven argv tokens, Java build profiles and an optional target JAR path;
- token environment-variable names;
- bounded timeout and retry policy;
- dependency health paths;
- non-secret bindings from named Stack facts;
- optional environment-variable to Key Vault secret-name bindings.

The parser emits one deterministic `acceptance_config` JSON object. The
integration action resolves its bindings against environment facts written by
`spi onboard`: gateway URL, data partition, Entitlements domain and primary
storage account. Maven arguments remain an array and are passed to `mvn` as
argv; they are never evaluated or shell-split from one command string.

The descriptor may name a Key Vault secret but may never contain a secret
value. It may not select Azure identity, subscription, cluster, namespace,
Deployment, container, Flux namespace, gateway, Key Vault or any workflow
permission/action. Reserved process and GitHub Actions environment names are
rejected.

Repository rules require the stable deploy and integration summary checks only
after:

1. the descriptor contains a valid acceptance contract;
2. `spi onboard` has written every required environment binding; and
3. the first transactional canary has succeeded and set
   `DEPLOY_VALIDATED=true`.

Schema version 1 remains readable for build compatibility but does not describe
a deploy-ready service.

## Consequences

- Test behavior changes with the branch and is reviewed beside service code.
- Re-homing changes environment variables once; descriptor bindings follow the
  new environment without source edits.
- Java and Python use one acceptance contract and one integration action.
- A malformed or incomplete contract fails before Azure login or cluster
  mutation.
- Environment onboarding remains privileged and operator-approved.
- Existing test variables are removed after service descriptors move to schema
  version 2.

## Related Decisions

- [ADR-034: Federated Identity for Actions to Azure](034-federated-identity-actions-to-azure.md)
- [ADR-036: Workflow Trust Boundaries for CI/CD](036-workflow-trust-boundaries.md)
- [ADR-039: Fork-Owned Service Descriptor](039-fork-owned-service-descriptor.md)
- [ADR-041: Transactional Candidate Validation](041-transactional-candidate-validation.md)
