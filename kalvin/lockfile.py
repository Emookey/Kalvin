# SPDX-License-Identifier: AGPL-3.0-or-later
"""Secret-free immutable repository and implementation lock validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .loader import read_json
from .models import Architecture, UserInputError
from .validation import sensitive_value_reason


FULL_GIT_OBJECT_ID = re.compile(r"^[0-9a-f]{40}$")
IMMUTABLE_IMPLEMENTATION_VERSION = re.compile(
    r"^(?:[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?|sha256:[0-9a-f]{64})$"
)
AMBIGUOUS_REFS = {"head", "latest", "tip", "current"}


@dataclass(frozen=True)
class LockData:
    schema_version: str
    repository_entries: dict[str, dict[str, Any]]
    implementation_entries: dict[str, dict[str, Any]]


def _error_path(error: Any) -> str:
    path = ".".join(str(item) for item in error.absolute_path)
    return path or "$"


def validate_lock_document(document: dict[str, Any], architecture: Architecture) -> LockData:
    schema = architecture.schemas.get("repository-lock.schema.json")
    if schema is None:
        raise UserInputError("Architecture is missing schemas/repository-lock.schema.json")
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda item: (list(item.absolute_path), item.message))
    if errors:
        details = "; ".join(f"{_error_path(error)}: {error.message}" for error in errors)
        raise UserInputError(f"Repository lock SCHEMA ERROR: {details}")

    repositories: dict[str, dict[str, Any]] = {}
    implementations: dict[str, dict[str, Any]] = {}
    known_repositories = {item["id"] for item in architecture.catalogs["repositories"]["repositories"]}
    known_components = {item["id"] for item in architecture.catalogs["components"]["components"]}

    for index, entry in enumerate(document["locks"]):
        for key, value in entry.items():
            if isinstance(value, str):
                reason = sensitive_value_reason(value)
                if reason:
                    raise UserInputError(f"Repository lock POLICY ERROR at locks[{index}].{key}: {reason} is forbidden")
        desired_ref = entry["desired_ref"]
        if desired_ref.strip().lower() in AMBIGUOUS_REFS:
            raise UserInputError(f"Repository lock POLICY ERROR at locks[{index}]: desired_ref {desired_ref!r} is ambiguous")
        if entry["kind"] == "REPOSITORY":
            repository_id = entry["repository_id"]
            if repository_id not in known_repositories:
                raise UserInputError(f"Repository lock CROSS-REFERENCE ERROR: unknown repository {repository_id!r}")
            if repository_id in repositories:
                raise UserInputError(f"Repository lock SEMANTIC ERROR: duplicate repository lock {repository_id!r}")
            commit = entry["resolved_commit"]
            if not FULL_GIT_OBJECT_ID.fullmatch(commit):
                raise UserInputError(
                    f"Repository lock POLICY ERROR for {repository_id}: resolved_commit must be a lowercase full 40-hex immutable Git object ID; branches, tags, HEAD, and short SHAs are not commits"
                )
            repositories[repository_id] = entry
        else:
            component_id = entry["component_id"]
            if component_id not in known_components:
                raise UserInputError(f"Implementation lock CROSS-REFERENCE ERROR: unknown component {component_id!r}")
            if component_id in implementations:
                raise UserInputError(f"Implementation lock SEMANTIC ERROR: duplicate component lock {component_id!r}")
            resolved_version = entry["resolved_version"]
            if not IMMUTABLE_IMPLEMENTATION_VERSION.fullmatch(resolved_version):
                raise UserInputError(
                    f"Implementation lock POLICY ERROR for {component_id}: resolved_version must be an exact semantic version or sha256 digest, not a moving ref"
                )
            implementations[component_id] = entry

    return LockData(document["schema_version"], repositories, implementations)


def load_lock(path: Path, architecture: Architecture) -> LockData:
    document = read_json(path.resolve(), purpose="repository/version lock")
    return validate_lock_document(document, architecture)
