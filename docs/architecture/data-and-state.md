# Data and State Architecture

Status: **TARGET boundary; no data has been moved or deployed.**

## Five data domains

| Domain | Application authority | Kalvin responsibility | Required boundary |
| --- | --- | --- | --- |
| 1. PRIVATE USER | Kal owns user-scoped application records and retrieval authorization | Isolate storage, credentials, backups, and service access | No platform-wide or Beepy-readable shared directory; user authorization remains in Kal |
| 2. SHARED MSP KNOWLEDGE | Kal owns publication and retrieval authorization | Isolate and protect the deployment/storage path | Shared read scope does not imply global write, delete, archive, or administration scope |
| 3. BEEPY BUSINESS DATA | Beepy owns business state and business authorization | Provide dedicated database/storage/secret boundaries and backup coordination | No general Kal or platform mount; only the scoped application contract may cross the boundary |
| 4. TEST/HISTORICAL | The owning test repository or preserved GoodWill history | Keep separate from production mounts and backup sets | Synthetic or historical content is never promoted automatically into production authority |
| 5. SYSTEM/PLATFORM | Kalvin and narrowly scoped infrastructure services | Own non-application deployment metadata, health state, and backup catalogs | No application content and no general application access to host-control state |

These domains are conceptual and security-relevant. They do not map to one shared `data/` directory. A host may contain several domains while preserving separate service identities, paths, access controls, backup sets, and restore procedures.

## State classes

### Authoritative application state

- Kal SQLite records and raw/approved Library documents are authoritative for Kal.
- Beepy business database records and application-owned file objects are authoritative for Beepy.
- Any key material required to interpret encrypted authoritative state is recovery-critical secret material, but it remains outside Git and outside ordinary backup logs.
- A third-party component's state becomes authoritative only for that component when operators deliberately depend on it and document the decision.

Authoritative state requires application-consistent snapshots, off-host protection, integrity verification, retention policy, and tested restoration.

### Derived state

Kal Chroma collections, vector indexes, and embeddings that can be reproduced from authoritative documents are derived. They may be snapshotted as a recovery accelerator, but they cannot be the only recovery source and cannot override restored authority.

Beepy may store computed vectors inside its authoritative database. Kalvin must follow Beepy's restore contract rather than partially removing database content based on a platform assumption that a field is derived.

### Reproducible caches

Model downloads, package caches, embedding-model caches, thumbnails, and temporary extractions are normally excluded from minimum disaster-recovery sets when a pinned manifest and accessible source can reproduce them. A locally created or otherwise irreplaceable model artifact must be reclassified before relying on this rule.

### Configuration and secrets

Public templates and schemas belong in Git. Rendered host configuration does not. Secrets, tokens, passwords, private keys, decryption material, and integration credentials are injected externally and exposed only to the consuming service.

### Temporary runtime state

Sockets, PID files, locks, readiness probes, transient working files, and other process-lifetime state are non-authoritative. They are recreated at service start and are not restored as application truth.

## Ownership consequences

Kalvin coordinates state placement and recovery order but does not inspect business tables or duplicate application migrations. Kal and Beepy define consistency requirements, data formats, migrations, and integrity checks. Infrastructure permissions are defense in depth and never replace application authorization.

## Restore and reconciliation order

1. Select pinned platform and application revisions.
2. Render approved configuration and inject required secrets externally.
3. Restore Kal authoritative state through Kal's approved mechanism.
4. Restore Beepy database and file objects through Beepy's approved mechanism.
5. Restore separately classified third-party state when required.
6. Run migrations supplied by each owning application.
7. Reconcile or rebuild vector indexes and other derived state.
8. Recreate caches from pinned sources where practical.
9. Validate data integrity, owner isolation, the Kal–Beepy contract, health, and readiness.

No restore implementation exists in this bootstrap.
