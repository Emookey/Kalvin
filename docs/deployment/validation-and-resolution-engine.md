# Validation and Resolution Engine

Status: **CURRENT Phase 4D executable; read-only with respect to host state.**

## Purpose

The engine answers: “What would this Kalvin deployment require?” It safely loads the committed JSON contracts, validates syntax and policy, combines one selected profile with immutable repository/component locks, analyzes dependency relationships, and emits a deterministic resolved plan to stdout.

It has no apply stage. It does not deploy, install, fetch, start or stop services, render host files, inspect live configuration, resolve a secret value, probe health, contact a network, or persist deployment records.

## Commands and exits

```text
python3 -m kalvin --help
python3 -m kalvin validate [--format text|json]
python3 -m kalvin resolve --profile lab --lock LOCK.json [--enable COMPONENT] [--format text|json]
python3 -m kalvin resolve --profile core --lock LOCK.json [--enable COMPONENT] [--format text|json]
python3 -m kalvin resolve --profile storage --lock LOCK.json [--enable COMPONENT] [--format text|json]
```

Exit `0` means validation or structural resolution succeeded. Exit `2` means user input, a manifest, policy, cross-reference, or lock failed validation. Exit `3` identifies an unexpected internal engine failure. A structurally resolved Core plan returns `0` even when expected external readiness evidence is absent; its plan still says `BLOCKED_EXTERNAL_GATE`.

Normal user mistakes produce concise messages rather than tracebacks. There are no `apply`, `deploy`, `install`, service-control, host-detection, or arbitrary output-file options.

## Validation classes

The validator uses local Draft 2020-12 schemas through the declared `jsonschema` dependency, then applies architecture-specific checks. Findings are classified where practical as:

- `SCHEMA ERROR` for malformed JSON structures and vocabulary syntax;
- `SEMANTIC ERROR` for duplicates, unsafe state relationships, and cycles;
- `CROSS-REFERENCE ERROR` for missing components, repositories, dependencies, or gates;
- `POLICY ERROR` for forbidden exposure, privilege, identity, backup, lock, compatibility, or private-material behavior.

Remote schema references are rejected. The validator does not attempt to become a general network-enabled schema resolver.

## Lock contract

The schema is [`repository-lock.schema.json`](../../schemas/repository-lock.schema.json). A lock contains synthetic/public-safe logical identities and either:

- a repository ID, contextual desired ref, and lowercase full 40-hex resolved Git commit; or
- a component ID, contextual desired implementation, and exact semantic version or `sha256` digest.

The full commit or exact implementation version is the correctness anchor. `HEAD`, `latest`, short SHAs, branch names in the commit field, credential-bearing URLs, secret-looking assignments, duplicates, and unknown IDs fail closed. A `lab` desired ref may name development only when its full commit is present. Core rejects development refs for Kal and Beepy.

Files under [`tests/fixtures/`](../../tests/fixtures/) are explicitly synthetic examples. They are not claims about current production versions and must not be promoted as production locks.

## Resolution model

Phase 4D keeps three states separate:

```text
DESIRED STATE (profile and optional selections)
  -> RESOLVED PLAN (exact declared requirements; Phase 4D output)
  -> DEPLOYED/OBSERVED STATE (future evidence; not evaluated here)
```

The plan includes profile and component policy, ownership, immutable locks, stable dependency order, distinct startup/health/readiness/optional-integration relationships, configuration requirements, logical secret references, state and backup declarations, filesystem destinations as intent, exposure ceilings, identities, privileges, compatibility requirements, readiness gates, external blockers, and overall statuses.

Secret references never contain values. Configuration requirements never read the process environment or host files. Filesystem paths are carried through as declared intent and are never touched.

## Determinism

The same manifests, profile, optional selections, and lock produce byte-identical JSON. Keys are sorted, semantically unordered lists use stable ordering, and dependency ordering uses lexical tie-breaking. JSON contains no timestamp, hostname, current user, working directory, process ID, temporary path, random value, or observed host detail.

## Dependencies and readiness

`STARTUP`, `HEALTH`, `READINESS`, and `OPTIONAL_INTEGRATION` remain distinct. Required missing dependencies fail resolution. Startup ordering does not claim health or readiness. Blocking relationship cycles are validated independently and reported with a cycle path.

Architecture validity, structural resolution, and production readiness are separate:

- `VALID` / `INVALID` describes the contracts;
- `RESOLVED` / `UNRESOLVED` describes whether exact declared requirements were calculated;
- `READY`, `BLOCKED_EXTERNAL_GATE`, or `NOT_APPLICABLE` describes production readiness scope.

Phase 4D can verify declarative contract, lock, exposure, and identity structure. Runtime/application gates remain `REQUIRED / EXTERNAL / UNVERIFIED`. In particular, Core always carries `kal.rag-status-durable` that way until canonical Kal supplies validated persistence and restart/reconciliation evidence. There is no CLI bypass.

## Later phases

Local host capability inspection now belongs to the separate Phase 4E read-only boundary documented in [Read-Only Host Inspection and Preflight](host-inspection-and-preflight.md). Controlled persistence, remote inspection, configuration rendering, repository acquisition, orchestration, backup/restore transport, application health probes, and deployment remain separately authorized future phases. None is implied by a Phase 4D plan or Phase 4E host comparison.
