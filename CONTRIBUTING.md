# Contributing to Kalvin

Kalvin currently contains a charter and non-operational declarative architecture contracts. Contributions should preserve repository boundaries and describe future runtime behavior honestly as `TARGET` or `PLANNED` until implementation and validation exist.

## Branch model

- `main` is the stable, reviewed branch.
- `development` is the normal active-work branch.

Begin ordinary work from an up-to-date `development` branch, use a focused topic branch when the review workflow calls for one, and propose reviewed changes back into `development`. Promotion from `development` to `main` should occur through the repository's reviewed process.

Force pushes are not part of the normal workflow. Do not rewrite shared history, bypass review, or change `main` directly to make a sequence look cleaner.

## Before changing the repository

1. Read `AGENTS.md` and the relevant architecture document.
2. Identify whether the concern belongs to Kalvin, Kal, or Beepy.
3. Label the change as current implementation, target architecture, historical evidence, or planned work.
4. Identify affected host roles, service identities, state classes, privileges, and compatibility behavior.
5. Define validation and rollback before proposing a live-system effect.

If a change requires application logic or schema changes, stop at the repository boundary and coordinate the change in the owning application repository.

## Security and private data

Never commit:

- credentials, tokens, passwords, private keys, certificate private material, or real secret files;
- private email addresses, customer/business records, private endpoint details, host inventories, or production logs;
- rendered environment files, local overrides, database files or dumps, runtime uploads, attachments, caches, container volumes, or backup archives;
- output from commands that may expose configuration values or machine identity.

Safe examples use explicit placeholders and logical service names. A passing scanner does not replace review of the exact diff.

## Platform boundary changes

Changes to identity, privilege, secrets, exposure, data ownership, backup authority, restore ordering, application contracts, or production-readiness gates require careful review. Document:

- the current and target state;
- affected profiles and repositories;
- threat and failure behavior;
- required privileges;
- migration and rollback path;
- tests and acceptance evidence.

Do not make local-network reachability an authorization rule. Do not expose host-management/RMM authority to Kal agents or tools.

## Compatibility changes

A compatibility alias or adapter needs:

- a proven current consumer;
- canonical and legacy identifiers;
- a single translation direction;
- fail-closed conflict behavior;
- tests and observable deprecation without value leakage;
- an owner, rollback procedure, and retirement condition.

Do not preserve or add a legacy name solely because it appears in GoodWill history. Do not mechanically rename persisted identifiers or historical evidence.

## Implementation changes

Large or privileged changes must first be represented through a reviewed candidate or declarative profile design and tested in an isolated environment appropriate to the risk. Do not use an ordinary documentation or repository-maintenance task to mutate live services, networking, storage, or production data.

When executable implementation is authorized later:

- prefer small, reversible, one-purpose changes;
- provide preflight and dry-run behavior where meaningful;
- validate exact targets before mutation;
- keep application migrations in Kal or Beepy;
- keep authoritative state recoverable and derived caches disposable;
- avoid hidden fallback to legacy production behavior.

## Review checklist

Before committing:

```bash
git status --short
git diff --check
git diff
```

Also verify:

- reference manifests pass `python3 tests/validate_architecture.py`;
- documentation links resolve;
- no unexpected executable or symlink was added;
- no secret, private endpoint, runtime state, or generated artifact is tracked;
- profile and repository ownership remain explicit;
- tests match the risk and do not contact live systems by default;
- a license claim has not been introduced without the human decision.

Use clear, focused commit messages that describe the outcome. Review every staged path before committing or publishing.
