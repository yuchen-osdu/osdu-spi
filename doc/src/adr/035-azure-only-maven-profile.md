# ADR-035: Azure-Only Maven Profiles

## Context

OSDU Java reactors contain shared modules and provider-specific modules. Activating an Azure profile disables Maven profiles marked `activeByDefault`, so `-P azure` can omit the shared core modules that the Azure module requires.

## Decision

The Java lane uses `core,azure` when the descriptor does not declare `build.mavenProfiles`. The descriptor carries any service-specific profile list as reviewed source data. The action validates the comma-separated profile value before passing it to Maven and never emits an empty `-P`.

Filtered `fork_upstream` validation uses `core` because that branch intentionally omits the fork-owned Azure modules. Acceptance-test Maven arguments remain a separate `tests.acceptance.mavenArguments` contract.

- **Rejected alternative: build every provider profile in normal SPI CI.** It gives cross-provider regression signal, but it spends build time on implementations that SPI does not ship.
- **Rejected alternative: activate only `azure`.** It is shorter, but Maven deactivates the default core profile and can leave required reactor modules unresolved.
- **Rejected alternative: keep the override only in a repository variable.** It permits administrative changes without a commit, but it is not branch-versioned or reviewed with the service.

## Consequences

- Java CI builds shared core and Azure modules by default.
- Services with different reactor layouts can declare an explicit profile set.
- Provider regressions outside Azure are not part of the normal SPI signal.
- Filtered upstream validation remains valid without pretending that fork-owned Azure source exists on `fork_upstream`.
