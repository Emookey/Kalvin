# Remediation Planning and Approval Contract

Status: **CURRENT Phase 4G planning-only architecture; execution and rollback are not implemented.**

## Boundary

Kalvin can now turn eligible Phase 4F drift findings into a deterministic review document. The implemented boundary is:

```text
OBSERVE  ->  COMPARE  ->  PLAN  ->  MODEL APPROVAL CONTRACT
allowed      allowed      allowed    model only

EXECUTE  ->  ROLL BACK
absent       absent
```

Generating, viewing, resolving, or comparing a plan never implies authorization. Phase 4G does not persist approvals, inventory, or plans; collect credentials; change a host; implement rollback; or expose an arbitrary process runner. Every plan and action says `execution_available: false`.

The CLI surface adds only:

```text
python3 -m kalvin host plan --profile core --lock LOCK.json --format text
python3 -m kalvin host plan --profile core --lock LOCK.json --format json
```

This command reuses the existing bounded local inspector and drift comparison in memory. The first live-host planning smoke test is reserved for a human operator. Automated tests inject synthetic observed state and do not inspect the machine.

## Finding classification and minimization

The planner processes findings in stable requirement-ID order and fails closed when blocking drift has no approved planning rule.

| Drift result | Planning result | Host mutation proposal |
| --- | --- | --- |
| `SATISFIED` | `NO_REMEDIATION` | No |
| `NOT_APPLICABLE` | `NO_REMEDIATION` | No |
| `DECISION_PENDING` | `HUMAN_POLICY_DECISION_REQUIRED` | No |
| `UNKNOWN` | `INVESTIGATION_REQUIRED` | No |
| blocking, required `UNSATISFIED` with an action rule | `REMEDIATION_PROPOSED` | Declarative proposal only |
| blocking, required `UNSATISFIED` with a decision rule | `HUMAN_POLICY_DECISION_REQUIRED` | No |
| blocking, required `UNSATISFIED` without a rule | `BLOCKED_NO_RULE` | No |

Recommended or optional findings do not silently become mutation work. A drift-free host produces zero actions even when policy decisions or external readiness gates remain open.

`UNKNOWN` means evidence is insufficient. The investigation record names the missing observation status and retains the existing safe guidance. It does not elevate probes or treat absence as failure. An observation that crosses a future trust boundary would require separate approval; Phase 4G does not cross one.

`DECISION_PENDING` means governance or architecture evidence is incomplete. For example, an unapproved CPU minimum produces a sizing-policy decision, not a CPU upgrade, and the undecided Core/Storage Docker policy produces a policy decision, not a runtime installation proposal.

## Versioned contracts

| Contract | Version | Artifact |
| --- | --- | --- |
| remediation planning policy/action catalog | `1.0.0` | `manifests/remediation-actions.json` |
| action catalog schema | `1.0.0` | `schemas/remediation-action-catalog.schema.json` |
| remediation plan schema/plan | `1.0.0` | `schemas/remediation-plan.schema.json` |
| model approval record schema | `1.0.0` | `schemas/approval-record.schema.json` |

The catalog is non-operational and explicitly declares execution unavailable. It contains action classes and review expectations, never executable recipes. Fields with executable meaning—including `command`, `shell`, `argv`, and `script`—are rejected.

## Action catalog

The initial catalog defines eleven declarative classes:

| Action class | Domain | Default risk | Future automatic consideration |
| --- | --- | --- | --- |
| `PACKAGE_OR_RUNTIME_PROVISION` | host runtime/tooling | `MODERATE` | separate future policy required |
| `SERVICE_STATE_CHANGE` | service | `HIGH` | separate future policy required |
| `CONFIGURATION_CHANGE` | configuration | `HIGH` | separate future policy required |
| `FILESYSTEM_OR_MOUNT_CHANGE` | filesystem/storage | `HIGH` | never |
| `STORAGE_CAPACITY_CHANGE` | storage/backup | `CRITICAL` | never |
| `NETWORK_CONFIGURATION_CHANGE` | network/security boundary | `HIGH` | never |
| `APPLICATION_MIGRATION` | application/backup | `CRITICAL` | never |
| `BACKUP_PREPARATION` | backup authority | `MODERATE` | never |
| `SECRET_OR_CONFIGURATION_RESOLUTION` | external security/configuration boundary | `CRITICAL` | never |
| `REPOSITORY_OR_VERSION_CHANGE` | version/application/configuration | `HIGH` | separate future policy required |
| `MANUAL_ARCHITECTURE_DECISION` | governance | `LOW` | never; non-mutating |

The catalog does not make any action executable. “Separate future policy required” is not approval and grants no present or future authority. Destructive formatting, destructive partition changes, authoritative-data deletion, backup-repository deletion, security-control disablement, destructive database reset, externally coordinated credential rotation, and arbitrary process execution are not automatic action classes and have no bypass.

Application migrations remain owned and validated by their application. Kalvin may someday sequence an approved application contract but must not replace it with platform-authored data edits.

## Risk model

Risk is based on potential change impact, not operator confidence:

- `LOW`: non-mutating investigation or decision work;
- `MODERATE`: bounded mutation with compatibility or availability impact;
- `HIGH`: service, state, connectivity, recovery, or security-boundary disruption is credible;
- `CRITICAL`: major state loss, management loss, or external recovery may be required.

This is an ordinal vocabulary, not a quantitative score or probability estimate. Low risk never implies silent mutation. Every host mutation remains approval-required until a separately reviewed future policy says otherwise.

## Scope model

Actions declare one or more affected scopes: `HOST_TOOLING`, `HOST_RUNTIME`, `SERVICE`, `NETWORK`, `FILESYSTEM`, `STORAGE`, `APPLICATION`, `CONFIGURATION`, `SECRET_REFERENCE`, `BACKUP`, and `SECURITY_BOUNDARY`. Multiple scopes make cross-boundary effects visible; they do not grant access to those domains.

Storage profile planning cannot include an application migration, repository/version application action, or `APPLICATION` scope. Storage remains concerned with retention infrastructure, storage/filesystem capability, backup target readiness, and monitoring. It does not inherit Kal, Beepy, or model-runtime compute work.

## Approval classes and states

Approval classes are:

- `NO_APPROVAL_NEEDED` for non-mutating work within an already approved observation boundary;
- `OPERATOR_APPROVAL` for an explicitly bounded host change;
- `ELEVATED_OPERATOR_APPROVAL` for privileged or high-impact host scope;
- `MANUAL_EXTERNAL_APPROVAL` for an application, storage, backup, or security authority;
- `PROHIBITED_AUTOMATICALLY` for work that no automatic policy may select.

The state vocabulary is `NOT_REQUESTED`, `REQUIRED`, `APPROVED`, `DENIED`, `EXPIRED`, `STALE`, and `NOT_APPLICABLE`. Phase 4G plans use `REQUIRED` for every mutation proposal and never manufacture `APPROVED`.

Multiple required approval classes are supported. The contract does not impose two-person approval universally and does not implement identity infrastructure. Governance still must decide which destructive or security-boundary classes require multiple independent authorities.

## Approval record contract

The approval-record schema is model-only. A record contains:

- schema and planning-policy versions;
- the exact remediation-plan fingerprint;
- approval class and generic approver role type;
- approve/deny decision and explicit state;
- approved scope and constraints;
- validity mode and optional expiry concept;
- a reason; and
- `synthetic_model_only: true` in Phase 4G.

It contains no password, token, key, session, credential, or real person/host identity. Phase 4G does not persist real approvals. The synthetic contract can represent an expiry boundary, but no wall-clock authority or identity verification is implemented.

An operator being logged in is not approval. Approval of another plan is not approval. Plan generation is not approval. Approval will eventually have to bind to one fingerprint and satisfy every action's required class and constraints; that future authorization evaluator is outside Phase 4G.

## Deterministic identity and stale protection

Stable JSON uses UTF-8, sorted object keys, compact separators, and stable list ordering. No wall-clock timestamp is part of plan content. The plan fingerprint is SHA-256 over a canonical payload containing:

- schema and plan versions;
- planning-policy version;
- selected profile;
- requirement-policy version;
- sanitized resolved-plan identity;
- sanitized drift identity;
- finding classifications;
- proposed action content and action-definition fingerprints;
- decisions and investigations;
- blocking conditions; and
- external readiness references.

The resolved identity covers selected components, immutable repository/implementation locks, dependency order, configuration and safe secret-reference IDs, state declarations, readiness gates, and unresolved external blockers. The drift identity covers stable relevant finding content, including result and sanitized observed capability values. Action-definition fingerprints bind the selected catalog class and finding rule.

The plan stores only these fingerprints, finding classifications, safe reference IDs, and review content. It does not store a raw host snapshot or host identity. Before hashing, the planner rejects executable fields, credential-like values, private addresses, MACs, and private-identity fields. It never hashes secret values.

Limitation: the sanitized drift fingerprint proves equality of the relevant published capability evidence, not the physical identity of a machine. A future executor must re-resolve, re-inspect through the approved bounded observation path, rerun drift, regenerate or verify the canonical plan payload, and reject a mismatch. Phase 4G cannot safely bind a plan to a private hostname, hardware serial, MAC, or address and intentionally does not try.

An approval is `STALE` if its plan fingerprint or planning-policy version differs. Material changes to requirement policy, planning policy, resolved deployment, relevant drift, or action definition produce a new fingerprint. Approval does not carry forward. A future executor must also make validity/expiry and single-use decisions fail closed.

## Preconditions and backup-first policy

Each proposal carries explicit prerequisites with state `SATISFIED`, `UNVERIFIED`, `UNSATISFIED`, or `NOT_APPLICABLE`. Phase 4G marks only what the available synthetic planning evidence proves. Operator approval, rollback capability, maintenance windows, package-source trust, external configuration, backup readiness, and recovery access are generally `UNVERIFIED`.

Changes affecting configuration, repositories/versions, applications, filesystems, or storage declare `backup.pre-update-verified` where state or recovery risk is meaningful. It starts `UNVERIFIED`; Kalvin does not infer backup success or initiate a backup. A future backup verifier must identify the authority, protected set, recovery source, and usable restore evidence without exposing protected data.

Any `UNSATISFIED` prerequisite forbids execution. Any required `UNVERIFIED` prerequisite also forbids execution until a future reviewed verifier establishes it. Phase 4G has no precondition executor.

## Validation, rollback, and failure contracts

Every mutation proposal states how a future phase would prove success. Existing safe concepts are preferred: bounded inspection, fresh drift, required service-state observation, immutable version re-resolution, and existing application-owned health/readiness gates. External checks remain `UNVERIFIED`; the planner does not invent application checks.

Rollback classes are:

- `NOT_REQUIRED` — no persistent reversal expected, but validation/reassessment still applies;
- `DEFINED_REQUIRED` — a reviewed reversal or version restore must exist;
- `BACKUP_REQUIRED` — a verified recovery source is mandatory;
- `MANUAL_RECOVERY_REQUIRED` — documented human recovery is required;
- `NO_SAFE_AUTOMATIC_ROLLBACK` — no automatic rollback is accepted.

Theoretical reversibility is not treated as evidence. Network changes require out-of-band recovery and a defined recovery path. Storage layout/capacity work declares no safe automatic rollback. Phase 4G implements no rollback executor.

Failure behavior is one of `STOP`, `ROLLBACK_REQUIRED`, `MANUAL_RECOVERY_REQUIRED`, or `REASSESS_REQUIRED`. These are expectations only. No failure handler exists.

## Multi-action graph

Actions have stable declarative IDs and `depends_on` IDs. Dependency references must exist, and cycles are rejected. This models ordering without encoding a process invocation. A future executor must separately validate action allowlisting, state freshness, and transaction behavior; a valid graph is not authorization.

## Application and external readiness boundary

Host remediation, application readiness, and business workflow remain separate:

- `kal.rag-status-durable` stays `REQUIRED_EXTERNAL_UNVERIFIED` and belongs to Kal;
- Beepy health and business authorization stay application/external responsibilities;
- configuration and secret-reference resolution remain external readiness, not Linux package drift;
- application authorization is not established by changing host software.

The plan carries external readiness gate IDs and states under `EXTERNAL_NOT_HOST_REMEDIATION`. It creates no host actions for those gates unless a future explicitly defined platform workflow is reviewed.

## Network, service, package, storage, and secret boundaries

- Network changes are high risk, require explicit elevated operator approval, and require management-independent recovery. Plans contain no addresses or network instructions.
- Service lifecycle changes are mutations. Plans describe the class but cannot start, stop, restart, or enable a service.
- Package/runtime provisioning is mutation. Plans name the approved capability objective but contain no package-manager or installer invocation. Package-source trust remains a precondition.
- Filesystem and storage mutations are high/critical risk. Destructive storage operations are never automatic and require independent backup/manual recovery evidence.
- Plans may reference safe secret requirement/provider IDs already present in architecture but never resolve or store secret values.

## Future execution gate

Host mutation capability remains forbidden until a separately scoped phase designs, reviews, tests, and receives explicit approval for all of the following:

1. a dedicated execution engine with no arbitrary process interface;
2. a strict, versioned action allowlist and typed parameters;
3. exact approval binding and authorization evaluation;
4. a reviewed privilege model and least-privilege service identity inaccessible to ordinary applications/agents;
5. implemented and tested rollback paths;
6. backup verification and recovery-source authority;
7. transaction, journal, and audit semantics;
8. stale-state re-resolution, reinspection, drift rerun, and fingerprint rejection;
9. explicit failure handling and fail-closed dependency behavior;
10. emergency stop and operator recovery procedures;
11. protection against network/management-path loss;
12. secret-provider handling that never enters plans or logs;
13. isolated integration tests for every allowed action;
14. profile-specific human smoke tests; and
15. one-service-at-a-time operational review and rollback proof.

Phase 4G supplies none of those execution capabilities. A future phase must not reinterpret this catalog as an executable recipe.

## Human decisions still open

Phase 4F decisions remain unresolved:

- exact supported Ubuntu release range;
- workload-derived CPU sizing;
- workload-derived memory sizing;
- Core local working-set/staging capacity;
- Storage retention/capacity/replication policy;
- independent Core and Storage container-runtime policy;
- long-term service-manager/systemd policy; and
- provider/model-derived CPU, memory, GPU, and VRAM sizing.

Phase 4G also introduces governance decisions that remain open:

- final approval-class authority definitions;
- which narrowly bounded future actions, if any, may ever be automatic;
- high-risk approval validity and expiry rules;
- destructive/security actions requiring external or multiple approvals;
- minimum rollback evidence by action class;
- maintenance-window rules;
- backup verification authority and freshness; and
- acceptable out-of-band recovery proof for network changes.

These decisions require human review. The conservative defaults do not resolve them.
