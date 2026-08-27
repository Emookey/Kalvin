# Declarative Deployment Model

Status: **CURRENT Phase 4C architecture contract; non-operational.**

## Layers

Kalvin separates five kinds of input and evidence:

1. **Catalogs and vocabularies** define valid components, repositories, state/backup classes, exposure classes, privilege classes, dependency kinds, readiness gates, and compatibility metadata.
2. **Profiles** select a primary host role and declare required, optional, and forbidden components plus backup, exposure, repository, and readiness policy.
3. **Desired deployment manifests** record operator intent: profile, human-friendly refs, selected optional components, logical host-configuration reference, secret references, and approved compatibility entries.
4. **Resolution inputs** bind desired refs to immutable commits or immutable implementation versions, combine repository-safe defaults with profile and host-local configuration, and resolve external secret references without copying secret values into Git.
5. **Resolved deployment records** report the exact revisions and component versions that ran, configuration revision, application-exposed migration state, readiness results, host role, and deployment time. They contain references and results, never secret values.

Catalogs and profiles are committed public contracts. Host-local configuration, provider bindings, secret values, authoritative backup payloads, and ordinary resolved records are host state outside Git. A deliberately sanitized record may be retained as review evidence, but it is never a substitute for current host state.

## Desired versus resolved state

A desired manifest answers “what should this host run?” A resolved record answers “what exact state was observed after deployment?” The same desired ref can resolve differently over time, so production validation always requires an immutable resolution before host mutation.

The future resolver must:

- reject an unknown profile, component, gate, or vocabulary value;
- reject optional components not explicitly enabled and forbidden components that are enabled;
- resolve every selected repository/component version before mutation;
- require an immutable commit for every Git repository, including development refs in `lab`;
- reject `core` development refs;
- keep source/mirror selection outside correctness: the verified object identity is authoritative;
- reject unresolved secret references and missing required configuration;
- calculate profile readiness from required gates and record failures without enabling exposure.

## Composition and conflict rules

A desired deployment selects exactly one base profile. Optional selection can narrow exposure or add an allowed component, but cannot silently remove required components, enable forbidden components, weaken a backup requirement, or waive a readiness gate. Such a change requires review of the base profile contract.

Canonical configuration wins only when the competing values are equivalent. Canonical and compatibility values that conflict cause validation failure. A compatibility entry must name its current consumer, canonical replacement, justification, test, and retirement gate; absence of canonical production configuration never triggers an implicit legacy fallback.

## Non-operational guarantee

The reference JSON has no shell, container, service-manager, firewall, storage, or network procedures. JSON was selected instead of YAML for this phase so the standard-library validator can parse every declaration deterministically without adding a package dependency. A later renderer may accept another human-edited format only if it preserves these contracts and validates before mutation.

No architecture artifact is an instruction to change a host.
