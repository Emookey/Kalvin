# Repository Map and Roadmap

Status: **CURRENT Phase 4G remediation planning/approval contract and PLANNED later implementation sequence.**

## Current repository map

```text
.gitignore
AGENTS.md
CONTRIBUTING.md
README.md
LICENSE
pyproject.toml
deploy/
  profiles/                     # lab/core/storage intent; non-operational JSON
docs/
  architecture/                 # charter, ownership, data, and host namespace
  deployment/                   # declarative lifecycle and security contracts
  development/                  # this map and roadmap
  migration/                    # GoodWill provenance and compatibility policy
  operations/                   # backup/restore policy
manifests/
  compatibility.json            # zero implicit aliases; future entry contract
  components.json               # component/dependency/state catalog
  host-requirements.json        # versioned evidence, profile policy, severity, guidance
  remediation-actions.json      # planning-only action catalog, risk, approval, recovery policy
  readiness-gates.json          # health/readiness vocabulary and ownership
  repositories.json             # independent repository and pinning policy
  vocabularies.json              # state, backup, exposure, privilege vocabulary
schemas/
  compatibility.schema.json
  component-catalog.schema.json
  deployment-profile.schema.json
  host-preflight.schema.json
  host-drift.schema.json
  host-requirements.schema.json
  remediation-action-catalog.schema.json
  remediation-plan.schema.json
  approval-record.schema.json
  observed-host.schema.json
  desired-deployment.schema.json
  readiness-gates.schema.json
  repository-catalog.schema.json
  repository-lock.schema.json
  resolved-plan.schema.json
  resolved-deployment-record.schema.json
  vocabularies.schema.json
kalvin/
  cli.py                         # validate/resolve/inspect/requirements/drift/plan contract
  loader.py                      # constrained JSON input loading
  validation.py                  # schema, semantic, reference, policy checks
  graph.py                       # stable dependency analysis
  lockfile.py                    # immutable lock validation
  resolver.py                    # in-memory resolved-plan calculation
  output.py                      # deterministic JSON and operator text
  probes.py                      # exact local read-only command allowlist
  host_parsers.py                # pure parsers and identity sanitizers
  host_inspector.py              # ephemeral local observed-host assembly
  drift.py                       # pure requirement selection and drift evaluation
  remediation.py                 # pure planning, fingerprints, graph, approval/stale semantics
  preflight.py                   # retained Phase 4E compatibility view
tests/
  README.md
  fixtures/                      # explicitly synthetic locks and observed host
  test_*.py                      # engine, negative, CLI, and safety tests
  validate_architecture.py       # retained architecture compatibility checks
```

Every current directory contains a useful artifact. `deploy/`, `manifests/`, and `schemas/` are runtime input to the bounded read-only engine. The repository contains no application source, deployment executor, captured host inventory, live template, secret, runtime state, or backup payload. Kalvin is licensed `AGPL-3.0-or-later`.

## Directory responsibilities

| Path | Responsibility |
| --- | --- |
| `deploy/profiles/` | Exactly three primary host-role intent contracts with component, readiness, backup, exposure, and compatibility policy |
| `manifests/` | Shared catalogs, host policy, and non-operational remediation action policy |
| `schemas/` | Syntax contracts for catalogs/profiles, resolved state, plans, and model approvals |
| `docs/` | Human-readable architecture, ownership, lifecycle, migration, and operations policy |
| `kalvin/` | Declaration validation, deterministic resolution, bounded local inspection, pure requirements/drift comparison, planning, approval binding semantics, and presentation |
| `tests/` | Isolated positive, negative, CLI, parser, determinism, staleness, graph, privacy, and mutation-boundary validation |

Create a future top-level directory only with its first reviewed artifact. There is no `scripts/`, `deploy/compose/`, `deploy/templates/`, or application vendor directory today.

## Roadmap

### Phase 4D — first safe implementation tooling (complete)

Phase 4D implements offline declaration validation and desired-to-resolved planning. It accepts secret-free immutable locks, emits stable text/JSON plans, and preserves external readiness gates. It deliberately excludes host preflight and every mutation mechanism; it does not preselect Compose or native services.

### Phase 4E — local host observation and preflight (complete)

Phase 4E observes bounded, sanitized capability data on only the executing host and compares it with resolved profile requirements. Its command allowlist is fixed and read-only. It neither persists inventory nor changes the host. CPU/RAM/storage minimums remain explicitly unspecified pending evidence and human decisions.

### Phase 4F — host requirements and drift policy (complete)

Phase 4F versions the evidence-backed profile requirement policy, establishes an initial Ubuntu-family/x86_64 support baseline, preserves unapproved numeric/model/runtime choices as human decisions, and reports deterministic drift with severity and descriptive remediation. It adds no probe and performs no action. Host compliance remains separate from external application/platform readiness.

### Phase 4G — remediation planning and approval contract (current)

Phase 4G classifies drift into minimized declarative mutation proposals, human policy decisions, or safe investigations. Plans bind resolved state, relevant sanitized drift, requirement policy, planning policy, and action definitions through deterministic fingerprints. Risk, scope, approval, preconditions, validation, rollback, and failure expectations are explicit. Approval records are synthetic/model-only and become stale when the exact plan or policy changes. Execution, rollback, approval persistence, and every host-mutation path remain absent.

### Later implementation gates

1. human review of the Phase 4G plan/action/approval contracts and live read-only planning smoke test;
2. resolution of Phase 4F sizing/runtime and Phase 4G approval/recovery governance decisions;
3. optional dedicated low-privilege inspector/persistence architecture;
4. separately designed execution engine, strict action allowlist, approval binding, privilege model, journal, stale-state rejection, rollback, emergency stop, and recovery proof;
5. reviewed prerequisite/bootstrap implementation one action class at a time;
6. service orchestration for one explicitly selected profile;
7. external configuration and secret-provider adapters;
8. application-consistent backup and restore transport;
9. health, readiness, and boundary reporting beyond current host drift;
10. compatibility and host-migration tooling;
11. Core clean-install and reconstruction proof;
12. Storage-role implementation, retention, and recovery proof;
13. reviewed GoodWill superseded notice and eventual archival.

Do not combine these into one privileged installer or treat successful service startup as proof of recovery or authorization.

## External application dependency

Core production readiness depends on canonical Kal persisting RAG indexing status and passing restart/reconciliation validation. This work belongs in Kal. Kalvin tracks the `kal.rag-status-durable` gate without implementing a parallel database or changing Kal during platform deployment.

## Unresolved decisions

- **License:** resolved as `AGPL-3.0-or-later` in Kalvin's own `LICENSE`.
- **Orchestration mechanism:** Compose, native services, or a constrained combination remains a later implementation decision; Phase 4D contains none.
- **Secret provider:** the reference/ownership interface is fixed; production provider selection is open.
- **Backup technology:** consistency, identity, direction, authority, and retention ownership are fixed; product, schedule, encryption implementation, replication topology, and numeric retention are open.
- **Monitoring implementation:** signal boundaries and profile responsibility are fixed; product and storage policy are open.
- **Optional extensions:** RMM, network overlay, temporary public testing, desktop controls, and exporters require separate review and stay default off/outside core logic.

The unresolved implementation decisions do not block read-only resolution review. They block claims that the platform is operational.

Phase 4G additionally leaves approval-authority definitions, future automatic-action eligibility, high-risk approval expiry, external/multiple approval rules, rollback sufficiency, maintenance windows, backup verification authority, and network recovery proof for human decision. The conservative planning defaults grant no execution authority.
