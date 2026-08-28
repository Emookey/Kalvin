# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stable JSON and operator-oriented text presentation."""

from __future__ import annotations

import json
from typing import Any

from .models import ValidationResult


def stable_json(value: Any) -> str:
    """Return stable JSON for repeatable plans and synthetic host snapshots."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def validation_text(result: ValidationResult) -> str:
    if result.valid:
        return "Architecture validity: VALID\nDeclarative contracts: PASS\n"
    lines = ["Architecture validity: INVALID", f"Findings: {len(result.ordered())}"]
    lines.extend(f"- {item.render()}" for item in result.ordered())
    return "\n".join(lines) + "\n"


def validation_json(result: ValidationResult) -> str:
    return stable_json(
        {
            "architecture_validity": "VALID" if result.valid else "INVALID",
            "findings": [
                {
                    "category": item.category,
                    "code": item.code,
                    "location": item.location,
                    "message": item.message,
                }
                for item in result.ordered()
            ],
        }
    )


def _section(lines: list[str], title: str) -> None:
    if lines:
        lines.append("")
    lines.append(title)


def plan_text(plan: dict[str, Any]) -> str:
    lines: list[str] = []
    _section(lines, "Profile")
    lines.extend(
        [
            f"  Selected: {plan['selected_profile']}",
            f"  Role: {plan['profile_role']}",
            f"  Desired architecture: {plan['architecture_validity']}",
        ]
    )
    _section(lines, "Components")
    for item in plan["components"]:
        lines.append(f"  - {item['id']} ({item['requirement']}; owner {item['owner']})")
    lines.append(f"  Dependency order: {' -> '.join(plan['dependency_order'])}")

    _section(lines, "Repository versions")
    if not plan["repository_locks"]:
        lines.append("  - None selected")
    for item in plan["repository_locks"]:
        lines.append(f"  - {item['repository_id']} for {item['component']}: {item['desired_ref']} -> {item['resolved_commit']}")
    for item in plan["implementation_locks"]:
        lines.append(f"  - {item['component']} implementation: {item['desired_ref']} -> {item['resolved_version']}")

    _section(lines, "Dependencies")
    for label, key in (
        ("STARTUP", "startup"),
        ("HEALTH", "health"),
        ("READINESS", "readiness"),
        ("OPTIONAL INTEGRATION", "optional_integrations"),
    ):
        entries = plan["dependencies"][key]
        if not entries:
            lines.append(f"  {label}: none")
        for item in entries:
            selected = "selected" if item["selected"] else "not selected"
            lines.append(f"  {label}: {item['component']} -> {item['dependency']} ({selected})")

    _section(lines, "Configuration requirements")
    lines.append(f"  Precedence: {' -> '.join(plan['configuration_precedence'])}")
    for item in plan["configuration_requirements"]:
        status = "required" if item["required"] else "optional"
        lines.append(f"  - {item['id']} ({item['component']}; {item['source_layer']}; {status}; {item['conflict_policy']})")

    _section(lines, "Secret references")
    if not plan["secret_references"]:
        lines.append("  - None")
    for item in plan["secret_references"]:
        status = "REQUIRED" if item["required"] else "OPTIONAL"
        lines.append(f"  - {status} SECRET REFERENCE: {item['id']} ({item['component']}; value not read)")

    _section(lines, "State and backup policy")
    for item in plan["state_declarations"]:
        lines.append(f"  - {item['component']}.{item['id']}: {item['state_class']} / {item['backup_policy']} -> {item['filesystem_destination']} (declared intent only)")

    _section(lines, "Exposure")
    for item in plan["exposure"]:
        lines.append(f"  - {item['component']}: default {item['declared_default']}; ceiling {item['profile_ceiling']}")

    _section(lines, "Privileges")
    for item in plan["identity_and_privilege"]:
        lines.append(f"  - {item['component']}: {item['identity_class']} / {item['privilege_class']}")

    _section(lines, "Readiness gates")
    for item in plan["readiness_gates"]:
        lines.append(f"  - {item['id']}: {item['requirement']} / {item['verification_scope']} / {item['status']}")

    _section(lines, "Blockers")
    if not plan["unresolved_external_blockers"]:
        lines.append("  - None")
    for item in plan["unresolved_external_blockers"]:
        lines.append(f"  - {item['type']}: {item['id']} [{item['status']}]")

    _section(lines, "Overall result")
    lines.extend(
        [
            f"  Resolution: {plan['resolution_status']}",
            f"  Production readiness: {plan['production_readiness']}",
            "  Operational deployment: NONE (resolved plan only; no observed/deployed state)",
        ]
    )
    return "\n".join(lines) + "\n"


def observed_host_text(observed: dict[str, Any]) -> str:
    """Render sanitized capability categories without raw probe output."""
    lines = ["Observed host", "  Local observation only; no identity or addresses emitted"]
    os_data = observed["operating_system"]
    lines.extend(
        [
            "",
            "Operating system",
            f"  Status: {os_data['status']}",
            f"  Family/version: {os_data['family'] or 'UNKNOWN'} / {os_data['version'] or 'UNKNOWN'}",
            f"  Kernel/architecture: {os_data['kernel_release'] or 'UNKNOWN'} / {os_data['architecture'] or 'UNKNOWN'}",
        ]
    )
    cpu, memory = observed["cpu"], observed["memory"]
    lines.extend(
        [
            "",
            "CPU and memory",
            f"  CPU: {cpu['status']}; architecture {cpu['architecture'] or 'UNKNOWN'}; logical CPUs {cpu['logical_cpu_count'] if cpu['logical_cpu_count'] is not None else 'UNKNOWN'}",
            f"  Memory: {memory['status']}; total bytes {memory['total_bytes'] if memory['total_bytes'] is not None else 'UNKNOWN'}",
        ]
    )
    lines.extend(
        [
            "",
            "Storage and mounts",
            f"  Block storage: {observed['block_storage']['status']}; sanitized devices {len(observed['block_storage']['devices'])}",
            f"  Filesystems: {observed['filesystems']['status']}; sanitized mounts {len(observed['filesystems']['mounts'])}",
            "",
            "Services and runtimes",
            f"  systemd: {'AVAILABLE' if observed['systemd']['available'] else 'UNAVAILABLE'}",
            f"  Docker CLI/service: {observed['docker']['cli']['status']} / {observed['docker']['service']['state']}",
            f"  Python: {observed['runtimes']['python']['status']} / {observed['runtimes']['python']['version']}",
            "",
            "Network capability",
            f"  Links: {observed['network']['status']}; sanitized interfaces {len(observed['network']['links'])}",
            f"  Default route: {observed['network']['default_route']['status']} / {observed['network']['default_route']['present']}",
            "",
            "Result",
            "  OBSERVED STATE ONLY; no desired state changed and no host action performed",
        ]
    )
    return "\n".join(lines) + "\n"


def preflight_text(preflight: dict[str, Any]) -> str:
    lines = [
        "Host preflight",
        f"  Profile: {preflight['profile']}",
        f"  Host capability result: {preflight['host_preflight_status']}",
        f"  Production readiness: {preflight['production_readiness']}",
        "",
        "Capability checks",
    ]
    for item in preflight["checks"]:
        lines.append(f"  - {item['id']}: {item['requirement']} / {item['status']} — {item['explanation']}")
    lines.extend(["", "External application/platform gates"])
    if not preflight["external_readiness_gates"]:
        lines.append("  - None")
    for item in preflight["external_readiness_gates"]:
        lines.append(f"  - {item['id']}: {item['status']}")
    lines.extend(
        [
            "",
            "Result",
            "  Comparison only; no correction, deployment, persistence, or host change performed",
        ]
    )
    return "\n".join(lines) + "\n"


def _display(value: Any) -> str:
    if value is None:
        return "NOT SPECIFIED"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    return "SANITIZED STRUCTURED CAPABILITY"


def requirements_text(document: dict[str, Any]) -> str:
    lines = [
        "Host requirement policy",
        f"  Profile: {document['profile']}",
        f"  Policy version: {document['requirement_policy_version']}",
        "  Requirements only; no host observation or action performed",
    ]
    for item in document["requirements"]:
        lines.extend(
            [
                "",
                f"[{item['category']}] {item['id']}",
                f"  State: {item['state']}",
                f"  Expected: {_display(item['expected'])} ({item['comparison']})",
                f"  Evidence: {item['evidence_class']} — {item['evidence_source']}",
                f"  Rationale: {item['reason']}",
                f"  Lifecycle: {item['lifecycle']}",
                f"  Blocks host compliance now: {'YES' if item['currently_blocks_host_compliance'] else 'NO'}",
                f"  Policy guidance: {item['remediation']['guidance']}",
                "  Action performed: NONE",
            ]
        )
    return "\n".join(lines) + "\n"


def drift_text(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "DRIFT REPORT ONLY",
        "NO CHANGES PERFORMED",
        "",
        "Profile",
        f"  Selected: {report['profile']}",
        f"  Requirement policy: {report['requirement_policy_version']}",
        "",
        "Host drift",
        f"  Blocking: {summary['blocking_count']}",
        f"  Warnings: {summary['warning_count']}",
        f"  Decision pending: {summary['decision_pending_count']}",
        f"  Unknown: {summary['unknown_count']}",
    ]
    groups = (
        ("BLOCKING", lambda item: item["severity"] == "BLOCKING"),
        ("WARNING", lambda item: item["severity"] == "WARNING"),
        ("DECISION PENDING", lambda item: item["result"] == "DECISION_PENDING"),
        ("OTHER FINDINGS", lambda item: item["severity"] == "INFO" and item["result"] != "DECISION_PENDING"),
    )
    for title, predicate in groups:
        selected = [item for item in report["findings"] if predicate(item)]
        lines.extend(["", title])
        if not selected:
            lines.append("  - None")
        for item in selected:
            lines.extend(
                [
                    f"  - {item['id']}: {item['result']} ({item['requirement_state']})",
                    f"    Expected: {_display(item['expected'])}",
                    f"    Observed: {item['observed_status']} / {_display(item['observed'])}",
                    f"    Evidence: {item['evidence_class']}",
                    f"    {_drift_guidance_label(item['result'])}: {item['remediation']['guidance']}",
                    "    Action performed: NONE",
                ]
            )
    lines.extend(["", "External readiness"])
    gates = report["external_readiness_summary"]["gates"]
    if not gates:
        lines.append("  - None")
    for gate in gates:
        lines.append(f"  - {gate['id']}: {gate['status']} (not host drift)")
    lines.extend(
        [
            "",
            "Result",
            f"  Host compliance: {report['host_compliance']}",
            f"  Host drift status: {report['host_drift_status']}",
            f"  Production readiness: {report['production_readiness']}",
            "  DRIFT REPORT ONLY — NO CHANGES PERFORMED",
        ]
    )
    return "\n".join(lines) + "\n"


def _drift_guidance_label(result: str) -> str:
    return {
        "SATISFIED": "Guidance",
        "NOT_APPLICABLE": "Guidance",
        "DECISION_PENDING": "Decision guidance",
        "UNKNOWN": "Investigation guidance",
        "UNSATISFIED": "Suggested remediation",
    }[result]
