# Updates, Rollback, and Drift

Status: **CURRENT lifecycle contract; no updater or drift repair exists.**

## Safe update lifecycle

A future implementation follows this gate sequence:

1. preflight the selected profile, host role, current record, and application contracts;
2. resolve desired refs to immutable versions and verify policy;
3. require current, verified authoritative backup evidence when update policy says rollback may need data restore;
4. quiesce only components whose application/database consistency contract requires it;
5. deploy pinned code/configuration while exposure remains disabled;
6. invoke migrations supplied by each owning application;
7. reconcile derived state from authoritative state;
8. run component health checks, then profile readiness checks;
9. enable only approved exposure;
10. write the resolved deployment record and retain rollback evidence.

Unknown versions, missing secrets, failed backup preconditions, migration failures, and readiness failures block promotion. Migrations are not assumed reversible.

## Rollback boundary

**Code rollback** may select a prior immutable repository/component version when its application compatibility contract permits it.

**Data/schema rollback** is separate. After an irreversible or backward-incompatible migration, returning to an older Git commit is insufficient and may be unsafe. Recovery may require restoring a pre-update authoritative backup through application-owned procedures, rerunning compatible migrations, rebuilding derived state, and revalidating readiness before exposure.

Every update plan records the last known compatible code/data pair, backup evidence, migration boundary, and acceptance/rollback decision. Kalvin does not invent reverse migrations.

## Drift model

Future tooling compares three views:

```text
desired manifest <-> resolved deployment record <-> observed host state
```

Reportable drift includes a wrong repository commit, unresolved/missing configuration, secret-reference failure, unexpected service, missing/extra mount, path-owner mismatch, profile mismatch, exposure beyond policy, state-class mismatch, or readiness regression.

Initial drift tooling reports evidence before repair. It does not automatically stop services, rewrite configuration, change storage, or discard state. Any repair is a separately planned, bounded action with backup and rollback appropriate to the affected state class.
