# Architecture Contract Validation

Status: **CURRENT isolated engine validation; no deployment capability.**

Run from the repository root:

```text
python3 tests/validate_architecture.py
python3 -m unittest discover -s tests -p 'test_*.py'
```

The retained architecture validator uses only the Python standard library. The engine declares `jsonschema` for full Draft 2020-12 validation. The unit suite covers Phase 4D resolution plus synthetic Phase 4E OS/CPU/memory/storage/mount/service/executable/Docker/network parsing, observation status distinctions, Lab/Core/Storage preflight, deterministic output, privacy sanitization, probe failure handling, CLI no-write behavior, and the explicit mutation boundary.

Tests use synthetic locks, a synthetic observed-host document, mocked probe execution, and controlled temporary directories only. Ordinary tests do not run full live inspection, render configuration, resolve secret values, acquire repositories, contact services, or change a host. Passing establishes the tested read-only boundary, not operational or production readiness.
