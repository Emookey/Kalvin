# Repository Map and Roadmap

Status: **CURRENT Phase 4F read-only host requirements/drift and PLANNED later implementation sequence.**

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
  observed-host.schema.json
  desired-deployment.schema.json
  readiness-gates.schema.json
  repository-catalog.schema.json
  repository-lock.schema.json
  resolved-plan.schema.json
  resolved-deployment-record.schema.json
  vocabularies.schema.json
kalvin/
  cli.py                         # validate/resolve/inspect/requirements/drift contract
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
| `manifests/` | Shared catalogs and controlled vocabulary independent of a runtime engine |
| `schemas/` | Syntax contracts for current catalogs/profiles and future desired/resolved deployment records |
| `docs/` | Human-readable architecture, ownership, lifecycle, migration, and operations policy |
| `kalvin/` | Declaration validation, deterministic resolution, bounded local inspection, pure requirements/drift comparison, and presentation |
| `tests/` | Isolated positive, negative, CLI, parser, determinism, privacy, and mutation-boundary validation |

Create a future top-level directory only with its first reviewed artifact. There is no `scripts/`, `deploy/compose/`, `deploy/templates/`, or application vendor directory today.

## Roadmap

### Phase 4D — first safe implementation tooling (complete)

Phase 4D implements offline declaration validation and desired-to-resolved planning. It accepts secret-free immutable locks, emits stable text/JSON plans, and preserves external readiness gates. It deliberately excludes host preflight and every mutation mechanism; it does not preselect Compose or native services.

### Phase 4E — local host observation and preflight (complete)

Phase 4E observes bounded, sanitized capability data on only the executing host and compares it with resolved profile requirements. Its command allowlist is fixed and read-only. It neither persists inventory nor changes the host. CPU/RAM/storage minimums remain explicitly unspecified pending evidence and human decisions.

### Phase 4F — host requirements and drift policy (current)

Phase 4F versions the evidence-backed profile requirement policy, establishes an initial Ubuntu-family/x86_64 support baseline, preserves unapproved numeric/model/runtime choices as human decisions, and reports deterministic drift with severity and descriptive remediation. It adds no probe and performs no action. Host compliance remains separate from external application/platform readiness.

### Later implementation gates

1. human live review of the local inspector and Phase 4F requirement/decision policy;
2. optional dedicated low-privilege inspector/persistence architecture;
3. reviewed prerequisite/bootstrap implementation;
4. service orchestration for one explicitly selected profile;
5. external configuration and secret-provider adapters;
6. application-consistent backup and restore transport;
7. health, readiness, and boundary reporting beyond current host drift;
8. compatibility and host-migration tooling;
9. Core clean-install and reconstruction proof;
10. Storage-role implementation, retention, and recovery proof;
11. reviewed GoodWill superseded notice and eventual archival.

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
