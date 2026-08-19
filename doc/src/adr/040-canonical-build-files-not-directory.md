# ADR-040: Sync Canonical Build Files Without Owning the Directory

## Status

Accepted.

## Context

ADR-037 made the engineering system responsible for canonical Java and Python
Dockerfiles. The initial sync rule owned the whole `build/` directory. Some
upstream services keep other active build tooling beside those Dockerfiles,
and directory replacement deleted those service-owned files.

## Decision

Synchronize the five canonical build files individually:

- `build/Dockerfile`
- `build/docker-entrypoint.sh`
- `build/python/Dockerfile`
- `build/python/Dockerfile.dockerignore`
- `build/python/docker-entrypoint.sh`

Do not treat the enclosing `build/` directory as template-owned.

## Consequences

- Canonical image recipes still receive every central security and runtime
  update.
- Service-owned scripts and metadata beside those recipes survive
  initialization and template sync.
- Adding another canonical build file requires an explicit sync-config entry.
