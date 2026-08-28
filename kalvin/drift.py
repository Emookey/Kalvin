# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic, guidance-only host requirement and drift evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from .models import UserInputError


PROFILE_IDS = ("lab", "core", "storage")
REQUIREMENT_STATES = {
    "REQUIRED",
    "OPTIONAL",
    "RECOMMENDED",
    "NOT_APPLICABLE",
    "HUMAN_DECISION_REQUIRED",
}
DRIFT_RESULTS = {"SATISFIED", "UNSATISFIED", "UNKNOWN", "NOT_APPLICABLE", "DECISION_PENDING"}
SEVERITIES = {"INFO", "WARNING", "BLOCKING"}
OBSERVATION_STATUSES = {"OBSERVED", "UNAVAILABLE", "INSUFFICIENT_PERMISSION", "UNSUPPORTED", "UNKNOWN"}


@dataclass(frozen=True)
class ObservationSpec:
    value_path: tuple[str, ...]


OBSERVATION_PATHS = {
    "operating_system.family": ObservationSpec(("operating_system", "family")),
    "operating_system.version": ObservationSpec(("operating_system", "version")),
    "operating_system.architecture": ObservationSpec(("operating_system", "architecture")),
    "cpu.logical_cpu_count": ObservationSpec(("cpu", "logical_cpu_count")),
    "memory.total_bytes": ObservationSpec(("memory", "total_bytes")),
    "block_storage.status": ObservationSpec(("block_storage", "status")),
    "block_storage.devices": ObservationSpec(("block_storage", "devices")),
    "filesystems.status": ObservationSpec(("filesystems", "status")),
    "systemd.available": ObservationSpec(("systemd", "available")),
    "executables.git.present": ObservationSpec(("executables", "git", "present")),
    "runtimes.python.version": ObservationSpec(("runtimes", "python", "version")),
    "docker.cli.present": ObservationSpec(("docker", "cli", "present")),
    "services.docker.state": ObservationSpec(("services", "docker", "state")),
    "network.default_route.present": ObservationSpec(("network", "default_route", "present")),
}


def _version(value: Any) -> tuple[int, ...] | None:
    if not isinstance(value, str) or re.fullmatch(r"\d+(?:\.\d+)*", value) is None:
        return None
    return tuple(int(part) for part in value.split("."))


def _observation(observed: dict[str, Any], path: str) -> tuple[str, Any]:
    spec = OBSERVATION_PATHS.get(path)
    if spec is None:
        raise UserInputError(f"Unsupported host-requirement observation path {path!r}")
    value: Any = observed
    status = "UNKNOWN"
    for part in spec.value_path:
        if isinstance(value, dict) and value.get("status") in OBSERVATION_STATUSES:
            status = value["status"]
        if not isinstance(value, dict) or part not in value:
            return "UNKNOWN", None
        value = value[part]
    if isinstance(value, dict) and value.get("status") in OBSERVATION_STATUSES:
        status = value["status"]
    if value is None:
        return "UNKNOWN", None
    return status, value


def _compare(operator: str, observed: Any, expected: Any) -> bool | None:
    if operator == "EQUALS":
        if type(observed) is not type(expected):
            return False
        return observed == expected
    if operator == "VERSION_AT_LEAST":
        actual_version, expected_version = _version(observed), _version(expected)
        if actual_version is None or expected_version is None:
            return None
        return actual_version >= expected_version
    if operator == "AT_LEAST":
        if isinstance(observed, bool) or isinstance(expected, bool):
            return None
        if not isinstance(observed, (int, float)) or not isinstance(expected, (int, float)):
            return None
        return observed >= expected
    raise UserInputError(f"Unsupported host-requirement comparison {operator!r}")


def _remediations(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in policy["remediations"]}


def requirement_by_id(policy: dict[str, Any], requirement_id: str) -> dict[str, Any]:
    for requirement in policy["requirements"]:
        if requirement["id"] == requirement_id:
            return requirement
    available = ", ".join(sorted(item["id"] for item in policy["requirements"]))
    raise UserInputError(f"Unknown host requirement {requirement_id!r}; available requirements: {available}")


def requirements_for_profile(
    policy: dict[str, Any], profile: str, *, requirement_ids: Iterable[str] | None = None
) -> dict[str, Any]:
    """Return the selected declarative policy without observing a host."""
    if profile not in PROFILE_IDS:
        raise UserInputError(f"Unknown profile {profile!r}; available profiles: {', '.join(PROFILE_IDS)}")
    if requirement_ids is None:
        selected = list(policy["requirements"])
    else:
        selected = [requirement_by_id(policy, requirement_id) for requirement_id in requirement_ids]
    remediation_by_id = _remediations(policy)
    requirements = []
    for item in sorted(selected, key=lambda requirement: requirement["id"]):
        remediation = remediation_by_id[item["remediation_id"]]
        state = item["profiles"][profile]
        requirements.append(
            {
                "id": item["id"],
                "category": item["category"],
                "state": state,
                "description": item["description"],
                "comparison": item["comparison"],
                "expected": item["expected"],
                "observation_path": item["observation_path"],
                "evidence_class": item["evidence_class"],
                "evidence_source": item["evidence_source"],
                "reason": item["reason"],
                "lifecycle": item["lifecycle"],
                "decision_state": item["decision_state"],
                "applies_when_components": sorted(item["applies_when_components"]),
                "currently_blocks_host_compliance": state == "REQUIRED",
                "remediation": {
                    "id": remediation["id"],
                    "guidance": remediation["guidance"],
                    "action": "NONE",
                },
            }
        )
    return {
        "schema_version": "1.0.0",
        "kind": "KALVIN_PROFILE_HOST_REQUIREMENTS",
        "requirement_policy_version": policy["policy_version"],
        "profile": profile,
        "requirements": requirements,
        "action_performed": "NONE",
    }


def _severity(policy: dict[str, Any], state: str, result: str) -> str:
    severity = policy["severity_policy"]
    if result == "SATISFIED" or result == "NOT_APPLICABLE":
        return severity["satisfied"]
    if result == "DECISION_PENDING":
        return severity["decision_pending"]
    if state == "REQUIRED":
        return severity["required_unknown" if result == "UNKNOWN" else "required_unsatisfied"]
    if state == "RECOMMENDED":
        return severity["recommended_unknown" if result == "UNKNOWN" else "recommended_unsatisfied"]
    return severity["optional"]


def _evaluate_requirement(
    requirement: dict[str, Any],
    profile: str,
    observed: dict[str, Any],
    selected_components: set[str],
    policy: dict[str, Any],
    remediation_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    state = requirement["profiles"][profile]
    component_scope = set(requirement["applies_when_components"])
    observation_status = "NOT_EVALUATED"
    observed_value: Any = None

    if state == "NOT_APPLICABLE" or (component_scope and not component_scope & selected_components):
        result = "NOT_APPLICABLE"
        explanation = "The requirement does not apply to the selected profile/component set."
    elif state == "HUMAN_DECISION_REQUIRED" or requirement["comparison"] == "DECISION_PENDING":
        result = "DECISION_PENDING"
        explanation = "Architecture evidence is insufficient for enforcement; human approval is required."
    else:
        path = requirement["observation_path"]
        if not isinstance(path, str):
            raise UserInputError(f"Host requirement {requirement['id']!r} has no observable capability")
        observation_status, observed_value = _observation(observed, path)
        if observation_status != "OBSERVED":
            result = "UNKNOWN"
            observed_value = None
            explanation = f"Observation evidence is {observation_status}; absence is not treated as false."
        else:
            comparison = _compare(requirement["comparison"], observed_value, requirement["expected"])
            if comparison is None:
                result = "UNKNOWN"
                explanation = "Observed and expected values could not be compared safely."
            elif comparison:
                result = "SATISFIED"
                explanation = "Observed capability satisfies the declared policy."
            elif state == "OPTIONAL":
                result = "NOT_APPLICABLE"
                explanation = "The optional capability is absent or does not match; it is not required for this profile."
            else:
                result = "UNSATISFIED"
                explanation = "Observed capability does not satisfy the declared policy."

    remediation = remediation_by_id[requirement["remediation_id"]]
    return {
        "id": requirement["id"],
        "category": requirement["category"],
        "requirement_state": state,
        "comparison": requirement["comparison"],
        "expected": requirement["expected"],
        "observed_status": observation_status,
        "observed": observed_value,
        "result": result,
        "severity": _severity(policy, state, result),
        "evidence_class": requirement["evidence_class"],
        "evidence_source": requirement["evidence_source"],
        "reason": requirement["reason"],
        "lifecycle": requirement["lifecycle"],
        "explanation": explanation,
        "remediation": {"id": remediation["id"], "guidance": remediation["guidance"], "action": "NONE"},
        "action_performed": "NONE",
    }


def evaluate_host_drift(
    resolved_plan: dict[str, Any], observed_host: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    """Compare resolved intent with sanitized observation; perform no action."""
    if observed_host.get("kind") != "KALVIN_OBSERVED_HOST":
        raise UserInputError("Observed host input is not a KALVIN_OBSERVED_HOST document")
    profile = resolved_plan.get("selected_profile")
    if profile not in PROFILE_IDS:
        raise UserInputError(f"Unknown resolved profile {profile!r}")
    selected_components = {item["id"] for item in resolved_plan["components"]}
    remediation_by_id = _remediations(policy)
    findings = sorted(
        (
            _evaluate_requirement(
                requirement,
                profile,
                observed_host,
                selected_components,
                policy,
                remediation_by_id,
            )
            for requirement in policy["requirements"]
        ),
        key=lambda item: item["id"],
    )
    blocking_count = sum(item["severity"] == "BLOCKING" for item in findings)
    warning_count = sum(item["severity"] == "WARNING" for item in findings)
    decision_pending_count = sum(item["result"] == "DECISION_PENDING" for item in findings)
    required_unknown = any(
        item["requirement_state"] == "REQUIRED" and item["result"] == "UNKNOWN" for item in findings
    )
    if blocking_count:
        host_compliance = "UNSATISFIED"
    elif required_unknown:
        host_compliance = "UNKNOWN"
    else:
        host_compliance = "SATISFIED"
    if any(item["result"] == "UNSATISFIED" for item in findings):
        host_drift_status = "DRIFT_DETECTED"
    elif any(item["result"] == "UNKNOWN" for item in findings):
        host_drift_status = "EVIDENCE_INCOMPLETE"
    else:
        host_drift_status = "DRIFT_FREE"
    external_gates = sorted(
        (
            {"id": item["id"], "status": item["status"]}
            for item in resolved_plan["unresolved_external_blockers"]
            if item["type"] == "READINESS_GATE"
        ),
        key=lambda item: item["id"],
    )
    return {
        "schema_version": "1.0.0",
        "kind": "KALVIN_HOST_DRIFT_REPORT",
        "requirement_policy_version": policy["policy_version"],
        "profile": profile,
        "findings": findings,
        "summary": {
            "blocking_count": blocking_count,
            "warning_count": warning_count,
            "decision_pending_count": decision_pending_count,
            "unknown_count": sum(item["result"] == "UNKNOWN" for item in findings),
            "satisfied_count": sum(item["result"] == "SATISFIED" for item in findings),
        },
        "host_compliance": host_compliance,
        "host_drift_status": host_drift_status,
        "production_readiness": resolved_plan["production_readiness"],
        "external_readiness_summary": {
            "classification": "EXTERNAL_NOT_HOST_DRIFT",
            "gates": external_gates,
            "configuration_requirement_count": len(resolved_plan["configuration_requirements"]),
            "secret_reference_count": len(resolved_plan["secret_references"]),
        },
        "resolved_plan_summary": {
            "resolution_status": resolved_plan["resolution_status"],
            "components": sorted(selected_components),
            "observed_or_deployed_state": resolved_plan["observed_or_deployed_state"],
        },
        "report_notice": "DRIFT REPORT ONLY — NO CHANGES PERFORMED",
        "changes_performed": False,
    }
