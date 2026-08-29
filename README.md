# Kalvin

Kalvin is the platform, infrastructure, and orchestration layer for independently maintained Kal and Beepy applications. Its intended job is to make supported hosts reconstructable: define host roles, connect services, inject configuration and secrets safely, coordinate backups and restores, expose health signals, and guide migrations without absorbing application source.

## Repository status

**CURRENT — declarative architecture plus read-only resolution, observation, drift reporting, and remediation planning.** This repository contains the Phase 4B charter, Phase 4C contracts, Phase 4D validator/resolver, Phase 4E bounded local inspector/preflight, Phase 4F evidence-backed host requirement/drift policy, and Phase 4G deterministic remediation-plan and approval contracts. The engine can explain noncompliance and produce a review plan, but it cannot execute, remediate, deploy, repair, roll back, elevate, contact a network, persist approval, or persist inventory. There are no Compose stacks, systemd units, installers, network rules, backup/restore executors, or host-migration tools, and the repository is not production-ready.

**TARGET — portable platform.** A later implementation phase may build narrowly scoped tooling against these reviewed contracts. Documentation continues to distinguish designed behavior from implemented and validated behavior.

## What Kalvin is

- platform infrastructure and service wiring;
- deployment orchestration and explicit host-role definitions;
- reconstruction and host-migration infrastructure;
- configuration and secret-injection architecture;
- backup/restore coordination and storage-role policy;
- monitoring, health, and readiness integration;
- platform security, exposure, and privilege boundaries;
- a host-neutral portability recipe for pinned application releases.

## What Kalvin is not

- Kal or Beepy application source;
- a monorepo or a submodule collection;
- a renamed GoodWill repository;
- a runtime-data, database, container-volume, cache, or secrets backup;
- a replacement for Kal- or Beepy-owned migrations;
- a legacy server disk-image project;
- an unrestricted host-management or agent-privilege layer;
- a promise that all profiles run all services.

## Repository relationships

### Kal

Kal is the general-purpose assistant application. It owns assistant behavior, UI and application logic, sessions, Memory, Library, RAG and retrieval authorization, model abstraction, the Beepy-scoped service contract, application migrations and tests, research, multimodal workflows, and controlled agents/tools.

Kalvin may deploy and configure a pinned Kal release. It must not copy those implementations into this repository or treat network access as application authorization.

### Beepy

Beepy is the business/work intelligence application. It owns business records, tickets, projects, email workflows, work-specific UI/backend code, business integrations, database state, migrations, tests, and the scoped Beepy-to-Kal client.

Kalvin may deploy and configure a pinned Beepy release. Business application logic and business authorization remain in Beepy.

### GoodWill

**HISTORICAL — provenance only.** GoodWill records the earlier monolithic AI Workspace Lab. Kalvin starts from new Git history and rewritten architecture, not from a GoodWill clone, commit import, or mechanical rename. GoodWill history is expected to remain preserved and may later be marked superseded and archived only after the successor repositories are established.

## Host profiles

- `lab` selects experimental or compatibility components. Its current behavior does not define production truth.
- `core` is the future primary application/compute role. It hosts selected platform services, Kal, Beepy, and model compute as appropriate, and sends backups outward.
- `storage` is the backup/NAS/retention role planned for suitable storage infrastructure. It does not run Kal or Beepy by default.

Profiles are **CURRENT architecture contracts**, explicit, and composable. The resolver reads them as deployment intent, but they remain declarations rather than executable deployment files.

## Read-only tooling

From the repository root:

```text
python3 -m kalvin validate
python3 -m kalvin resolve --profile lab --lock tests/fixtures/synthetic-lab.lock.json --format text
python3 -m kalvin resolve --profile core --lock tests/fixtures/synthetic-core.lock.json --format json
python3 -m kalvin resolve --profile storage --lock tests/fixtures/synthetic-storage.lock.json --format text
python3 -m kalvin host inspect --format text
python3 -m kalvin host preflight --profile core --lock tests/fixtures/synthetic-core.lock.json --format text
python3 -m kalvin host requirements --profile core --format text
python3 -m kalvin host drift --profile core --lock tests/fixtures/synthetic-core.lock.json --format text
python3 -m kalvin host plan --profile core --lock tests/fixtures/synthetic-core.lock.json --format text
```

The tracked examples are explicitly synthetic and are not production locks or captured host inventories. `host requirements` observes nothing. `host inspect`, `host preflight`, `host drift`, and `host plan` observe only the local machine and write only stdout/stderr. `host plan` emits an in-memory review contract with deterministic fingerprints and `execution_available: false`; the first live smoke test is reserved for a human operator. The CLI has no apply, execute, repair, deploy, install, service-control, approval-persistence, rollback, remote-inspection, network-client, or arbitrary file-output command. Host compliance does not mean software ran or application readiness passed.

## Portability objective

The target reconstruction path starts with a fresh supported Ubuntu Server installation, installs reviewed prerequisites, obtains pinned canonical repositories independently, selects a profile, injects configuration and secrets externally, restores approved authoritative data, runs application-owned migrations, rebuilds derived indexes, starts services, and validates health, readiness, and boundaries.

The design must not require an old disk image, legacy absolute paths, committed machine addresses, committed secrets, copied container volumes as master data, or one model provider.

## Current readiness interlock

Canonical Kal currently keeps RAG indexing status in process-local memory. Durable indexing status and restart/reconciliation validation are required before the `core` profile can be considered production-ready. The application change belongs to Kal; Kalvin tracks the dependency and must not implement it here.

## Documentation

- [Platform overview](docs/architecture/overview.md)
- [Repository boundaries](docs/architecture/repository-boundaries.md)
- [Data and state architecture](docs/architecture/data-and-state.md)
- [Conceptual host layout](docs/architecture/host-layout.md)
- [Deployment profiles](docs/deployment/profiles.md)
- [Declarative deployment model](docs/deployment/declarative-model.md)
- [Validation and resolution engine](docs/deployment/validation-and-resolution-engine.md)
- [Read-only host inspection and preflight](docs/deployment/host-inspection-and-preflight.md)
- [Host requirements and drift policy](docs/deployment/host-requirements-and-drift.md)
- [Hardware requirement decisions](docs/deployment/hardware-requirement-decisions.md)
- [Remediation planning and approval](docs/deployment/remediation-planning-and-approval.md)
- [Component model](docs/deployment/component-model.md)
- [Repository and version pinning](docs/deployment/repository-pinning.md)
- [Configuration and secret references](docs/deployment/configuration-and-secrets.md)
- [Dependencies, health, and readiness](docs/deployment/health-readiness-and-dependencies.md)
- [Network, identity, and privilege](docs/deployment/network-identity-and-privilege.md)
- [Updates, rollback, and drift](docs/deployment/update-rollback-and-drift.md)
- [Portability and readiness](docs/deployment/portability-and-readiness.md)
- [Backup and restore model](docs/operations/backup-restore-model.md)
- [GoodWill migration and legacy compatibility](docs/migration/goodwill-and-compatibility.md)
- [Repository map and roadmap](docs/development/repository-map-and-roadmap.md)

## Architecture contracts and bounded implementation

Reference profiles live under `deploy/profiles/`, shared catalogs and evidence-backed host/planning policy under `manifests/`, syntax contracts under `schemas/`, read-only engine modules under `kalvin/`, and isolated validation under `tests/`. The engine calculates intent, observes bounded local capabilities, reports deterministic host drift, and produces declarative remediation proposals, human decisions, and investigations.

**PLANNED — absent today.** Inventory persistence, approval persistence, remote inspection, operational orchestration, controlled execution/rollback, and bounded deployment tooling remain later, separately reviewed phases. Phase 4G contains no apply/execute/fix/deploy/repair/rollback path.

## License

Kalvin is licensed under the GNU Affero General Public License version 3 or later (`AGPL-3.0-or-later`). See `LICENSE` for the full license terms.
