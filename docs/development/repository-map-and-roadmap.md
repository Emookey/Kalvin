# Repository Map and Roadmap

Status: **CURRENT Phase 4C architecture contents and PLANNED implementation sequence.**

## Current repository map

```text
.gitignore
AGENTS.md
CONTRIBUTING.md
README.md
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
  readiness-gates.json          # health/readiness vocabulary and ownership
  repositories.json             # independent repository and pinning policy
  vocabularies.json              # state, backup, exposure, privilege vocabulary
schemas/
  compatibility.schema.json
  component-catalog.schema.json
  deployment-profile.schema.json
  desired-deployment.schema.json
  readiness-gates.schema.json
  repository-catalog.schema.json
  resolved-deployment-record.schema.json
  vocabularies.schema.json
tests/
  README.md
  validate_architecture.py       # static standard-library contract validation
```

Every current directory contains a useful artifact. `deploy/`, `manifests/`, and `schemas/` are reference architecture, not runtime input to an implemented engine. The repository contains no application source, deployment executable, live template, secret, runtime state, backup payload, or license file.

## Directory responsibilities

| Path | Responsibility |
| --- | --- |
| `deploy/profiles/` | Exactly three primary host-role intent contracts with component, readiness, backup, exposure, and compatibility policy |
| `manifests/` | Shared catalogs and controlled vocabulary independent of a runtime engine |
| `schemas/` | Syntax contracts for current catalogs/profiles and future desired/resolved deployment records |
| `docs/` | Human-readable architecture, ownership, lifecycle, migration, and operations policy |
| `tests/` | Isolated static validation only; no host or service operations |

Create a future top-level directory only with its first reviewed artifact. There is no `scripts/`, `deploy/compose/`, `deploy/templates/`, or application vendor directory today.

## Roadmap

### Phase 4D — first safe implementation tooling

After human review and canonical integration of the Phase 4C contracts, implement the smallest bounded foundation: offline declaration validation, desired-to-resolved planning, dry-run/preflight behavior, and public-safe configuration interfaces. The exact Phase 4D authorization must decide which mechanism is in scope; these contracts do not preselect Compose or native services.

### Later implementation gates

1. reviewed prerequisite/bootstrap implementation;
2. service orchestration for one explicitly selected profile;
3. external configuration and secret-provider adapters;
4. application-consistent backup and restore transport;
5. health, readiness, boundary, and drift reporting;
6. compatibility and host-migration tooling;
7. Core clean-install and reconstruction proof;
8. Storage-role implementation, retention, and recovery proof;
9. reviewed GoodWill superseded notice and eventual archival.

Do not combine these into one privileged installer or treat successful service startup as proof of recovery or authorization.

## External application dependency

Core production readiness depends on canonical Kal persisting RAG indexing status and passing restart/reconciliation validation. This work belongs in Kal. Kalvin tracks the `kal.rag-status-durable` gate without implementing a parallel database or changing Kal during platform deployment.

## Unresolved decisions

- **License:** LICENSE POLICY REQUIRES HUMAN DECISION. Kalvin does not automatically inherit Kal's AGPL-3.0-or-later terms, and no `LICENSE` file exists.
- **Orchestration mechanism:** Compose, native services, or a constrained combination requires Phase 4D review.
- **Secret provider:** the reference/ownership interface is fixed; production provider selection is open.
- **Backup technology:** consistency, identity, direction, authority, and retention ownership are fixed; product, schedule, encryption implementation, replication topology, and numeric retention are open.
- **Monitoring implementation:** signal boundaries and profile responsibility are fixed; product and storage policy are open.
- **Optional extensions:** RMM, network overlay, temporary public testing, desktop controls, and exporters require separate review and stay default off/outside core logic.

These decisions do not block architecture review. They block claims that the platform is operational or that contribution/publication governance is settled.
