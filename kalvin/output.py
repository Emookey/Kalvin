# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stable JSON and operator-oriented text presentation."""

from __future__ import annotations

import json
from typing import Any

from .models import ValidationResult


def stable_json(value: Any) -> str:
    """Return canonical-enough stable JSON for repeatable Phase 4D plans."""
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
