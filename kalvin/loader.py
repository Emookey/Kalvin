# SPDX-License-Identifier: AGPL-3.0-or-later
"""Constrained JSON loading for public architecture and lock documents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Architecture, Finding, UserInputError


CATALOG_PATHS = {
    "vocabularies": Path("manifests/vocabularies.json"),
    "repositories": Path("manifests/repositories.json"),
    "components": Path("manifests/components.json"),
    "readiness-gates": Path("manifests/readiness-gates.json"),
    "compatibility": Path("manifests/compatibility.json"),
    "host-requirements": Path("manifests/host-requirements.json"),
    "remediation-actions": Path("manifests/remediation-actions.json"),
}
PROFILE_IDS = ("core", "lab", "storage")


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sensitive_path(path: Path) -> bool:
    for part in path.parts:
        lowered = part.lower()
        if lowered in {"secret", "secrets", "credential", "credentials"}:
            return True
        if lowered == ".env" or lowered.startswith(".env."):
            return True
        if lowered in {"id_rsa", "id_ed25519", "id_ecdsa"}:
            return True
        if lowered.endswith((".pem", ".p12", ".pfx")):
            return True
    return False


def read_json(path: Path, *, purpose: str) -> dict[str, Any]:
    """Read one non-secret JSON object without following a secret-named path."""
    if _sensitive_path(path):
        raise UserInputError(f"Refusing to read secret-bearing path for {purpose}: {path}")
    try:
        if path.is_symlink():
            raise UserInputError(f"Refusing symlink input for {purpose}: {path}")
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UserInputError(f"Cannot read {purpose} {path}: {exc}") from exc
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UserInputError(
            f"Malformed JSON in {purpose} {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    if not isinstance(value, dict):
        raise UserInputError(f"{purpose} {path} must contain one JSON object")
    return value


def load_architecture(root: Path | None = None) -> tuple[Architecture | None, list[Finding]]:
    """Load the fixed public contract set and return parse findings, never a traceback."""
    root = (root or repository_root()).resolve()
    catalogs: dict[str, dict[str, Any]] = {}
    profiles: dict[str, dict[str, Any]] = {}
    schemas: dict[str, dict[str, Any]] = {}
    document_paths: dict[str, Path] = {}
    findings: list[Finding] = []

    for name, relative in CATALOG_PATHS.items():
        path = root / relative
        try:
            catalogs[name] = read_json(path, purpose="architecture declaration")
            document_paths[f"catalog:{name}"] = path
        except UserInputError as exc:
            findings.append(Finding("SCHEMA ERROR", "document-load", relative.as_posix(), str(exc)))

    for profile_id in PROFILE_IDS:
        relative = Path(f"deploy/profiles/{profile_id}.json")
        path = root / relative
        try:
            profiles[profile_id] = read_json(path, purpose="deployment profile")
            document_paths[f"profile:{profile_id}"] = path
        except UserInputError as exc:
            findings.append(Finding("SCHEMA ERROR", "document-load", relative.as_posix(), str(exc)))

    schema_dir = root / "schemas"
    try:
        schema_paths = sorted(schema_dir.glob("*.schema.json"), key=lambda item: item.name)
    except OSError as exc:
        findings.append(Finding("SCHEMA ERROR", "schema-directory", "schemas", str(exc)))
        schema_paths = []
    for path in schema_paths:
        try:
            schemas[path.name] = read_json(path, purpose="JSON Schema")
            document_paths[f"schema:{path.name}"] = path
        except UserInputError as exc:
            findings.append(Finding("SCHEMA ERROR", "schema-load", f"schemas/{path.name}", str(exc)))

    if findings:
        return None, sorted(findings)
    return Architecture(root, catalogs, profiles, schemas, document_paths), []
