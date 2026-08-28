# ADR-042: Opt-In Upstream Tree Transform

## Context

OSDU upstream repositories combine shared code with multiple provider implementations and their pipeline assets. Azure service forks need the shared code while keeping the Azure provider and Azure acceptance modules under fork ownership. Deleting unwanted upstream paths after a merge creates recurring modify/delete conflicts and leaves irrelevant files in review and scan surfaces.

Explicitly identified files in upstream history can prevent a GitHub push even when those files are absent from the tip. History cleanup and tip-tree reduction solve different problems and must compose deterministically.

The yuchen fleet contains Java and Python repositories with different ownership layouts, so the tree transform cannot be enabled globally by repository shape.

## Decision

`UPSTREAM_HISTORY_EXCLUDE_PATHS` optionally defines administrator-reviewed paths removed from upstream history with a pinned `git-filter-repo` version. Initialization and every later sync apply the same history rewrite. The resulting branch tip becomes the selected upstream source; without the variable, the raw upstream tip is the source.

A fork opts into tree transformation by committing `.github/upstream-filter.yml` on `main`. Without that file, sync retains the legacy merge path. Once the file exists, invalid configuration, unknown entries, missing expected paths, unresolved modules, or failed injections halt the sync with exit code 2; the workflow does not fall back after an opted-in transform fails.

For an opted-in fork, the workflow remains checked out on `main`. It materializes every tracked file from the selected upstream source through a scratch index, applies the deterministic filter, writes the resulting tree, and creates a merge-shaped `fork_upstream` commit whose parents are the previous `fork_upstream` tip and the selected upstream tip. `Upstream-Sha` and `Filter-Rev` trailers record the source commit and the engine-version-plus-config hash.

The filter applies these ownership rules:

- `provider/` and `devops/` are absent from generated `fork_upstream`;
- the per-service config classifies other top-level entries, testing modules, root Maven profiles, and FOSSA modules;
- fork-owned Azure provider and Azure test modules remain only on `fork_integration` and `main`;
- stored Azure profile and testing-module blocks are injected into upstream-owned poms;
- dangling modules are pruned, while expected kept and absent paths provide positive and negative checks.

After cascade merges the generated branch, the engine verifies that fork-owned Azure paths survived and stamps every upstream-derived version in their poms. Stamping fails unless no pre-bump version remains. Filtered `fork_upstream` validation builds `core`; Azure compilation occurs after the fork-owned paths rejoin on `fork_integration`.

Initialization does not enable the tree transform or seed fork-owned Azure trees automatically. A repository receives the legacy topology until an operator reviews its filter configuration and performs a cutover that preserves the Azure paths.

- **Rejected alternative: merge upstream and delete unwanted paths afterward.** It keeps ordinary merge history, but upstream edits to deleted paths create recurring modify/delete conflicts.
- **Rejected alternative: use sparse checkout or local ignore rules.** It reduces the working view, but the files remain in the branch tree and in scanners, dependency tools, and reviews.
- **Rejected alternative: enable one filter configuration across the fleet.** It reduces rollout work, but mixed repository layouts require service-specific ownership and classification.
- **Rejected alternative: use history filtering as the tree filter.** It can remove oversized historical paths, but rewriting all unwanted provider history would change lineage unnecessarily and would not maintain the fork-owned Azure split.

## Consequences

- Opted-in `fork_upstream` branches contain only classified upstream-owned content and injected references.
- Fork-owned Azure code survives later upstream deletion because it is absent from the generated branch lineage.
- Unknown upstream structure blocks sync for explicit classification instead of being silently kept or removed.
- Optional history exclusions permit GitHub-compatible lineage while preserving all non-excluded history.
- Existing unconfigured Java and Python forks keep legacy merge behavior.
- Initialization and cutover require operator work before a repository gains the reduced-tree model.
