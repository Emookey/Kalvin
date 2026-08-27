# GoodWill Migration and Legacy Compatibility

Status: **HISTORICAL source boundary and TARGET compatibility policy; no migration has been executed.**

## Historical relationship

GoodWill records the earlier monolithic AI Workspace Lab. Kalvin is its architectural successor at the platform layer, but not its renamed repository or continuation of Git history. Kal and Beepy are separate application successors for their own domains.

This repository was initialized with new independent history. It contains no GoodWill commit, Git object, script, configuration example, mock dataset, or verbatim document.

## Phase 4A disposition summary

The frozen GoodWill reference contained 130 tracked paths. Phase 4A classified them as:

| Disposition | Count |
| --- | ---: |
| Migrate concept/ownership to Kalvin | 6 |
| Migrate concept/ownership to Kal | 8 |
| Migrate concept/ownership to Beepy | 0 |
| Keep in GoodWill history | 90 |
| Rewrite as Kalvin documentation | 14 |
| Retire or supersede | 12 |
| Needs path-specific human decision | 0 |

These counts are migration evidence, not permission to copy. Phase 4A approved no GoodWill content for verbatim reuse. Platform concepts in this candidate were rewritten around the new boundaries. The 61-file legacy mock corpus remains in GoodWill history and is not platform orchestration data.

## Terminology

| Class | Names | Use |
| --- | --- | --- |
| Canonical current | Kalvin, Kal, Beepy, Core, Storage | New documentation, profiles, services, examples, and future identifiers |
| Legacy compatibility | GoodWill, Odysseus, MBC Intelligence, old paths/resources | Only where a proven current consumer or safe data transition requires the exact identifier |
| Historical provenance | Old repository names, commits, backup labels, paths, and dated evidence | Preserve accurately in migration/history context; never rewrite as current state |

## Compatibility contract

Compatibility is not a second production configuration system. A future compatibility entry must record:

- canonical and legacy identifiers;
- identifier kind and owning repository;
- current consumer evidence and last verified revision;
- one-way legacy-to-canonical interpretation;
- fail-closed behavior when values conflict or canonical configuration is incomplete;
- migration and rollback procedure;
- tests, warning behavior, and retirement condition.

Do not mechanically rename persisted database identifiers, container resources, volume names, backup labels, audit evidence, or old absolute paths. Do not create new legacy-named identifiers merely to resemble the old host.

## Path transitions

New deployments use the canonical host namespace documented in [Conceptual Host Layout](../architecture/host-layout.md). Legacy absolute paths may appear in a dated migration record or an explicit temporary adapter. An adapter requires a current consumer, must not become a silent fallback, and is removed after its retirement gate passes.

## GoodWill future disposition

The expected sequence is:

1. Establish reviewed canonical Kal, Beepy, and Kalvin successors.
2. Prove the required migration and recovery paths.
3. Optionally add a reviewed superseded notice to GoodWill's README.
4. Optionally archive the GoodWill repository on GitHub with separate approval.
5. Preserve all GoodWill Git history and provenance throughout.

No GoodWill file, ref, remote, history, or GitHub state is modified by this architecture phase.

## Licensing boundary

GoodWill has no tracked license file, Beepy has no tracked license file, and Kal declares AGPL-3.0-or-later. Those facts do not select terms for Kalvin or authorize copying legacy content.

**LICENSE POLICY REQUIRES HUMAN DECISION.** Kalvin does not inherit Kal's license by deployment relationship, and this architecture adds no `LICENSE` file.
