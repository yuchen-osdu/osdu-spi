# ADR-040: Sync Canonical Build Files Individually

## Context

The engineering system owns canonical Java and Python image files, while service-owned scripts and metadata also occupy `build/`. Replacing the directory would delete those service-owned files.

## Decision

Template sync copies these files individually:

- `build/Dockerfile`
- `build/docker-entrypoint.sh`
- `build/python/Dockerfile`
- `build/python/Dockerfile.dockerignore`
- `build/python/docker-entrypoint.sh`

The enclosing `build/` directory remains shared rather than template-owned.

- **Rejected alternative: synchronize the complete `build/` directory.** It is simpler to configure and automatically includes new canonical files, but it deletes unrelated service-owned content.
- **Rejected alternative: stop synchronizing canonical image files.** It preserves full service ownership, but security and runtime fixes would drift across forks.

## Consequences

- Canonical image assets receive central updates without taking ownership of neighboring files.
- Adding or removing a canonical asset requires an explicit sync-config change.
- Service repositories retain additional build tooling beside the canonical files.
