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

| Class | Backup expectation | Restore/rebuild | Acceptable loss | Owner | Examples |
| --- | --- | --- | --- | --- | --- |
| `AUTHORITATIVE` | `REQUIRED`; application-consistent and protected off-host | Restore before migration and derived reconciliation | Only within an explicitly accepted recovery point objective | Owning application or Storage recovery service | Kal SQLite/raw documents; Beepy business database/files; protected backup payloads |
| `DERIVED` | `REBUILDABLE`; optional accelerator only | Recreate/reconcile from authority and verify | Entire copy when source and recipe remain available | Component that derives it | Kal Chroma/vector index; reproducible model/package caches |
| `EPHEMERAL` | `EXCLUDED` | Recreate at process/service start | Entire process-lifetime copy | Runtime service | sockets, PID files, locks, temporary work |
| `CONFIGURATION` | Reconstruct from reviewed declarations plus approved host inventory; not a substitute for authoritative backup | Render for the target host and validate | Host-local copy may be replaced when source inputs survive | Platform plus consuming service | rendered non-secret settings, retention policy |
| `SECRET` | Separate protected recovery policy; never ordinary Git/log backup | Inject from an approved secret provider | Determined by credential recovery/rotation policy | Credential owner and consuming service | tokens, passwords, keys, recovery material |
| `LOG` | `EXCLUDED` from authoritative sets unless a separate evidence policy requires bounded retention | Do not restore as application truth | Defined by audit/operations policy | Emitting service / log operator | service and deployment logs |

`REQUIRED`, `REBUILDABLE`, and `EXCLUDED` are backup-policy classes, not synonyms for state classes. A state declaration must choose both.

Kal Chroma collections, vector indexes, and embeddings remain `DERIVED`. A warm snapshot may accelerate recovery, but it cannot be the only recovery source or override restored authority. Model downloads and caches are derived only when pinned information and an accessible source can reproduce them; an irreplaceable local artifact must be reclassified before use.

Beepy may store computed vectors inside its authoritative database. Kalvin follows Beepy's restore contract rather than partially deleting database content based on a platform assumption.

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

No restore implementation exists in Phase 4C.
