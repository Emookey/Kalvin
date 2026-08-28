# Hardware Requirement Decisions

Status: **CURRENT Phase 4F decision register; no undecided item is enforceable.**

The current development host and any one planned Core machine are examples, not universal minimums. Each item below requires explicit approval backed by compatibility or workload evidence.

## Exact supported Ubuntu releases

- **CURRENT EVIDENCE:** Reconstruction documentation selects Ubuntu Server, but no release compatibility matrix or lifecycle window is canonical.
- **RECOMMENDATION:** Test the Kalvin CLI and selected profile implementations against named supported releases, then publish either an explicit set or bounded compatibility range.
- **TRADEOFF:** A narrow set is easier to validate but ages quickly; a broad range reduces certainty and increases test cost.
- **SAFE DEFAULT:** Require Ubuntu family for Core/Storage and report release policy as decision pending.
- **DO NOT ENFORCE UNTIL APPROVED:** No exact release rejection is active.

## CPU minimum strategy

- **CURRENT EVIDENCE:** No canonical workload benchmark establishes a logical CPU minimum.
- **RECOMMENDATION:** Derive CPU sizing from selected application components, concurrency targets, and model-provider benchmarks.
- **TRADEOFF:** Too low degrades latency/concurrency; too high excludes valid low-demand deployments and raises cost.
- **SAFE DEFAULT:** Observe CPU capacity and report the threshold decision without blocking.
- **DO NOT ENFORCE UNTIL APPROVED:** No CPU count is a minimum.

## Memory minimum strategy

- **CURRENT EVIDENCE:** Kalvin has no approved application/model memory envelope.
- **RECOMMENDATION:** Combine measured Kal/Beepy working sets, selected model requirements, database/cache bounds, and operational margin.
- **TRADEOFF:** Too low risks pressure and failures; too high excludes valid provider-remote or lightweight deployments.
- **SAFE DEFAULT:** Observe total memory and leave the threshold decision pending.
- **DO NOT ENFORCE UNTIL APPROVED:** No byte value is mandatory.

## Core local storage minimum strategy

- **CURRENT EVIDENCE:** Core owns application state and bounded backup staging, but Storage owns long-term retention.
- **RECOMMENDATION:** Size from selected application working sets, growth horizon, migration workspace, rebuildable data policy, and maximum approved staging window.
- **TRADEOFF:** Too low risks interrupted operation/backups; too high can blur the Core-to-Storage authority boundary and waste capacity.
- **SAFE DEFAULT:** Keep Core capacity decision pending and preserve outbound backup responsibility.
- **DO NOT ENFORCE UNTIL APPROVED:** No universal Core capacity exists.

## Storage capacity and retention strategy

- **CURRENT EVIDENCE:** Storage owns protected backup payloads, retention, and restore-source availability; working-set size, retention values, replication, and safety margin are open.
- **RECOMMENDATION:** Define required capacity as protected working sets plus approved retention and replication overhead plus an explicit safety margin.
- **TRADEOFF:** Too low breaks retention/recovery objectives; too high increases cost and may obscure unbounded retention policy.
- **SAFE DEFAULT:** Require block/mount observability but keep capacity decision pending.
- **DO NOT ENFORCE UNTIL APPROVED:** Device presence is not capacity or health proof.

## Docker long-term policy

- **CURRENT EVIDENCE:** Phase 4E observes Docker capability, but Kalvin has no operational container deployment and the platform abstraction does not require Docker forever.
- **RECOMMENDATION:** Decide per profile after selecting an implementation; distinguish current implementation requirement from permanent platform invariant.
- **TRADEOFF:** Mandating Docker simplifies one implementation but constrains portability; remaining flexible increases orchestration/testing scope.
- **SAFE DEFAULT:** Docker is optional in Lab and decision pending in Core/Storage.
- **DO NOT ENFORCE UNTIL APPROVED:** Docker absence does not currently block Core or Storage.

## systemd long-term policy

- **CURRENT EVIDENCE:** Ubuntu Server orientation and future service integration favor systemd, but no Kalvin systemd units or operational service implementation exist.
- **RECOMMENDATION:** Keep systemd recommended while the service/orchestration design evaluates whether alternatives are supported.
- **TRADEOFF:** Requiring it narrows/test-hardens the host contract; permitting alternatives increases implementation complexity.
- **SAFE DEFAULT:** Report absence as warning drift only.
- **DO NOT ENFORCE UNTIL APPROVED:** systemd is not a blocking requirement.

## GPU and model-runtime strategy

- **CURRENT EVIDENCE:** `model-runtime` is provider-neutral; provider/model-specific CPU, RAM, GPU, and VRAM needs are not canonical Kalvin constants.
- **RECOMMENDATION:** Let the immutable implementation/model selection contribute validated component constraints to a future sizing contract.
- **TRADEOFF:** Static platform numbers are simple but inaccurate; component-derived constraints are accurate but need provider/model metadata and tests.
- **SAFE DEFAULT:** Report model compute as decision pending only when `model-runtime` is selected; never require it on Storage.
- **DO NOT ENFORCE UNTIL APPROVED:** No GPU, VRAM, CPU, or memory model threshold exists.
