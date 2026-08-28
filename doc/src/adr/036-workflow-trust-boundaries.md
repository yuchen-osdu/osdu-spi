# ADR-036: Credentialed Workflow Trust Boundaries

## Context

Image publication has package write access, and candidate validation has an Azure identity with cluster and secret access. Read-only build validation can accept a wider event set than those credentialed operations.

## Decision

Credential-bearing jobs enforce their trust predicate directly:

- image publication and candidate validation exclude Dependabot, `pull_request_target`, external-fork pull requests, and ordinary manual dispatches;
- push events on `fork_upstream` do not publish, and filtered `fork_upstream` changes do not produce the image prerequisite;
- internal pull requests and pushes to protected service branches run the credentialed path when their direct build prerequisites succeed;
- `workflow_dispatch` runs the path only when `force_full_pipeline` is true;
- candidate validation also requires onboarding configuration, and automatic runs require `DEPLOY_VALIDATED=true`.

Read-only jobs inspect pull-request content. On `pull_request_target`, workflows restore trusted actions, build files, and service-configuration tooling from `main` before running them. Each sensitive job receives only the job-level permissions it needs.

Stable summary jobs report an intentional skip or fail when an expected publication, deployment, test, or restore result is missing.

- **Rejected alternative: allow credentialed `pull_request_target` jobs.** It makes secrets available to automation PRs, but it would allow checked-out pull-request code to run in the base repository context and exfiltrate them.
- **Rejected alternative: deploy external-fork pull requests.** It improves contributor feedback, but it runs untrusted code with the service identity.
- **Rejected alternative: rely on an upstream sensitive job to skip all downstream jobs.** It reduces repeated expressions, but later dependency changes would reopen a credentialed path.

## Consequences

- Untrusted pull requests retain read-only build signal but receive no registry write or Stack access.
- Trusted internal changes can exercise the complete Java or Python delivery lane.
- Manual full-pipeline runs require an explicit operator choice.
- The repeated predicates are verbose and must be updated together when the event model changes.
