# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pure, deterministic remediation planning and model-only approval semantics."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .graph import find_cycle
from .models import UserInputError


PLAN_SCHEMA_VERSION = "1.0.0"
PLAN_VERSION = "1.0.0"
APPROVAL_SCHEMA_VERSION = "1.0.0"
RISK_CLASSES = {"LOW", "MODERATE", "HIGH", "CRITICAL"}
APPROVAL_CLASSES = {
    "NO_APPROVAL_NEEDED",
    "OPERATOR_APPROVAL",
    "ELEVATED_OPERATOR_APPROVAL",
    "MANUAL_EXTERNAL_APPROVAL",
    "PROHIBITED_AUTOMATICALLY",
}
APPROVAL_STATES = {
    "NOT_REQUESTED",
    "REQUIRED",
    "APPROVED",
    "DENIED",
    "EXPIRED",
    "STALE",
    "NOT_APPLICABLE",
}
PRECONDITION_STATES = {"SATISFIED", "UNVERIFIED", "UNSATISFIED", "NOT_APPLICABLE"}
ROLLBACK_CLASSES = {
    "NOT_REQUIRED",
    "DEFINED_REQUIRED",
    "BACKUP_REQUIRED",
    "MANUAL_RECOVERY_REQUIRED",
    "NO_SAFE_AUTOMATIC_ROLLBACK",
}
FAILURE_CLASSES = {"STOP", "ROLLBACK_REQUIRED", "MANUAL_RECOVERY_REQUIRED", "REASSESS_REQUIRED"}
MUTATION_CLASSES = {"HOST_MUTATION", "APPLICATION_MUTATION", "EXTERNAL_MUTATION"}
PROHIBITED_EXECUTABLE_FIELDS = {
    "argv",
    "automatic_remediation",
    "command",
    "docker_command",
    "script",
    "shell",
    "sudo_command",
    "systemctl_command",
}
PRIVATE_IDENTITY_FIELDS = {
    "address",
    "fqdn",
    "host_name",
    "hostname",
    "ip",
    "ip_address",
    "mac",
    "mac_address",
    "serial",
    "tailnet",
    "wwn",
}
_PRIVATE_IPV4 = re.compile(
    r"(?<!\d)(?:10(?:\.\d{1,3}){3}|127(?:\.\d{1,3}){3}|169\.254(?:\.\d{1,3}){2}|"
    r"192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(?!\d)"
)
_MAC = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])")
_CREDENTIAL = re.compile(
    r"(?i)(?:-----BEGIN .*PRIVATE KEY-----|[a-z][a-z0-9+.-]*://[^/@\s:]+:[^/@\s]+@|"
    r"\b(?:password|passwd|api[_-]?key|access[_-]?token|secret[_-]?value)\s*[:=]\s*\S+)"
)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _walk(value: Any, location: str = "$") -> Iterable[tuple[str, str | None, Any]]:
    if isinstance(value, dict):
        for key in sorted(value):
            child_location = f"{location}.{key}"
            yield child_location, key, value[key]
            yield from _walk(value[key], child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_location = f"{location}[{index}]"
            yield child_location, None, child
            yield from _walk(child, child_location)


def assert_publication_safe(value: Any, *, purpose: str) -> None:
    """Reject executable fields, secret-looking values, and private host identity."""
    for location, key, child in _walk(value):
        lowered = key.lower() if isinstance(key, str) else None
        if lowered in PROHIBITED_EXECUTABLE_FIELDS:
            raise UserInputError(f"{purpose} contains forbidden executable field at {location}")
        if lowered in PRIVATE_IDENTITY_FIELDS:
            raise UserInputError(f"{purpose} contains private host identity field at {location}")
        if isinstance(child, str):
            if _CREDENTIAL.search(child):
                raise UserInputError(f"{purpose} contains credential-like material at {location}")
            if _PRIVATE_IPV4.search(child) or _MAC.search(child):
                raise UserInputError(f"{purpose} contains private network identity at {location}")


def content_fingerprint(value: Any, *, purpose: str) -> str:
    assert_publication_safe(value, purpose=purpose)
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _ids(items: list[dict[str, Any]]) -> list[str]:
    return [item.get("id") for item in items if isinstance(item, dict)]


def planning_policy_errors(
    policy: dict[str, Any], requirement_policy: dict[str, Any]
) -> list[tuple[str, str, str]]:
    """Return stable semantic policy errors after JSON Schema validation."""
    errors: list[tuple[str, str, str]] = []
    vocabularies = {
        "risk_classes": RISK_CLASSES,
        "approval_classes": APPROVAL_CLASSES,
        "approval_states": APPROVAL_STATES,
        "precondition_states": PRECONDITION_STATES,
        "rollback_classes": ROLLBACK_CLASSES,
        "failure_classes": FAILURE_CLASSES,
    }
    for name, expected in vocabularies.items():
        actual = set(_ids(policy[name]))
        if actual != expected:
            errors.append(("planning-vocabulary", name, f"expected {sorted(expected)}, got {sorted(actual)}"))
        duplicates = sorted(item for item, count in Counter(_ids(policy[name])).items() if count > 1)
        if duplicates:
            errors.append(("duplicate-planning-vocabulary", name, f"duplicate IDs: {', '.join(duplicates)}"))

    scope_ids = set(_ids(policy["scope_classes"]))
    action_ids = _ids(policy["action_classes"])
    action_id_set = set(action_ids)
    for duplicate in sorted(item for item, count in Counter(action_ids).items() if count > 1):
        errors.append(("duplicate-action-class", duplicate, "action class IDs must be unique"))
    for action in policy["action_classes"]:
        action_id = action["id"]
        if action["default_risk"] not in RISK_CLASSES:
            errors.append(("unknown-risk-class", action_id, action["default_risk"]))
        unknown_scopes = sorted(set(action["scopes"]) - scope_ids)
        if unknown_scopes:
            errors.append(("unknown-scope-class", action_id, ", ".join(unknown_scopes)))
        unknown_approvals = sorted(set(action["required_approval_classes"]) - APPROVAL_CLASSES)
        if unknown_approvals:
            errors.append(("unknown-approval-class", action_id, ", ".join(unknown_approvals)))
        if action["rollback_class"] not in ROLLBACK_CLASSES:
            errors.append(("unknown-rollback-class", action_id, action["rollback_class"]))
        if action["failure_behavior"] not in FAILURE_CLASSES:
            errors.append(("unknown-failure-class", action_id, action["failure_behavior"]))
        if action["mutation_class"] in MUTATION_CLASSES and not action["required_approval_classes"]:
            errors.append(("mutation-without-approval", action_id, "all mutation classes require explicit approval"))
        if action["default_risk"] == "CRITICAL" and action["future_automatic_execution"] != "NEVER":
            errors.append(("critical-automatic-action", action_id, "critical action classes must remain NEVER automatic"))
        if "PROHIBITED_AUTOMATICALLY" in action["required_approval_classes"] and action["future_automatic_execution"] != "NEVER":
            errors.append(("prohibited-action-automatic", action_id, "prohibited action classes must remain NEVER automatic"))
        for expectation in [*action["preconditions"], *action["validation_expectations"]]:
            if expectation["initial_state"] not in PRECONDITION_STATES:
                errors.append(("unknown-precondition-state", action_id, expectation["initial_state"]))

    requirement_ids = {item["id"] for item in requirement_policy["requirements"]}
    rule_requirements = [item["requirement_id"] for item in policy["finding_rules"]]
    proposal_ids = [item["proposal_id"] for item in policy["finding_rules"]]
    decision_ids = [item["decision"]["id"] for item in policy["finding_rules"] if "decision" in item]
    for duplicate in sorted(item for item, count in Counter(rule_requirements).items() if count > 1):
        errors.append(("duplicate-finding-rule", duplicate, "requirement may have only one planning rule"))
    for duplicate in sorted(item for item, count in Counter(proposal_ids).items() if count > 1):
        errors.append(("duplicate-proposal-id", duplicate, "proposal IDs must be unique"))
    for duplicate in sorted(item for item, count in Counter(decision_ids).items() if count > 1):
        errors.append(("duplicate-decision-id", duplicate, "decision IDs must be unique"))
    proposal_id_set = set(proposal_ids)
    for rule in policy["finding_rules"]:
        if rule["requirement_id"] not in requirement_ids:
            errors.append(("unknown-rule-requirement", rule["requirement_id"], "no such host requirement"))
        if rule["disposition"] == "ACTION" and rule.get("action_class") not in action_id_set:
            errors.append(("unknown-action-class", rule["proposal_id"], str(rule.get("action_class"))))
        if (
            rule["disposition"] == "ACTION"
            and rule.get("decision", {}).get("id") == rule["proposal_id"]
        ):
            errors.append(
                (
                    "decision-action-identity-collision",
                    rule["proposal_id"],
                    "policy decision ID must differ from the future mutation proposal ID",
                )
            )
        for dependency in rule.get("depends_on_proposals", []):
            if dependency not in proposal_id_set:
                errors.append(("missing-rule-dependency", rule["proposal_id"], dependency))
    try:
        assert_publication_safe(policy, purpose="remediation planning policy")
    except UserInputError as exc:
        errors.append(("unsafe-planning-policy", "manifests/remediation-actions.json", str(exc)))
    return sorted(errors)


def validate_planning_policy(policy: dict[str, Any], requirement_policy: dict[str, Any]) -> None:
    errors = planning_policy_errors(policy, requirement_policy)
    if errors:
        code, location, message = errors[0]
        raise UserInputError(f"Invalid remediation planning policy [{code}] {location}: {message}")


def _resolved_identity_payload(plan: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "contract_version",
        "selected_profile",
        "component_policy",
        "components",
        "repository_locks",
        "implementation_locks",
        "dependency_order",
        "configuration_requirements",
        "secret_references",
        "state_declarations",
        "readiness_gates",
        "unresolved_external_blockers",
    )
    return {key: plan[key] for key in keys}


def _drift_identity_payload(report: dict[str, Any]) -> dict[str, Any]:
    finding_keys = (
        "id",
        "category",
        "requirement_state",
        "comparison",
        "expected",
        "observed_status",
        "observed",
        "result",
        "severity",
        "lifecycle",
        "remediation",
    )
    return {
        "requirement_policy_version": report["requirement_policy_version"],
        "profile": report["profile"],
        "findings": [
            {key: finding.get(key) for key in finding_keys}
            for finding in sorted(report["findings"], key=lambda item: item["id"])
        ],
    }


def _classification(action_count: int, decision_count: int, investigation_count: int) -> str:
    kinds = sum(bool(value) for value in (action_count, decision_count, investigation_count))
    if kinds > 1:
        return "MIXED"
    if action_count:
        return "ACTIONABLE_DRIFT"
    if investigation_count:
        return "EVIDENCE_INCOMPLETE"
    if decision_count:
        return "DECISIONS_ONLY"
    return "DRIFT_FREE"


def _decision_record(
    rule: dict[str, Any] | None,
    finding: dict[str, Any],
    profile: str,
) -> dict[str, Any]:
    """Render policy-decision identity/text separately from a future action proposal."""
    if rule is None:
        decision_id = f"decide-{finding['id']}"
        what = finding["remediation"]["guidance"]
        why = finding["reason"]
    else:
        presentation = rule.get("decision", {})
        decision_id = presentation.get("id", rule["proposal_id"])
        what = presentation.get("summary_by_profile", {}).get(
            profile, presentation.get("summary", rule["summary"])
        )
        why = presentation.get("why_by_profile", {}).get(
            profile, presentation.get("why", finding["reason"])
        )
    return {
        "id": decision_id,
        "requirement_id": finding["id"],
        "status": "HUMAN_POLICY_DECISION_REQUIRED",
        "what": what,
        "why": why,
        "approval_class": "MANUAL_EXTERNAL_APPROVAL",
        "host_mutation_proposed": False,
    }


def validate_action_graph(actions: list[dict[str, Any]]) -> None:
    action_ids = [item.get("id") for item in actions]
    if len(action_ids) != len(set(action_ids)):
        raise UserInputError("Remediation action IDs must be unique")
    known = set(action_ids)
    edges: list[tuple[str, str]] = []
    for action in actions:
        for dependency in action.get("depends_on", []):
            if dependency not in known:
                raise UserInputError(
                    f"Remediation action {action['id']!r} has missing dependency {dependency!r}"
                )
            edges.append((dependency, action["id"]))
    cycle = find_cycle(known, edges)
    if cycle:
        raise UserInputError(f"Remediation action dependency cycle: {' -> '.join(cycle)}")


_PLAN_FINGERPRINT_FIELDS = (
    "schema_version",
    "plan_version",
    "plan_policy_version",
    "profile",
    "source_policy_version",
    "source_resolved_plan_identity",
    "source_drift_identity",
    "created_from_state_classification",
    "findings",
    "actions",
    "decisions",
    "investigations",
    "blocking_conditions",
    "external_readiness",
)


def plan_fingerprint(plan: dict[str, Any]) -> str:
    payload = {key: plan[key] for key in _PLAN_FINGERPRINT_FIELDS}
    return content_fingerprint(payload, purpose="remediation plan fingerprint payload")


def _expectations(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"id": item["id"], "description": item["description"], "state": item["initial_state"]}
        for item in sorted(items, key=lambda value: value["id"])
    ]


def generate_remediation_plan(
    resolved_plan: dict[str, Any],
    drift_report: dict[str, Any],
    requirement_policy: dict[str, Any],
    planning_policy: dict[str, Any],
    *,
    plan_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an in-memory plan. This function has no observation or execution path."""
    validate_planning_policy(planning_policy, requirement_policy)
    assert_publication_safe(resolved_plan, purpose="resolved plan")
    assert_publication_safe(drift_report, purpose="drift report")
    profile = resolved_plan.get("selected_profile")
    if drift_report.get("kind") != "KALVIN_HOST_DRIFT_REPORT":
        raise UserInputError("Planning input is not a KALVIN_HOST_DRIFT_REPORT")
    if profile != drift_report.get("profile"):
        raise UserInputError("Resolved plan and drift report profiles do not match")
    if requirement_policy.get("policy_version") != drift_report.get("requirement_policy_version"):
        raise UserInputError("Requirement policy version does not match the drift report")
    if planning_policy.get("execution_available") is not False or planning_policy.get("operational") is not False:
        raise UserInputError("Phase 4G planning policy must remain non-operational")

    rules = {item["requirement_id"]: item for item in planning_policy["finding_rules"]}
    classes = {item["id"]: item for item in planning_policy["action_classes"]}
    active_proposal_ids: set[str] = set()
    findings: list[dict[str, str]] = []
    actions: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    investigations: list[dict[str, Any]] = []
    blockers: list[dict[str, str]] = []

    for finding in sorted(drift_report["findings"], key=lambda item: item["id"]):
        result = finding["result"]
        planning_classification = "NO_REMEDIATION"
        rule = rules.get(finding["id"])
        if result == "DECISION_PENDING":
            planning_classification = "HUMAN_POLICY_DECISION_REQUIRED"
            decisions.append(_decision_record(rule, finding, profile))
        elif result == "UNKNOWN":
            planning_classification = "INVESTIGATION_REQUIRED"
            investigations.append(
                {
                    "id": f"investigate-{finding['id']}",
                    "requirement_id": finding["id"],
                    "status": "INVESTIGATION_REQUIRED",
                    "missing_evidence": f"Required observation evidence is {finding['observed_status']}.",
                    "safe_observation_required": finding["remediation"]["guidance"],
                    "trust_boundary_approval": "NO_APPROVAL_NEEDED",
                    "host_mutation_proposed": False,
                }
            )
        elif (
            result == "UNSATISFIED"
            and finding["requirement_state"] == "REQUIRED"
            and finding["severity"] == "BLOCKING"
        ):
            if rule is None:
                planning_classification = "BLOCKED_NO_RULE"
                blockers.append(
                    {
                        "id": f"unplanned-{finding['id']}",
                        "status": "ACTIVE",
                        "reason": "Blocking drift has no approved declarative planning rule.",
                    }
                )
            elif rule["disposition"] == "HUMAN_POLICY_DECISION_REQUIRED":
                planning_classification = "HUMAN_POLICY_DECISION_REQUIRED"
                decisions.append(_decision_record(rule, finding, profile))
            else:
                action_class = classes[rule["action_class"]]
                if not action_class["phase4g_may_plan"]:
                    planning_classification = "BLOCKED_NO_RULE"
                    blockers.append(
                        {
                            "id": f"forbidden-plan-{finding['id']}",
                            "status": "ACTIVE",
                            "reason": "The action class is not plannable in Phase 4G.",
                        }
                    )
                else:
                    planning_classification = "REMEDIATION_PROPOSED"
                    active_proposal_ids.add(rule["proposal_id"])
                    preconditions = _expectations(action_class["preconditions"])
                    validation = _expectations(action_class["validation_expectations"])
                    approval = {
                        "action_id": rule["proposal_id"],
                        "classes": sorted(action_class["required_approval_classes"]),
                        "state": "REQUIRED",
                        "plan_binding": "EXACT_PLAN_FINGERPRINT_REQUIRED",
                    }
                    rollback_status = (
                        "NOT_APPLICABLE" if action_class["rollback_class"] == "NOT_REQUIRED" else "UNVERIFIED"
                    )
                    actions.append(
                        {
                            "id": rule["proposal_id"],
                            "source_finding_ids": [finding["id"]],
                            "action_class": action_class["id"],
                            "action_definition_fingerprint": content_fingerprint(
                                {"class": action_class, "rule": rule},
                                purpose=f"action definition {rule['proposal_id']}",
                            ),
                            "affected_domain": action_class["affected_domain"],
                            "mutation_class": action_class["mutation_class"],
                            "what": rule["summary"],
                            "why": finding["explanation"],
                            "risk": action_class["default_risk"],
                            "scopes": sorted(action_class["scopes"]),
                            "approval": approval,
                            "preconditions": preconditions,
                            "validation": validation,
                            "rollback": {
                                "class": action_class["rollback_class"],
                                "status": rollback_status,
                                "expectation": action_class["rollback_expectation"],
                            },
                            "failure_behavior": action_class["failure_behavior"],
                            "depends_on": sorted(rule.get("depends_on_proposals", [])),
                            "future_automatic_execution": action_class["future_automatic_execution"],
                            "execution_available": False,
                        }
                    )
        findings.append(
            {
                "requirement_id": finding["id"],
                "drift_result": result,
                "severity": finding["severity"],
                "planning_classification": planning_classification,
            }
        )

    actions.sort(key=lambda item: item["id"])
    decisions.sort(key=lambda item: item["id"])
    investigations.sort(key=lambda item: item["id"])
    for action in actions:
        action["depends_on"] = sorted(set(action["depends_on"]) & active_proposal_ids)
    validate_action_graph(actions)
    if profile == "storage":
        for action in actions:
            if action["action_class"] in {"APPLICATION_MIGRATION", "REPOSITORY_OR_VERSION_CHANGE"} or "APPLICATION" in action["scopes"]:
                raise UserInputError("Storage remediation planning may not contain application compute actions")

    preconditions = [
        {"action_id": action["id"], **item}
        for action in actions
        for item in action["preconditions"]
    ]
    validation = [
        {"action_id": action["id"], **item}
        for action in actions
        for item in action["validation"]
    ]
    rollback = [
        {"action_id": action["id"], **action["rollback"]}
        for action in actions
    ]
    external_gates = sorted(
        (
            {"id": item["id"], "status": item["status"]}
            for item in drift_report.get("external_readiness_summary", {}).get("gates", [])
        ),
        key=lambda item: item["id"],
    )
    state_classification = _classification(len(actions), len(decisions), len(investigations))
    plan: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "kind": "KALVIN_REMEDIATION_PLAN",
        "plan_version": PLAN_VERSION,
        "plan_policy_version": planning_policy["policy_version"],
        "profile": profile,
        "source_policy_version": requirement_policy["policy_version"],
        "source_resolved_plan_identity": content_fingerprint(
            _resolved_identity_payload(resolved_plan), purpose="resolved plan identity"
        ),
        "source_drift_identity": content_fingerprint(
            _drift_identity_payload(drift_report), purpose="drift report identity"
        ),
        "created_from_state_classification": state_classification,
        "plan_status": "PLAN_BLOCKED" if blockers else ("PLAN_GENERATED" if actions else "NO_ACTIONS_REQUIRED"),
        "findings": findings,
        "action_count": len(actions),
        "decision_count": len(decisions),
        "investigation_count": len(investigations),
        "actions": actions,
        "decisions": decisions,
        "investigations": investigations,
        "action_dependencies": [
            {"action_id": item["id"], "depends_on": item["depends_on"]} for item in actions
        ],
        "risk": [
            {"action_id": item["id"], "class": item["risk"], "basis": "Default change-impact risk from the versioned action class."}
            for item in actions
        ],
        "scope": [
            {"action_id": item["id"], "classes": item["scopes"], "affected_domain": item["affected_domain"]}
            for item in actions
        ],
        "approval_requirements": [item["approval"] for item in actions],
        "preconditions": preconditions,
        "validation": validation,
        "rollback": rollback,
        "blocking_conditions": sorted(blockers, key=lambda item: item["id"]),
        "external_readiness": {
            "classification": "EXTERNAL_NOT_HOST_REMEDIATION",
            "gates": external_gates,
        },
        "execution_available": False,
        "execution_status": "NOT_IMPLEMENTED",
        "notice": "REMEDIATION PLAN ONLY — EXECUTION NOT AVAILABLE — NO CHANGES PERFORMED",
    }
    fingerprint = plan_fingerprint(plan)
    plan["plan_fingerprint"] = fingerprint
    plan["plan_id"] = "remediation-plan-sha256-" + fingerprint.removeprefix("sha256:")
    validate_remediation_plan(plan, planning_policy, plan_schema=plan_schema)
    return plan


def validate_remediation_plan(
    plan: dict[str, Any],
    planning_policy: dict[str, Any],
    *,
    plan_schema: dict[str, Any] | None = None,
) -> None:
    assert_publication_safe(plan, purpose="remediation plan")
    if plan_schema is not None:
        errors = sorted(
            Draft202012Validator(plan_schema).iter_errors(plan),
            key=lambda item: (list(item.absolute_path), item.message),
        )
        if errors:
            raise UserInputError(f"Invalid remediation plan schema: {errors[0].message}")
    if plan.get("execution_available") is not False:
        raise UserInputError("Phase 4G remediation plan execution_available must be false")
    if plan.get("execution_status") != "NOT_IMPLEMENTED":
        raise UserInputError("Phase 4G execution engine must remain NOT_IMPLEMENTED")
    if plan.get("action_count") != len(plan.get("actions", [])):
        raise UserInputError("Remediation plan action_count does not match actions")
    class_by_id = {item["id"]: item for item in planning_policy["action_classes"]}
    scope_ids = set(_ids(planning_policy["scope_classes"]))
    for action in plan.get("actions", []):
        action_class = class_by_id.get(action.get("action_class"))
        if action_class is None:
            raise UserInputError(f"Unknown remediation action class {action.get('action_class')!r}")
        if action.get("risk") not in RISK_CLASSES:
            raise UserInputError(f"Unknown remediation risk class {action.get('risk')!r}")
        if set(action.get("scopes", [])) - scope_ids:
            raise UserInputError(f"Unknown remediation scope on action {action.get('id')!r}")
        approval = action.get("approval", {})
        if set(approval.get("classes", [])) - APPROVAL_CLASSES:
            raise UserInputError(f"Unknown remediation approval class on action {action.get('id')!r}")
        if action.get("mutation_class") in MUTATION_CLASSES and approval.get("state") != "REQUIRED":
            raise UserInputError("All Phase 4G mutation proposals must keep approval state REQUIRED")
        if action.get("execution_available") is not False:
            raise UserInputError("Action execution_available must be false in Phase 4G")
        if (
            "PROHIBITED_AUTOMATICALLY" in approval.get("classes", [])
            or action.get("risk") == "CRITICAL"
        ) and action.get("future_automatic_execution") != "NEVER":
            raise UserInputError("Destructive or critical action cannot become automatic")
        if action.get("rollback", {}).get("class") not in ROLLBACK_CLASSES:
            raise UserInputError(f"Unknown rollback class on action {action.get('id')!r}")
        if action.get("failure_behavior") not in FAILURE_CLASSES:
            raise UserInputError(f"Unknown failure behavior on action {action.get('id')!r}")
    validate_action_graph(plan.get("actions", []))
    expected = plan_fingerprint(plan)
    if plan.get("plan_fingerprint") != expected:
        raise UserInputError("Remediation plan fingerprint does not match canonical content")
    if plan.get("plan_id") != "remediation-plan-sha256-" + expected.removeprefix("sha256:"):
        raise UserInputError("Remediation plan ID does not match its fingerprint")


def validate_approval_record(
    record: dict[str, Any],
    *,
    approval_schema: dict[str, Any] | None = None,
) -> None:
    assert_publication_safe(record, purpose="approval record")
    if approval_schema is not None:
        errors = sorted(
            Draft202012Validator(approval_schema).iter_errors(record),
            key=lambda item: (list(item.absolute_path), item.message),
        )
        if errors:
            raise UserInputError(f"Invalid approval record schema: {errors[0].message}")
    if record.get("approval_class") not in APPROVAL_CLASSES - {"NO_APPROVAL_NEEDED"}:
        raise UserInputError(f"Unknown approval class {record.get('approval_class')!r}")
    if record.get("state") not in APPROVAL_STATES - {"NOT_REQUESTED", "REQUIRED", "NOT_APPLICABLE"}:
        raise UserInputError(f"Invalid persisted approval state {record.get('state')!r}")
    if record.get("decision") == "APPROVE" and record.get("state") not in {"APPROVED", "EXPIRED", "STALE"}:
        raise UserInputError("Approval decision and state disagree")
    if record.get("decision") == "DENY" and record.get("state") != "DENIED":
        raise UserInputError("Denial decision and state disagree")
    validity = record.get("validity", {})
    if validity.get("mode") == "EXPIRES" and not validity.get("expires_at"):
        raise UserInputError("Expiring approval requires an expiry value")
    if validity.get("mode") != "EXPIRES" and validity.get("expires_at") is not None:
        raise UserInputError("Non-expiring approval must not contain an expiry value")
    if record.get("synthetic_model_only") is not True:
        raise UserInputError("Phase 4G approval records must remain synthetic/model-only")


def approval_state_for_plan(
    plan: dict[str, Any],
    record: dict[str, Any],
    *,
    approval_schema: dict[str, Any] | None = None,
) -> str:
    """Evaluate binding/staleness only; never persist approval or authorize execution."""
    validate_approval_record(record, approval_schema=approval_schema)
    if (
        record["plan_fingerprint"] != plan["plan_fingerprint"]
        or record["plan_policy_version"] != plan["plan_policy_version"]
    ):
        return "STALE"
    return record["state"]
