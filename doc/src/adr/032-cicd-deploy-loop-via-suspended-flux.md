# ADR-032: Direct Candidate Deployment with Suspended Flux

## Context

The Stack establishes baseline service deployments through Flux. Candidate validation must replace a service image quickly without Flux or Helm reconciliation reverting the candidate during its test run.

## Decision

The shared Stack enters CI mode by suspending both Flux Kustomizations and HelmReleases. The deploy action refuses to mutate a Deployment unless it can list those resources and confirm that every reconciler is suspended.

Candidate deployment uses `kubectl set image` with an immutable `<repository>@sha256:<digest>` reference. Repository variables provide the namespace, Flux namespace, Deployment name, and container name; the workflow does not derive Kubernetes object names from the service name.

Deployment, testing, and restoration follow the transaction in [ADR-041](041-transactional-candidate-validation.md). Baseline reconciliation remains an operator action through the Stack CLI rather than part of each service run.

- **Rejected alternative: Flux image automation for every candidate.** It preserves GitOps reconciliation, but each candidate would require a Git change and controller latency.
- **Rejected alternative: a Helm release per pull request.** It provides isolation, but it adds namespaces, routing, cleanup, and resource ownership that the shared Stack does not provide.
- **Rejected alternative: direct mutation while Flux remains active.** It keeps self-healing enabled, but reconciliation can replace the candidate before or during tests.

## Consequences

- Candidate rollout uses the exact digest produced by the build.
- Flux and Helm self-healing are unavailable while the Stack is in CI mode.
- A wrong Flux namespace or any active reconciler fails deployment before mutation.
- Operators must perform baseline refresh and break-glass recovery when a transaction cannot restore the pre-run image.
