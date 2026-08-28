# ADR-025: Java/Maven Build Architecture

## Context

OSDU service repositories commonly use Java and Maven, but the fork template also supports a descriptor-selected Python lane. The engineering system needs one consistent Java path without forcing every repository into the same language.

## Decision

The `java-maven-azure` lane uses Temurin Java 17, Maven, Maven dependency caching, optional community repository settings, and JaCoCo reporting. It builds the checked-out source and uploads the resulting JARs for the container lane.

`.spi/service.yaml` selects the Java or Python lane. A repository without a descriptor retains the Java compatibility path when Maven project markers are present. Java build profiles and exceptional artifact paths are descriptor data; [ADR-035](035-azure-only-maven-profile.md) defines the Azure profile policy, and [ADR-037](037-engineering-system-owns-service-dockerfile.md) defines image construction.

- **Rejected alternative: support every build system through one generic command.** It would accommodate more repositories, but unreviewed command passthrough would weaken validation and make copied workflows inconsistent.
- **Rejected alternative: make Gradle the Java default.** Gradle supports richer build scripting, but OSDU service reactors and community repository settings use Maven.
- **Rejected alternative: require every repository to author its own build workflow.** It would maximize repository control, but it would remove the common required checks and central maintenance contract.

## Consequences

- Java repositories receive the same runtime, dependency, test, coverage, and artifact behavior.
- Python support does not replace the Java default or the descriptor-less Maven compatibility path.
- A non-Maven Java repository requires a new reviewed archetype rather than a free-form override.
- Community dependency access remains separate from the service artifact, which is always built from the checked-out source.
