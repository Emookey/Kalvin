# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 4E-compatible view over the Phase 4F drift evaluator."""

from __future__ import annotations

from typing import Any

from .drift import evaluate_host_drift


def compare_preflight(
    resolved_plan: dict[str, Any], observed_host: dict[str, Any], requirements: dict[str, Any]
) -> dict[str, Any]:
    """Return the retained preflight contract without changing either input."""
    drift = evaluate_host_drift(resolved_plan, observed_host, requirements)
    checks = []
    for item in drift["findings"]:
        status = "UNKNOWN" if item["result"] == "DECISION_PENDING" else item["result"]
        checks.append(
            {
                "id": item["id"],
                "requirement": item["requirement_state"],
                "status": status,
                "observation_path": next(
                    requirement["observation_path"]
                    for requirement in requirements["requirements"]
                    if requirement["id"] == item["id"]
                ),
                "expected": item["expected"],
                "observed": item["observed"],
                "explanation": item["explanation"],
            }
        )
    return {
        "schema_version": "1.0.0",
        "kind": "KALVIN_HOST_PREFLIGHT",
        "profile": drift["profile"],
        "host_preflight_status": drift["host_compliance"],
        "production_readiness": drift["production_readiness"],
        "checks": checks,
        "external_readiness_gates": drift["external_readiness_summary"]["gates"],
        "resolved_plan_summary": drift["resolved_plan_summary"],
        "observed_host": observed_host,
        "correction_performed": False,
    }
