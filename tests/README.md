# Architecture Contract Validation

Status: **CURRENT isolated engine validation; no deployment capability.**

Run from the repository root:

```text
python3 tests/validate_architecture.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

The retained architecture validator uses only the Python standard library. The engine declares `jsonschema` for full Draft 2020-12 validation. The unit suite covers Phase 4D resolution, synthetic Phase 4E observation/preflight, Phase 4F evidence-backed requirements/drift, and Phase 4G deterministic planning, plan minimization, action catalog validation, exact approval binding, stale-plan semantics, risk/scope/precondition/validation/rollback/failure contracts, action graphs, CLI no-write behavior, privacy, and the explicit mutation boundary.

Tests use synthetic locks, a synthetic observed-host document, mocked probe execution, in-memory policy mutation, synthetic model-only approvals, and controlled temporary directories only. Ordinary tests do not run live inspection/drift/planning, render configuration, resolve secret values, acquire repositories, contact services, persist approval or inventory, remediate, roll back, or change a host. Passing establishes the tested planning-only boundary, not operational or production readiness.
