# SPDX-License-Identifier: AGPL-3.0-or-later
"""Positive deterministic host requirement and drift tests."""

from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from kalvin.cli import main
from kalvin.drift import evaluate_host_drift, requirements_for_profile
from kalvin.loader import load_architecture
from kalvin.output import stable_json
from kalvin.resolver import resolve_plan


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


class DriftTests(unittest.TestCase):
    def setUp(self) -> None:
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.architecture = architecture
        self.policy = architecture.catalogs["host-requirements"]
        self.observed = json.loads((FIXTURES / "synthetic-observed-host.json").read_text(encoding="utf-8"))

    def plan(self, profile: str) -> dict:
        return resolve_plan(profile, FIXTURES / f"synthetic-{profile}.lock.json", root=ROOT)

    def report(self, profile: str, observed: dict | None = None) -> dict:
        return evaluate_host_drift(self.plan(profile), observed or self.observed, self.policy)

    def finding(self, report: dict, requirement_id: str) -> dict:
        return next(item for item in report["findings"] if item["id"] == requirement_id)

    def test_lab_requirements_load(self) -> None:
        document = requirements_for_profile(self.policy, "lab")
        self.assertEqual(document["profile"], "lab")
        self.assertEqual(document["requirement_policy_version"], "1.0.0")

    def test_core_requirements_load(self) -> None:
        states = {item["id"]: item["state"] for item in requirements_for_profile(self.policy, "core")["requirements"]}
        self.assertEqual(states["host.os-family"], "REQUIRED")
        self.assertEqual(states["host.docker-requirement"], "HUMAN_DECISION_REQUIRED")

    def test_storage_requirements_load(self) -> None:
        states = {item["id"]: item["state"] for item in requirements_for_profile(self.policy, "storage")["requirements"]}
        self.assertEqual(states["storage.block-inventory-observable"], "REQUIRED")
        self.assertEqual(states["host.minimum-storage-capacity"], "NOT_APPLICABLE")

    def test_supported_os_comparison(self) -> None:
        self.assertEqual(self.finding(self.report("core"), "host.os-family")["result"], "SATISFIED")
        observed = copy.deepcopy(self.observed)
        observed["operating_system"]["family"] = "synthetic-unsupported"
        self.assertEqual(self.finding(self.report("core", observed), "host.os-family")["severity"], "BLOCKING")

    def test_supported_architecture_comparison(self) -> None:
        self.assertEqual(self.finding(self.report("core"), "host.architecture-support")["result"], "SATISFIED")
        observed = copy.deepcopy(self.observed)
        observed["operating_system"]["architecture"] = "synthetic-unvalidated"
        self.assertEqual(self.finding(self.report("core", observed), "host.architecture-support")["result"], "UNSATISFIED")

    def test_python_runtime_requirement(self) -> None:
        finding = self.finding(self.report("storage"), "runtime.python-version")
        self.assertEqual((finding["requirement_state"], finding["result"]), ("REQUIRED", "SATISFIED"))

    def test_git_bootstrap_requirement(self) -> None:
        finding = self.finding(self.report("lab"), "capability.git")
        self.assertEqual((finding["lifecycle"], finding["result"]), ("BOOTSTRAP_TIME", "SATISFIED"))

    def test_optional_requirement_absent_is_not_applicable(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["docker"]["cli"]["present"] = False
        finding = self.finding(self.report("lab", observed), "host.docker-requirement")
        self.assertEqual((finding["requirement_state"], finding["result"]), ("OPTIONAL", "NOT_APPLICABLE"))

    def test_blocking_required_capability_satisfied(self) -> None:
        report = self.report("core")
        self.assertEqual(report["host_compliance"], "SATISFIED")
        self.assertEqual(report["summary"]["blocking_count"], 0)

    def test_blocking_required_capability_unsatisfied(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["executables"]["git"]["present"] = False
        report = self.report("core", observed)
        finding = self.finding(report, "capability.git")
        self.assertEqual((finding["result"], finding["severity"]), ("UNSATISFIED", "BLOCKING"))
        self.assertEqual(report["host_compliance"], "UNSATISFIED")

    def test_required_service_inactive_is_unsatisfied_without_action(self) -> None:
        policy = copy.deepcopy(self.policy)
        docker = next(item for item in policy["requirements"] if item["id"] == "host.docker-requirement")
        docker.update(
            observation_path="services.docker.state",
            expected="ACTIVE",
            evidence_class="IMPLEMENTATION_REQUIRED",
            decision_state="APPROVED",
        )
        docker["profiles"]["core"] = "REQUIRED"
        observed = copy.deepcopy(self.observed)
        observed["services"]["docker"]["state"] = "INACTIVE"
        report = evaluate_host_drift(self.plan("core"), observed, policy)
        finding = self.finding(report, "host.docker-requirement")
        self.assertEqual((finding["result"], finding["severity"]), ("UNSATISFIED", "BLOCKING"))
        self.assertEqual(finding["action_performed"], "NONE")

    def test_decision_pending_numeric_requirement(self) -> None:
        finding = self.finding(self.report("core"), "host.minimum-memory")
        self.assertEqual((finding["result"], finding["expected"]), ("DECISION_PENDING", None))
        self.assertEqual(finding["severity"], "INFO")

    def test_deterministic_synthetic_drift_json(self) -> None:
        self.assertEqual(stable_json(self.report("core")), stable_json(self.report("core")))

    def test_stable_output_ordering(self) -> None:
        identifiers = [item["id"] for item in self.report("storage")["findings"]]
        self.assertEqual(identifiers, sorted(identifiers))

    def test_core_host_compliance_does_not_bypass_external_gates(self) -> None:
        report = self.report("core")
        self.assertEqual(report["host_compliance"], "SATISFIED")
        self.assertEqual(report["production_readiness"], "BLOCKED_EXTERNAL_GATE")
        gates = {item["id"] for item in report["external_readiness_summary"]["gates"]}
        self.assertIn("kal.rag-status-durable", gates)

    def test_storage_does_not_gain_application_compute_requirements(self) -> None:
        report = self.report("storage")
        components = set(report["resolved_plan_summary"]["components"])
        self.assertFalse(components & {"kal", "beepy", "model-runtime"})
        model = self.finding(report, "model-runtime.compute-capacity")
        self.assertEqual(model["result"], "NOT_APPLICABLE")

    def test_drift_report_matches_schema(self) -> None:
        schema = json.loads((ROOT / "schemas/host-drift.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(self.report("core"))

    def test_requirements_command_observes_nothing(self) -> None:
        with patch("kalvin.cli.HostInspector.inspect", side_effect=AssertionError("inspector must not run")):
            with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()):
                exit_code = main(["host", "requirements", "--profile", "core", "--format", "json"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["kind"], "KALVIN_PROFILE_HOST_REQUIREMENTS")

    def test_synthetic_drift_cli_writes_no_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp, patch("kalvin.cli.HostInspector.inspect", return_value=copy.deepcopy(self.observed)):
            before = set(Path(temp).iterdir())
            previous = Path.cwd()
            try:
                os.chdir(temp)
                with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()):
                    exit_code = main(["host", "drift", "--profile", "core", "--lock", str(FIXTURES / "synthetic-core.lock.json"), "--format", "json"])
            finally:
                os.chdir(previous)
            self.assertEqual(exit_code, 0)
            self.assertEqual(set(Path(temp).iterdir()), before)
            self.assertEqual(json.loads(stdout.getvalue())["changes_performed"], False)

    def test_cli_distinguishes_blocking_and_unknown_host_drift(self) -> None:
        blocking = copy.deepcopy(self.observed)
        blocking["executables"]["git"]["present"] = False
        unknown = copy.deepcopy(self.observed)
        unknown["executables"]["git"].update(status="UNAVAILABLE", present=None)
        arguments = ["host", "drift", "--profile", "core", "--lock", str(FIXTURES / "synthetic-core.lock.json"), "--format", "json"]
        with patch("kalvin.cli.HostInspector.inspect", return_value=blocking), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(arguments), 4)
        with patch("kalvin.cli.HostInspector.inspect", return_value=unknown), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(arguments), 5)


if __name__ == "__main__":
    unittest.main()
