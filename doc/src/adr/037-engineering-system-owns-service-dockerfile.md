# ADR-037: Engineering-System-Owned Service Images

## Context

Service repositories do not provide consistent container recipes. Java provider Dockerfiles differ and become stale, while Python services need a locked source installation rather than a Spring Boot JAR copy. A copied workflow cannot depend on repository-specific image behavior that the template does not validate.

## Decision

The engineering system owns one canonical image recipe per descriptor lane:

- `build/Dockerfile` copies the Java lane's prebuilt Spring Boot JAR and canonical entrypoint. It performs no Maven build.
- `build/python/Dockerfile` installs the checked-out project from `pyproject.toml` and `uv.lock`, then copies only the runtime environment and canonical entrypoint.

The descriptor selects the lane. Java optionally declares `build.artifact.path`; otherwise the action tries the conventional Azure JAR path and Azure JAR discovery. Python declares a validated ASGI module and optional runtime extras.

Base images, the Dockerfile frontend, and the Python `uv` stage are digest-pinned. The Java image includes the checksum-pinned Application Insights agent. Build credentials are not accepted as build arguments; a Python private index uses a BuildKit secret.

Java validation builds `linux/amd64`, and Java publication builds `linux/amd64` and `linux/arm64`. The Python source image builds `linux/amd64` because dependency installation occurs inside the image build.

- **Rejected alternative: use service-owned Dockerfiles.** They permit service-specific packaging, but they create unreviewed drift and fail when a fork has no usable recipe.
- **Rejected alternative: run Maven inside the Java Dockerfile.** It produces a self-contained build, but it duplicates compilation, caching, tests, and coverage outside the validated Java job.
- **Rejected alternative: force both languages through one Dockerfile.** It reduces file count, but JAR copying and locked Python source installation have different inputs and provenance.

## Consequences

- Central base, agent, entrypoint, and runtime changes propagate to service forks.
- Java images contain the JAR built from the checked-out source.
- Python images resolve the committed lock with the same pinned `uv` version used by CI.
- A service requiring a different packaging model needs a reviewed archetype or canonical profile rather than a private CI Dockerfile.
