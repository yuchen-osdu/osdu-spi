# ADR-038: Defer Generic Java Image Extra Files

## Context

The canonical Java image copies a built JAR and engineering-system runtime files. Reference services that need additional repository files at runtime do not fit this contract, and a generic Docker build argument can expand an empty or broad path and copy unintended build-context content.

The Python lane is not the same case. It installs the project from source, and runtime package data belongs in the Python distribution.

## Decision

The Java descriptor and Docker action do not expose a generic extra-file input. A Java service that requires auxiliary runtime files cannot use the canonical image until the engineering system defines and tests a specific contract.

Any later contract must accept repository-relative, non-empty paths; reject absolute paths and parent traversal; verify every source exists inside the build context; and copy only the declared files. It must remain engineering-system-owned rather than selecting a service Dockerfile.

- **Rejected alternative: pass ADME-style `OPTIONAL_FILES` directly to Docker.** It supports known reference-service layouts, but an empty or broad expansion can copy unintended context.
- **Rejected alternative: allow an arbitrary service Dockerfile for exceptions.** It unblocks unusual services, but it bypasses the ownership and patching guarantees in [ADR-037](037-engineering-system-owns-service-dockerfile.md).
- **Rejected alternative: copy the complete repository into the Java image.** It avoids path configuration, but it increases image content and can include source, metadata, or credentials that the runtime does not need.

## Consequences

- Java image inputs remain limited to the validated JAR and canonical runtime assets.
- Core Java services that need no auxiliary files require no additional image configuration.
- Reference services that depend on external runtime files remain unsupported until a bounded contract exists.
- Python package data continues through normal locked source packaging rather than a Java extra-file mechanism.
