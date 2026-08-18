# ADR-036: Workflow Trust Boundaries for CI/CD

## Context

- New CI/CD jobs (`docker-push`, `deploy`, `integration-test`) hold credentials with real blast radius:
  - `docker-push` uses `packages: write` on GHCR.
  - `deploy` / `integration-test` use an Azure federated identity with AKS Cluster User, a least-privilege custom Role on the shared `osdu` namespace, and Key Vault Secrets User.
- The read-only `📦 Container Image Validation` job runs with
  `permissions: contents: read` only (no GHCR write, no Azure login) and is
  therefore out of scope for this trust boundary. Trusted runs repeat the
  cache-backed BuildKit solve in `📤 Build & Publish Container Image`, whose
  job-level `packages: write` permission is protected by this ADR.
- GitHub event contexts are not equally trusted; some (`pull_request_target`, external-fork PRs, dependabot PRs) can place attacker-controlled code in a context with secret access. Running the credential-bearing jobs there would expose the cluster federated identity to attacker code, risking compromise across the current service forks.

## Decision

Enforce a single trust-boundary model for credential-bearing jobs, per the event matrix below (authoritative):

| Event | Code source | Secret access | Deploy stages run? |
|---|---|---|---|
| `push` to `main` / `fork_integration` / `fork_upstream` | Repo HEAD (post-merge) | Yes | **Yes** |
| `pull_request` from internal branch (head repo == base repo) | PR HEAD | Yes | **Yes** |
| `pull_request` from external fork | PR HEAD | No (GH default) | No — would fail at `azure/login` anyway, but explicitly skipped to avoid noise |
| `pull_request_target` (base-repo context) | PR HEAD (checked out via explicit ref) | Yes | **No** — too dangerous; would let a PR exfiltrate the federated identity by running arbitrary code in a workflow with secret access |
| `dependabot[bot]` PR | PR HEAD | Limited (Dependabot secrets scope only) | No — `dependabot-validation.yml` is the dependency-update path |
| `workflow_dispatch` | Repo HEAD at chosen ref | Yes | **Yes**, but only when `inputs.force_full_pipeline == true` (the operator is the manual gate) |
| Tag push (release-please) | Tagged commit (already in `main`) | Yes | **No** — tag pushes go through `release.yml`, not `validate.yml`; `release.yml` only re-tags the existing image with the semver (via `GITHUB_TOKEN` to GHCR — no `azure/login`) and does not re-deploy. No tag-scoped Azure federated subject is exercised today; `refs/tags/*` is provisioned only if a future registry pivot (§7.4) moves image auth to OIDC. |
| Cascade workflow push to `fork_integration` | Cascade-resolved tree | Yes | Yes |

Credential-bearing jobs all replicate this **event-trust predicate**:

```yaml
(
  github.actor != 'dependabot[bot]' &&
  github.event_name != 'pull_request_target' &&
  github.event_name != 'workflow_dispatch' &&
  (github.event_name != 'pull_request' ||
   github.event.pull_request.head.repo.full_name == github.repository)
) || (
  github.event_name == 'workflow_dispatch' &&
  inputs.force_full_pipeline == true
)
```

Each job combines that predicate with its actual direct predecessor:

```yaml
# Build & Publish Container Image
if: |
  !cancelled() &&
  needs.docker-build.result == 'success' &&
  ( <event-trust predicate above> )

# Deploy to spi-stack (Java only)
if: |
  !cancelled() &&
  needs.read-service-config.outputs.build_lane == 'java' &&
  needs.docker-push.result == 'success' &&
  vars.AZURE_CLIENT_ID != '' &&
  ( <event-trust predicate above> )

# Integration Tests (Java only)
if: |
  !cancelled() &&
  needs.read-service-config.outputs.build_lane == 'java' &&
  needs.docker-push.result == 'success' &&
  needs.deploy.result == 'success' &&
  vars.AZURE_CLIENT_ID != '' &&
  ( <event-trust predicate above> )
```

The angle-bracket line is explanatory pseudocode; the checked-in workflow
expands the full predicate at every credentialed job.

For example, the publication job's concrete normal/dispatch arms are:

```yaml
if: |
  !cancelled() &&
  needs.docker-build.result == 'success' &&
  (
    github.actor != 'dependabot[bot]' &&
    github.event_name != 'pull_request_target' &&
    github.event_name != 'workflow_dispatch' &&
    (github.event_name != 'pull_request' ||
     github.event.pull_request.head.repo.full_name == github.repository)
  ) || (
    !cancelled() &&
    needs.docker-build.result == 'success' &&
    github.event_name == 'workflow_dispatch' &&
    inputs.force_full_pipeline == true
  )
```

**Why the dependency chain is sufficient.** The selected language gate is
centralized in the read-only `Container Image Validation` job: it directly needs
the Java lane endpoint and the Python compatibility endpoint, and runs only when
the selected endpoint succeeded. `Build & Publish` directly requires that
validation result; deploy requires publication; integration requires deploy.
This produces a legible graph without weakening build provenance.

The **credential trust predicates remain replicated directly** on publication,
deploy and integration as defense in depth. They do not rely on skip propagation
from an upstream credentialed job. The `workflow_dispatch &&
force_full_pipeline` half is the W13 operator escape hatch, the only way to force
a full run when `paths-ignore` would otherwise skip a template-sync change. The
`github.event_name != 'workflow_dispatch'` guard in the first half is
load-bearing: without it, a plain dispatch could push credential-bearing jobs
without operator opt-in. None of the event guards may be dropped.

## Consequences

### Positive

- Cluster credentials are never exposed to attacker-controlled PR execution contexts.
- Trust assumptions are explicit and consistently applied across service forks.
- Cascade pushes keep deploy/test signal for upstream-integration risk.

### Negative

- External-fork PRs do not receive deploy/integration-test signal; maintainers must run trusted validation before merging external contributions (documented in CONTRIBUTING).
- The `if:` clause is verbose and easy to weaken accidentally when adding a new sensitive job — enforce via review template.

### Neutral

- Read-only container validation continues to run broadly because it carries no
  sensitive credentials. Keeping it separate from publication costs a second,
  normally cache-backed solve on trusted runs, but prevents untrusted jobs from
  receiving registry write permission and lets Java validate the release
  multi-arch platform set only on the publish path.
- Dependabot keeps its dedicated validation path outside cluster-credential workflows.

## Alternatives Considered

- **Allow `pull_request_target` for deploy/test** — rejected: direct credential-exfiltration risk.
- **Allow external-fork PR deploy/test** — rejected: untrusted-code boundary.
- **Move trust checks to reviewer convention only** — rejected: policy must be enforced in the workflow `if:` guard, not left to human vigilance.

---

[← ADR-035](035-azure-only-maven-profile.md) | :material-arrow-up: [Catalog](index.md)
