# ADR-034: Federated Identity from GitHub Actions to Azure

## Context

Deploy and acceptance workflows need access to AKS, Key Vault, and Entra tokens. Long-lived Azure credentials in repository secrets would outlive individual runs and expand the effect of a repository compromise.

## Decision

Each service fork uses a dedicated user-assigned managed identity and GitHub OIDC federation through `azure/login`. The workflow contract consists of the `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and `AZURE_SUBSCRIPTION_ID` secrets. `AZURE_CLIENT_ID` is also a non-secret repository variable used as an onboarding and diagnostics marker.

The Stack command `spi onboard --verify` owns identity creation, the branch and internal pull-request federated subjects used by the workflows, AKS and Key Vault access, Kubernetes bindings, repository configuration, and the first deployment canary. Service workflows consume that contract and do not provision Azure access.

Services that declare a negative-authorization token use a shared Stack identity with no deployment role or OSDU entitlements. Onboarding writes its client identifier only to opted-in repositories. The integration action exchanges a separate GitHub OIDC assertion in an isolated Azure CLI configuration, exports the descriptor-selected token variable, and removes that state without replacing the service identity session.

- **Rejected alternative: store `AZURE_CREDENTIALS` JSON.** It is easy to configure, but it creates a renewable long-lived secret in every repository.
- **Rejected alternative: share one privileged deployment identity across all service forks.** It reduces onboarding work, but a compromise in one repository would cross service boundaries.
- **Rejected alternative: use an invalid token for negative tests.** It is simpler, but it tests authentication failure rather than an authenticated caller without entitlements.

## Consequences

- GitHub stores identifiers but no reusable Azure client secret.
- Service identities isolate deployment access by repository.
- Negative-authorization suites exercise the intended 403 path with a valid caller.
- Federation subjects, repository configuration, and Azure RBAC must remain synchronized through the onboarding command.
