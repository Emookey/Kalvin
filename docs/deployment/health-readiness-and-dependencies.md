# Dependencies, Health, and Readiness

Status: **CURRENT semantic contract; probes and aggregators are PLANNED.**

## Health and readiness

**Health** means a process or service can perform its own bounded function. **Readiness** means it is safe and sufficiently complete for the intended profile use. A responding Kal HTTP process may be healthy while Core remains not ready because authoritative storage, migrations, RAG reconciliation, backup preconditions, or authorization checks are incomplete.

Every component declares a health gate and zero or more readiness gates. Every profile declares required aggregate gates. A future evaluator returns at least `PASS`, `FAIL`, `DEGRADED`, or `NOT_APPLICABLE` for each selected gate. Required `FAIL` or unresolved status makes the profile not ready. Optional-integration degradation is visible but does not fail unrelated documented modes.

Exposure is a post-readiness action. Health alone never enables LAN, overlay, or public exposure.

## Profile aggregation

- `lab` requires contract validity, immutable repository resolution, complete selected-component inputs, bounded monitoring, and explicit exposure policy. Lab success never proves production recovery or authorization.
- `core` additionally requires application-owned migrations/integrity, authoritative storage, outbound backup readiness, identity separation, derived reconciliation, application authorization, and durable Kal RAG status.
- `storage` requires backup repository integrity, retention policy, restore authorization controls, monitoring, and Storage-specific exposure policy. It does not require application health.

## Kal RAG hard gate

`kal.rag-status-durable` is an external application readiness gate owned by Kal. Before Core may be declared production-ready, Kal must demonstrate:

- durable indexing status tied to authoritative document identity/content;
- status persistence across process restart;
- reconciliation behavior for partial failure, restore, and stale derived indexes.

Kalvin consumes a future safe readiness interface and records the result. It does not add a second database, patch Kal's schema, or promote Chroma to authority.

## Failure behavior

Unknown components/gates, unresolved versions, missing required configuration or secrets, migration failures, compatibility conflicts, and readiness failures are fail-closed. A risky update is blocked when its profile requires a verified backup precondition and that evidence is absent. Failure leaves the deployment degraded/not-ready and does not enable new exposure.
