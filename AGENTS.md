# Kalvin Agent and Automation Policy

These instructions apply to AI assistants and automation operating in the Kalvin repository. More specific instructions may narrow them further, but ordinary tasks do not broaden authority to live hosts or external systems.

## Repository ownership

Kalvin owns platform infrastructure, deployment orchestration, host roles, service wiring, external configuration/secret-injection architecture, backup/restore coordination, monitoring/health integration, portability, host migration, and platform security boundaries.

Kal owns assistant behavior, UI/application logic, sessions, Memory, Library, RAG/retrieval and authorization, model abstraction, the Beepy service contract, application migrations/tests, research, multimodal workflows, and controlled agents/tools. Do not move or reimplement these concerns in Kalvin.

Beepy owns business records, tickets, projects, email workflows, work-specific UI/backend behavior, business integrations and authorization, database state, migrations/tests, and the scoped Beepy-to-Kal client. Do not move or reimplement these concerns in Kalvin.

Application migrations are authored and validated by their owning application. Kalvin may later sequence documented migration commands but must not replace them with platform-owned database edits.

## GoodWill and naming

GoodWill is historical/provenance material, not a parent source tree or current runbook. Do not clone its Git history into Kalvin, copy its full tree, import its mock corpus, or execute its administrative scripts as platform behavior.

Canonical current names are Kalvin, Kal, and Beepy. GoodWill, Odysseus, and MBC Intelligence are historical or compatibility names. Never apply a blind search-and-replace to commits, persisted identifiers, database values, volume names, backup labels, audit evidence, or old paths.

A legacy alias requires consumer evidence, canonical mapping, conflict behavior, tests, ownership, rollback, and retirement criteria. New identifiers use canonical names unless an approved compatibility contract explicitly requires otherwise.

## Secrets and publication safety

- Never read, print, copy, commit, or summarize real secret values.
- Never commit `.env` files, credentials, tokens, passwords, private keys, database content, private endpoints, business/customer data, or recovery material.
- Use placeholders in public templates and documentation.
- Treat health, logs, diagnostics, manifests, and command output as possible disclosure paths.
- Do not contact external services or use production credentials from an ordinary repository task.
- Review the exact tracked tree and reachable objects before publication; ignore rules alone are insufficient.

## Runtime data

Git is the reconstruction recipe, not a runtime backup. Do not add databases, dumps, rendered configuration, secrets, logs, uploads, attachments, caches, model blobs, container volumes, backup archives, host inventories, or temporary runtime state.

Keep the five domains separate: PRIVATE USER, SHARED MSP KNOWLEDGE, BEEPY BUSINESS DATA, TEST/HISTORICAL, and SYSTEM/PLATFORM. Never collapse them into one writable directory for convenience.

## Authoritative and derived state

- Kal SQLite/raw authoritative documents are authoritative.
- Beepy business database and application state are authoritative for Beepy.
- Chroma/vector indexes are derived and rebuildable.
- Model downloads and caches are derived where pinned sources can reproduce them.
- Temporary process state is non-authoritative.

Backup and restore proposals must prioritize authoritative state and rebuild derived state afterward. Do not give a cache authoritative status merely because copying it is easier.

## Host and privilege safety

Do not perform destructive host operations, or any live service, network, firewall, storage, package, container, backup, restore, migration, RMM, or production-state mutation without explicit authorization for that exact change phase.

Ordinary documentation, review, test, or repository-maintenance tasks do not authorize live-system changes. Prefer read-only inspection and isolated candidates. Never infer permission from access.

Kal applications and agents must not receive Docker, systemd, firewall, storage-administration, backup-administration, RMM, or unrestricted shell privileges. A future privileged helper must be separately reviewed, allowlisted, auditable, and inaccessible to ordinary agent/tool execution.

## Production-readiness gates

Do not describe a target as production-ready without recorded validation for:

- pinned repository and dependency identity;
- configuration and secret ownership;
- application migrations and integrity;
- authentication, authorization, and data-domain isolation;
- exposed-service policy;
- authoritative backup and restore proof;
- derived-state reconciliation;
- compatibility behavior and retirement gates;
- retained rollback evidence.

Canonical Kal's durable RAG indexing status and restart/reconciliation validation are a hard `core` readiness dependency. The change belongs in Kal. Do not implement a competing status authority in Kalvin.

## Testing expectations

- Keep tests isolated and non-destructive by default.
- Treat files under `deploy/`, `manifests/`, and `schemas/` as architecture contracts, not executable deployment instructions.
- Resolve selected repositories/components to immutable versions before any later host mutation; a branch or tag alone is not a production lock.
- Do not contact live Kal, Beepy, databases, email, business integrations, Docker, host-management, or network-control systems during ordinary tests.
- Validate repository-relative links, formatting, public safety, ignore behavior, file modes, symlinks, and Git integrity for repository changes.
- For future profiles and tools, test required/optional/forbidden combinations, target confinement, failure behavior, idempotence where promised, rollback, and secret-safe output.
- Distinguish liveness from readiness and readiness from production acceptance.

## Change discipline

Prefer minimal, reversible, one-purpose changes. Preserve user work and historical evidence. Inspect before mutation, identify exact targets, document expected benefit and risk, retain a rollback source, and validate the result. Do not create empty directory trees or speculative abstractions without a useful artifact.
