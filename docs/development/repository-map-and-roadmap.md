# Repository Map and Roadmap

Status: **CURRENT bootstrap contents and PLANNED implementation sequence.**

## Current repository map

```text
.gitignore
AGENTS.md
CONTRIBUTING.md
README.md
docs/
  architecture/
    data-and-state.md
    host-layout.md
    overview.md
    repository-boundaries.md
  deployment/
    portability-and-readiness.md
    profiles.md
  development/
    repository-map-and-roadmap.md
  migration/
    goodwill-and-compatibility.md
  operations/
    backup-restore-model.md
```

Every current directory contains useful documentation. The repository has no deployment implementation, executable, manifest, test fixture, secret, runtime state, or license file.

## Planned implementation structure

Create a top-level directory only when its first reviewed artifact exists:

| Planned path | Future responsibility |
| --- | --- |
| `deploy/profiles/` | Declarative, machine-neutral `lab`, `core`, and `storage` selections |
| `deploy/templates/` | Public-safe configuration inputs rendered with external values |
| `manifests/` | Pinned application/dependency identities, state classes, backup-set definitions, and compatibility metadata |
| `scripts/bootstrap/` | Bounded prerequisite and structure operations after design approval |
| `scripts/health/` | Secret-safe profile and service checks |
| `scripts/backup/` | Coordination of application-owned consistent snapshots and transfer/verification |
| `scripts/restore/` | Controlled restore ordering and calls to owner-provided migrations/reconciliation |
| `scripts/migration/` | Version-gated, one-time transitions with rollback evidence |
| `tests/` | Static policy/schema/publication checks and isolated implementation tests |

There is no separate top-level `config/` today because public deployment inputs fit under `deploy/templates/`. Add another category only if a distinct responsibility is demonstrated. Do not create `deploy/compose/` until a reviewed implementation actually selects Compose for a defined scope.

## Roadmap

### Phase 4C — portable deployment architecture

Design declarative profile schemas and composition rules, component/version manifests, service dependency and exposure contracts, configuration/secret inputs, state classes, and validation interfaces. Phase 4C remains architecture/design unless its authorization says otherwise.

### Later implementation work

After review, sequence the work into small gates:

1. prerequisite and bootstrap implementation;
2. service orchestration for selected profiles;
3. external configuration and secret injection;
4. application-consistent backup and restore implementation;
5. health, readiness, and boundary tooling;
6. compatibility and host-migration tooling;
7. clean-install and reconstruction proof for Core;
8. Storage-role implementation and recovery proof;
9. reviewed GoodWill superseded notice and eventual archival.

Do not combine these into one privileged installer or treat successful service startup as proof of recovery or authorization.

## External application dependency

Core production readiness depends on canonical Kal persisting RAG indexing status and passing restart/reconciliation validation. This work belongs in Kal. Kalvin must track and verify the dependency without implementing a parallel database or changing Kal during platform deployment.

## Governance decisions still open

- **License:** LICENSE POLICY REQUIRES HUMAN DECISION. Kalvin does not automatically inherit Kal's AGPL-3.0-or-later terms, and no `LICENSE` file exists.
- **Implementation mechanisms:** Compose, native services, or mixed orchestration remain to be selected per supported profile.
- **Secret delivery:** the interface and ownership rules are defined, but the production mechanism is not.
- **Backup technology and retention:** roles and authority rules are defined; products, schedules, retention values, encryption, and replication topology remain open.
- **Optional extensions:** RMM, Tailscale, public testing, desktop controls, and exporters require separate design and are not platform-core defaults.

Open decisions do not block this local documentation bootstrap. They do block claims that the platform is operational or ready for final public release.
