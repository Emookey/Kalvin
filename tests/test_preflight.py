# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthetic resolved-versus-observed preflight policy tests."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from kalvin.loader import load_architecture
from kalvin.output import stable_json
from kalvin.preflight import compare_preflight
from kalvin.resolver import resolve_plan


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


class PreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.observed = json.loads((FIXTURES / "synthetic-observed-host.json").read_text())
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.requirements = architecture.catalogs["host-requirements"]

    def result(self, profile: str, observed: dict | None = None) -> dict:
        plan = resolve_plan(profile, FIXTURES / f"synthetic-{profile}.lock.json", root=ROOT)
        return compare_preflight(plan, observed or self.observed, self.requirements)

    def test_lab_preflight(self) -> None:
        self.assertEqual(self.result("lab")["host_preflight_status"], "SATISFIED")

    def test_core_preflight(self) -> None:
        self.assertEqual(self.result("core")["host_preflight_status"], "SATISFIED")

    def test_storage_preflight(self) -> None:
        self.assertEqual(self.result("storage")["host_preflight_status"], "SATISFIED")

    def test_core_host_success_does_not_bypass_application_gates(self) -> None:
        result = self.result("core")
        self.assertEqual(result["production_readiness"], "BLOCKED_EXTERNAL_GATE")
        gates = {item["id"] for item in result["external_readiness_gates"]}
        self.assertIn("kal.rag-status-durable", gates)

    def test_storage_does_not_require_application_compute(self) -> None:
        components = set(self.result("storage")["resolved_plan_summary"]["components"])
        self.assertFalse(components & {"kal", "beepy", "model-runtime"})

    def test_fixed_synthetic_inventory_is_deterministic(self) -> None:
        self.assertEqual(stable_json(self.result("core")), stable_json(self.result("core")))

    def test_unknown_is_distinct_from_false(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["executables"]["git"]["present"] = None
        result = self.result("core", observed)
        check = next(item for item in result["checks"] if item["id"] == "capability.git")
        self.assertEqual(check["status"], "UNKNOWN")
        self.assertEqual(result["host_preflight_status"], "UNKNOWN")

    def test_missing_required_capability_is_unsatisfied(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["executables"]["git"]["present"] = False
        result = self.result("core", observed)
        self.assertEqual(result["host_preflight_status"], "UNSATISFIED")

    def test_optional_failure_is_reported_but_not_blocking(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["network"]["default_route"]["present"] = False
        result = self.result("core", observed)
        route = next(item for item in result["checks"] if item["id"] == "network.default-route")
        self.assertEqual(route["status"], "UNSATISFIED")
        self.assertEqual(result["host_preflight_status"], "SATISFIED")

    def test_unspecified_hardware_minimums_are_reported_unknown(self) -> None:
        result = self.result("core")
        memory = next(item for item in result["checks"] if item["id"] == "host.minimum-memory")
        self.assertEqual(memory["requirement"], "NOT_YET_SPECIFIED")
        self.assertEqual(memory["status"], "UNKNOWN")

    def test_preflight_never_reports_correction(self) -> None:
        self.assertFalse(self.result("core")["correction_performed"])

    def test_observed_input_is_not_mutated(self) -> None:
        before = stable_json(self.observed)
        self.result("storage")
        self.assertEqual(stable_json(self.observed), before)


if __name__ == "__main__":
    unittest.main()
