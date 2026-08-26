# Portability and Readiness

Status: **TARGET reconstruction contract and CURRENT readiness dependency; no installer or validator exists.**

## Reconstruction sequence

The intended sequence is:

1. Install a fresh supported Ubuntu Server release.
2. Verify supported hardware and install pinned platform prerequisites.
3. Obtain the canonical Kalvin, Kal, and Beepy repositories independently at reviewed revisions.
4. Select and validate an explicit `lab`, `core`, or `storage` profile.
5. Render machine-local configuration from public templates and external inventory.
6. Inject secrets through an approved out-of-band mechanism.
7. Provision service identities and state locations without making code checkouts writable.
8. Restore only approved authoritative data using application-consistent procedures.
9. Run migrations supplied by Kal and Beepy in their documented order.
10. Reconcile or rebuild derived indexes and reproducible caches.
11. Start selected services according to declared dependencies.
12. Run liveness, readiness, data-integrity, authorization, contract, backup, and boundary checks.
13. Record the exact manifest, restore source, results, and rollback reference.

## Portability exclusions

Reconstruction must not require:

- an old T420 image or a clone of any legacy system disk;
- GoodWill, Odysseus, or MBC Intelligence absolute host paths;
- committed IP addresses, hostnames, SSH targets, or secrets;
- copied container volumes treated as unquestioned source-of-truth;
- one model provider, one GPU vendor, or one deployment mechanism;
- a monorepo or Git submodules;
- application source or runtime data embedded in Kalvin.

## Readiness layers

| Layer | Minimum evidence |
| --- | --- |
| Repository | Pinned revisions, verified Git objects, reviewed manifests, no secret/runtime content |
| Host | Supported prerequisites, expected role, service identities, state ownership, storage availability |
| Service | Bounded liveness plus dependency-aware readiness; no sensitive output |
| Application | Owner-supplied migrations and integrity checks pass |
| Security | Authentication, authorization, data isolation, exposure policy, and scoped contract checks pass |
| Recovery | Recent verified authoritative backup and a documented restore proof exist |
| Derived state | Reconciliation/rebuild completes from authoritative data and reports durable status |
| Compatibility | Every enabled alias has consumer evidence, conflict behavior, tests, and retirement criteria |

An open port or successful HTTP response is only liveness evidence. It does not satisfy application, security, recovery, or data-integrity readiness.

## Kal RAG-status Core interlock

**CURRENT dependency:** canonical Kal records RAG indexing status in process-local memory. A process restart can therefore lose the reported pending/indexed/degraded/removed state even though authoritative SQLite documents and vector state persist independently.

**Required Kal milestone:** before `core` can be called production-ready, Kal must provide durable indexing status tied to authoritative document identity and content, plus restart, partial-failure, restore, stale-index, and reconciliation validation. The durable record should be able to distinguish what was authoritative, what was indexed, and whether retry or rebuild remains necessary.

This is a Kal application change. Kalvin tracks it as a hard deployment-readiness dependency and consumes a future safe readiness signal; it must not patch Kal's database or implement a parallel status authority.

## Core promotion gate

In addition to the RAG interlock, a future Core proof must show:

- independent pinned repositories and repeatable configuration rendering;
- secrets injected with intended ownership and absent from Git/logs;
- Kal and Beepy migrations and integrity checks passing;
- application authorization and the scoped Kal–Beepy contract passing;
- authoritative backup delivery and recoverability evidence;
- derived-state rebuild/reconciliation from restored authority;
- no undeclared legacy path or machine-identity dependency;
- only profile-approved services exposed;
- a retained, tested rollback source.

Phase 4B performs none of these operational actions.
