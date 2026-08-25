# ADR-041: Transactional Candidate Validation

## Status

Accepted.

## Context

Candidate deployment and live integration testing originally ran as separate
GitHub Actions jobs. Both jobs used the same concurrency group, but a job releases
that group when it finishes. A newer run could therefore deploy between the
older run's rollout and its integration tests.

The deploy action captured only the previous digest. The workflow did not consume
that output, and the manual restore workflow inferred the image repository from
the current GitHub repository. A failed or successful validation run could leave
its candidate running in the shared environment.

## Decision

Run candidate deploy, integration tests, and restore in one credentialed job
holding the existing per-service concurrency group for the complete transaction.

Before mutation, the deploy action requires and captures the complete immutable
image reference already configured on the Deployment:

```text
<repository>@sha256:<digest>
```

After tests, the transaction always attempts to restore that exact image. The PR
lane is responsible for undoing only its own mutation; converging the environment
to the Stack image lock remains a separate operator baseline-refresh concern.

The transaction records deploy, test, and restore outcomes before applying its
final failure result. Two unprivileged summary jobs retain the existing required
check names:

- `🚀 Deploy to spi-stack`
- `🧪 Integration Tests`

Those jobs run with `always()` and fail closed when an onboarded, trusted lane was
expected but image publication or the transaction did not complete.

No fleet-wide lock is introduced. Different services may continue to validate in
parallel. A future lock requires evidence that cross-service concurrency causes
real contamination.

## Consequences

- A newer run for the same service cannot replace the candidate between deploy
  and tests.
- Successful and failed tests return the service to its exact pre-run image.
- Restore works across GHCR, community registry, and future registries because
  the complete image reference is preserved.
- Restore failure blocks both required checks because the shared environment is
  not known to be clean.
- Manual cancellation or runner loss can still prevent cleanup. The break-glass
  restore workflow accepts the complete previous image from the transaction
  summary.
- The workflow performs a second Azure login during restore because it reuses the
  existing `aks-deploy` action. Removing that duplication is a later optimization,
  not a correctness requirement.

## Related Decisions

- [ADR-032: CI/CD Deploy Loop via Suspended Flux](032-cicd-deploy-loop-via-suspended-flux.md)
- [ADR-034: Federated Identity for Actions to Azure](034-federated-identity-actions-to-azure.md)
- [ADR-036: Workflow Trust Boundaries for CI/CD](036-workflow-trust-boundaries.md)
