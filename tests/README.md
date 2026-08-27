# Architecture Contract Validation

Status: **CURRENT static validation; not deployment tooling.**

Run from the repository root:

```text
python3 tests/validate_architecture.py
```

The validator uses only the Python standard library. It parses reference JSON, applies the local JSON Schema subset used by the repository, checks catalog/profile cross-references, validates state/backup/exposure/privilege/readiness invariants, checks repository independence rules, rejects operational command text in declarations, resolves internal Markdown file links, and scans public text for common private-material patterns.

It does not render configuration, resolve secret references, acquire repositories, contact services, inspect runtime state, or change a host. Passing means the repository contracts are internally consistent; it does not establish operational or production readiness.
