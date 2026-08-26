# Kalvin

Kalvin is the platform, infrastructure, and orchestration layer for independently maintained Kal and Beepy applications. Its intended job is to make supported hosts reconstructable: define host roles, connect services, inject configuration and secrets safely, coordinate backups and restores, expose health signals, and guide migrations without absorbing application source.

## Repository status

**CURRENT — declarative architecture candidate.** This repository contains the Phase 4B charter plus Phase 4C reference profiles, component/state catalogs, JSON Schemas, and static contract validation. The declarations are deliberately marked non-operational. There are no Compose stacks, systemd units, installers, network rules, backup/restore executables, or host-migration tools, and the repository is not production-ready.

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

Profiles are **CURRENT architecture contracts**, explicit, and composable. They declare intent and constraints; they are not executable deployment files.

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

## Architecture contracts and future implementation

Reference profiles live under `deploy/profiles/`, shared catalogs under `manifests/`, their syntax contracts under `schemas/`, and static architecture validation under `tests/`. These files describe and validate intent only.

**PLANNED — absent today.** Operational orchestration and bounded host tooling will be introduced only after review. Their eventual location and responsibility are described in the repository map; no empty implementation directory has been created in anticipation.

## License status

No Kalvin license has been selected, and this repository contains no `LICENSE` file.

**LICENSE POLICY REQUIRES HUMAN DECISION.** Kal's AGPL-3.0-or-later license does not automatically become Kalvin's license merely because Kalvin may deploy Kal. License selection remains a publication and governance decision before final public release is settled.
