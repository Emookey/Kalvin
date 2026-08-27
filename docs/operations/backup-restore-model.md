# Backup and Restore Model

Status: **TARGET policy; no backup or restore implementation exists.**

## Principles

1. Git is the reconstruction recipe, not the runtime-data backup.
2. Backups are selected by authority and recovery need, not by copying every directory that exists.
3. Applications define how their state is captured consistently and migrated.
4. Kalvin coordinates schedule, destination, verification, retention, restore order, and evidence.
5. The Core host sends backups outward; it is not automatically the master backup store.
6. The Storage role protects backup repositories but does not run restored application data by default.
7. A backup is not trusted until integrity checks and a representative restore have succeeded.

## Default treatment by state class

| State class | Backup treatment | Restore treatment |
| --- | --- | --- |
| Kal SQLite and authoritative documents/uploads | Required, consistent, protected off-host | Restore before migrations and vector reconciliation |
| Beepy business database and file-backed authoritative objects | Required through Beepy's consistency contract | Restore as one application-owned set; run Beepy migrations/integrity checks |
| Kal Chroma/vector indexes | Optional warm snapshot, never sole recovery source | Prefer reconcile/rebuild from authoritative Kal data |
| Model and package caches | Excluded when pinned and reproducible | Re-fetch from reviewed manifests |
| Monitoring or optional UI state | Explicit per-component decision | Restore only when the component is selected and its state is required |
| Rendered configuration | Reconstruct from Git templates plus approved external inventory | Render for the target host; do not restore stale machine identity blindly |
| Secrets and recovery keys | Separate encrypted recovery policy | Inject out of band with least privilege and audit |
| Temporary runtime state | Excluded | Recreate at service start |

The machine vocabulary calls these policies:

- `REQUIRED` — must be captured through a consistent owner-approved method and included in recovery proof;
- `REBUILDABLE` — useful as an accelerator but never required to reconstruct truth;
- `EXCLUDED` — must not be treated or restored as authoritative backup data.

Secrets use a separate protected recovery policy even when a component's state entry is `EXCLUDED` from normal backup payloads.

## Core-to-Storage boundary

Core participates in an outbound, mutually authenticated, narrowly scoped backup protocol to Storage. The backup-client identity can submit only approved backup sets and metadata; it is separate from human, application, platform-administration, and restore identities. Storage needs no Kal/Beepy application-admin credential and gains no Kal agent/tool privilege.

Storage owns repository integrity, retention, expiry, protected copies, and restore-source availability. A restore requires explicit authorization through a separate path and does not turn the Storage host into application compute. Product, transport, encryption implementation, schedules, and retention values remain open for Phase 4D or later review.

## Database consistency contract

An active database directory is never copied arbitrarily. Each application must publish an approved consistency method—such as a database-native dump, application export, coordinated snapshot, or bounded quiesce hook—and the backup record identifies which method and boundary were used. Kalvin may sequence that interface but does not inspect schemas or assume Kal and Beepy share a mechanism.

## Backup-set contract

A future backup manifest should identify:

- source application and revision;
- dataset class and authority;
- consistency mechanism and snapshot boundary;
- included and explicitly excluded paths/data classes;
- encryption and access policy without embedding key material;
- destination role and source host's stable logical identity;
- integrity metadata, creation time, retention class, and verification status;
- application migration compatibility and restore prerequisites;
- optional derived/cache payloads clearly separated from authoritative content.

Kalvin must not query application databases to invent this contract. Kal and Beepy publish their required snapshot and restore interfaces.

## Restore workflow

1. Choose a verified backup set and compatible pinned revisions.
2. Preserve the current target state as a rollback source when applicable.
3. Provision empty, correctly owned target locations.
4. Inject recovery-required secrets separately.
5. Invoke the application-owned restore mechanism for authoritative data.
6. Run application-owned migrations and integrity checks.
7. Rebuild or reconcile derived state; do not let a cache supersede restored authority.
8. Start services behind intended exposure controls.
9. Validate authentication, authorization, domain isolation, scoped contracts, and readiness.
10. Record results and retain the rollback source until acceptance.

## Failure boundaries

- A partial or stale vector index is a degraded derived state, not a reason to discard authoritative documents.
- A local backup on the same application host is not sufficient disaster recovery.
- RAID, snapshots, and replication solve different risks; none alone proves recoverability.
- A raw copy of a live database directory is not assumed consistent.
- A container volume name is an implementation detail, not an authority classification.
- Missing canonical configuration must fail closed rather than silently choosing a legacy production path.

Operational tools, schedules, retention values, encryption mechanisms, and storage implementations are deferred to later phases.
