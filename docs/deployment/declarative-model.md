# Declarative Deployment Model

Status: **CURRENT architecture contract with Phase 4D read-only resolution.**

## Layers

Kalvin separates five kinds of input and evidence:

1. **Catalogs and vocabularies** define valid components, repositories, state/backup classes, exposure classes, privilege classes, dependency kinds, readiness gates, and compatibility metadata.
2. **Profiles** select a primary host role and declare required, optional, and forbidden components plus backup, exposure, repository, and readiness policy.
3. **Desired deployment manifests** record operator intent: profile, human-friendly refs, selected optional components, logical host-configuration reference, secret references, and approved compatibility entries.
4. **Resolution inputs** bind desired refs to immutable commits or immutable implementation versions, combine repository-safe defaults with profile and host-local configuration, and resolve external secret references without copying secret values into Git.
5. **Resolved plans** are deterministic Phase 4D calculations of exact selected versions, dependencies, configuration and secret-reference requirements, state/backup intent, exposure, privilege, and unverified readiness gates. They contain no timestamp or host observation.
6. **Deployed/observed records** are a future concern. They would report what actually ran, readiness evidence, host role, and deployment time. Phase 4D neither creates nor persists them.

Phase 4E adds an ephemeral **observed host capability** document. It describes sanitized local OS, CPU, memory, storage, mount, service, executable/runtime, Docker, and network capability observations. It is not desired state, is not a resolved deployment plan, and is not evidence that an application ran. The preflight result compares it with the resolved profile without changing either input.

Catalogs and profiles are committed public contracts. Host-local configuration, provider bindings, secret values, authoritative backup payloads, and future deployed records are host state outside Git. Phase 4D plans go from input files to memory to stdout and are not persisted by the engine.

## Desired versus resolved state

A desired profile answers “what should this deployment require?” A resolved plan answers “what exact declared requirements result from this profile and lock?” A future deployed/observed record answers “what actually ran?” The same desired ref can resolve differently over time, so every Phase 4D plan binds selected repository refs to full immutable commits.

The Phase 4D resolver:

- reject an unknown profile, component, gate, or vocabulary value;
- reject optional components not explicitly enabled and forbidden components that are enabled;
- resolves every selected repository/component version before producing a plan;
- require an immutable commit for every Git repository, including development refs in `lab`;
- reject `core` development refs;
- keep source/mirror selection outside correctness: the verified object identity is authoritative;
- reports logical secret and configuration requirements without reading their values;
- carries external readiness gates as required and unverified without treating them as malformed architecture.

## Composition and conflict rules

A desired deployment selects exactly one base profile. Optional selection can narrow exposure or add an allowed component, but cannot silently remove required components, enable forbidden components, weaken a backup requirement, or waive a readiness gate. Such a change requires review of the base profile contract.

Canonical configuration wins only when the competing values are equivalent. Canonical and compatibility values that conflict cause validation failure. A compatibility entry must name its current consumer, canonical replacement, justification, test, and retirement gate; absence of canonical production configuration never triggers an implicit legacy fallback.

## Read-only execution boundary

The reference JSON has no shell, container, service-manager, firewall, storage, or network procedures. JSON remains the declaration format. Phase 4D uses the declared `jsonschema` dependency for Draft 2020-12 validation and contains no process execution, network client, host inspection, or filesystem-output path.

No architecture artifact or resolved plan is an instruction to change a host.
