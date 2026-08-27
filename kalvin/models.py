# SPDX-License-Identifier: AGPL-3.0-or-later
"""Small data models shared by the read-only engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, order=True)
class Finding:
    """One deterministic, human-readable architecture finding."""

    category: str
    code: str
    location: str
    message: str

    def render(self) -> str:
        return f"{self.category} [{self.code}] {self.location}: {self.message}"


@dataclass
class ValidationResult:
    """Validation outcome separated from resolution/readiness status."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.findings

    def add(self, category: str, code: str, location: str, message: str) -> None:
        self.findings.append(Finding(category, code, location, message))

    def ordered(self) -> list[Finding]:
        return sorted(set(self.findings))


@dataclass
class Architecture:
    """In-memory architecture documents; no observed host state."""

    root: Path
    catalogs: dict[str, dict[str, Any]]
    profiles: dict[str, dict[str, Any]]
    schemas: dict[str, dict[str, Any]]
    document_paths: dict[str, Path]


class UserInputError(Exception):
    """Expected user/manifest/lock failure with an exit-code-2 message."""


class InternalEngineError(Exception):
    """Unexpected engine failure suitable for an exit-code-3 diagnostic."""
