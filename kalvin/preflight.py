# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pure comparison of resolved profile requirements and sanitized observations."""

from __future__ import annotations

import re
from typing import Any

from .models import UserInputError


OBSERVATION_PATHS = {
    "operating_system.family": ("operating_system", "family"),
    "operating_system.architecture": ("operating_system", "architecture"),
    "cpu.logical_cpu_count": ("cpu", "logical_cpu_count"),
    "memory.total_bytes": ("memory", "total_bytes"),
    "block_storage.status": ("block_storage", "status"),
    "block_storage.devices": ("block_storage", "devices"),
    "filesystems.status": ("filesystems", "status"),
    "systemd.available": ("systemd", "available"),
    "executables.git.present": ("executables", "git", "present"),
    "runtimes.python.version": ("runtimes", "python", "version"),
    "docker.cli.present": ("docker", "cli", "present"),
    "network.default_route.present": ("network", "default_route", "present"),
}


def _lookup(observed: dict[str, Any], path: str) -> Any:
    if path not in OBSERVATION_PATHS:
        raise UserInputError(f"Unsupported host-requirement observation path {path!r}")
    value: Any = observed
    for part in OBSERVATION_PATHS[path]:
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _version(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, str) or re.fullmatch(r"\d+(?:\.\d+)*", value) is None:
        return None
    return tuple(int(part) for part in value.split("."))


def _evaluate(requirement: dict[str, Any], profile: str, observed: dict[str, Any]) -> dict[str, Any]:
    level = requirement["profiles"][profile]
    observed_value = _lookup(observed, requirement["observation_path"])
    if level == "NOT_APPLICABLE":
        status, explanation = "NOT_APPLICABLE", "Profile declares this capability not applicable."
    elif level == "NOT_YET_SPECIFIED" or requirement["comparison"] == "NOT_YET_SPECIFIED":
        status, explanation = "UNKNOWN", "Requirement threshold is NOT YET SPECIFIED; human architecture decision required."
    elif observed_value is None:
        status, explanation = "UNKNOWN", "Observation is unavailable or unknown; absence is not treated as false."
    elif requirement["comparison"] == "EQUALS":
        status = "SATISFIED" if observed_value == requirement["expected"] else "UNSATISFIED"
        explanation = "Observed capability matches the declaration." if status == "SATISFIED" else "Observed capability does not match the declaration."
    elif requirement["comparison"] == "VERSION_AT_LEAST":
        actual, expected = _version(observed_value), _version(requirement["expected"])
        if actual is None or expected is None:
            status, explanation = "UNKNOWN", "Version could not be compared safely."
        else:
            status = "SATISFIED" if actual >= expected else "UNSATISFIED"
            explanation = "Observed version meets the declared minimum." if status == "SATISFIED" else "Observed version is below the declared minimum."
    else:
        raise UserInputError(f"Unsupported host-requirement comparison {requirement['comparison']!r}")
    return {
        "id": requirement["id"],
        "requirement": level,
        "status": status,
        "observation_path": requirement["observation_path"],
        "expected": requirement["expected"],
        "observed": observed_value,
        "explanation": explanation,
    }


def compare_preflight(
    resolved_plan: dict[str, Any], observed_host: dict[str, Any], requirements: dict[str, Any]
) -> dict[str, Any]:
    """Compare in memory without changing desired, resolved, or observed input."""
    if observed_host.get("kind") != "KALVIN_OBSERVED_HOST":
        raise UserInputError("Observed host input is not a KALVIN_OBSERVED_HOST document")
    profile = resolved_plan["selected_profile"]
    checks = sorted(
        (_evaluate(requirement, profile, observed_host) for requirement in requirements["requirements"]),
        key=lambda item: item["id"],
    )
    blocking = [item for item in checks if item["requirement"] == "REQUIRED"]
    if any(item["status"] == "UNSATISFIED" for item in blocking):
        host_status = "UNSATISFIED"
    elif any(item["status"] == "UNKNOWN" for item in blocking):
        host_status = "UNKNOWN"
    else:
        host_status = "SATISFIED"
    external_gates = [
        {"id": item["id"], "status": item["status"]}
        for item in resolved_plan["unresolved_external_blockers"]
        if item["type"] == "READINESS_GATE"
    ]
    return {
        "schema_version": "1.0.0",
        "kind": "KALVIN_HOST_PREFLIGHT",
        "profile": profile,
        "host_preflight_status": host_status,
        "production_readiness": resolved_plan["production_readiness"],
        "checks": checks,
        "external_readiness_gates": external_gates,
        "resolved_plan_summary": {
            "resolution_status": resolved_plan["resolution_status"],
            "components": [item["id"] for item in resolved_plan["components"]],
            "observed_or_deployed_state": resolved_plan["observed_or_deployed_state"],
        },
        "observed_host": observed_host,
        "correction_performed": False,
    }
