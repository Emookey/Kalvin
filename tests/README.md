# Architecture Contract Validation

Status: **CURRENT isolated engine validation; no deployment capability.**

Run from the repository root:

```text
python3 tests/validate_architecture.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

The retained architecture validator uses only the Python standard library. The Phase 4D engine declares `jsonschema` for full Draft 2020-12 validation. The unit suite covers positive Lab/Core/Storage resolution, immutable locks, stable output, state/backup/configuration/secret handling, external readiness, negative policy cases, CLI exits, and the tested host-mutation boundary.

Tests use synthetic locks and temporary test directories only. They do not render configuration, resolve secret values, acquire repositories, contact services, inspect runtime state, or change a host. Passing establishes the tested declarative boundary, not operational or production readiness.
