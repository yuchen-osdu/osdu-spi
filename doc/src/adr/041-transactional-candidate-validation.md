# ADR-041: Transactional Candidate Validation

## Context

Separate deployment and acceptance jobs release their concurrency lock between phases. A newer run can then replace the candidate before the older run tests it, and either run can leave its image in the shared Stack.

## Decision

One credentialed job holds a per-service concurrency group with cancellation disabled while it deploys, tests, and restores. Different services keep independent groups.

Before mutation, the deploy action captures the complete immutable image reference from the target container. The job deploys the candidate digest, verifies the running pod digest, runs the descriptor-selected Java or Python acceptance suite, and always attempts to restore the captured repository and digest.

Each phase records its outcome before one final verdict. The stable `🚀 Deploy to spi-stack` and `🧪 Integration Tests` summary jobs fail when an expected publication, deployment, test, or restore result is missing. The operator restore workflow accepts the same complete immutable image reference for break-glass recovery.

- **Rejected alternative: keep deploy and test as separate jobs with the same concurrency group.** It preserves a simpler graph, but the group is released between jobs and cannot protect the candidate under test.
- **Rejected alternative: record only the previous digest.** It is shorter, but restoration can target the wrong registry or repository.
- **Rejected alternative: serialize the entire Stack with one fleet lock.** It prevents cross-service interference, but it removes safe parallel validation without evidence that all services conflict.

## Consequences

- A newer run for the same service waits until restoration completes.
- Passed and failed tests attempt to return the Deployment to its exact pre-run image.
- Restore failure fails both stable checks because the environment is not known to be clean.
- Runner loss or forced cancellation can still prevent cleanup and requires operator recovery.
- The action logs in to Azure again for restore because deploy and restore use the same composite action.
