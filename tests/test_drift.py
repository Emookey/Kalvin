# SPDX-License-Identifier: AGPL-3.0-or-later
"""Positive deterministic host requirement and drift tests."""

from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from kalvin.cli import main
from kalvin.drift import evaluate_host_drift, requirements_for_profile
from kalvin.loader import load_architecture
from kalvin.output import drift_text, requirements_text, stable_json
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
        self.assertEqual(document["requirement_policy_version"], "1.0.2")

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


class GuidanceRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.policy = architecture.catalogs["host-requirements"]
        self.observed = json.loads((FIXTURES / "synthetic-observed-host.json").read_text(encoding="utf-8"))

    def requirements(self, profile: str) -> dict:
        return requirements_for_profile(self.policy, profile)

    def report(self, profile: str) -> dict:
        plan = resolve_plan(profile, FIXTURES / f"synthetic-{profile}.lock.json", root=ROOT)
        return evaluate_host_drift(plan, self.observed, self.policy)

    @staticmethod
    def item(document: dict, requirement_id: str, collection: str) -> dict:
        return next(item for item in document[collection] if item["id"] == requirement_id)

    def test_lab_storage_capacity_guidance_is_lab_specific(self) -> None:
        guidance = self.item(self.requirements("lab"), "host.minimum-storage-capacity", "requirements")["remediation"]["guidance"]
        self.assertIn("Lab local experimental working set", guidance)
        self.assertNotIn("Core", guidance)

    def test_storage_local_capacity_not_applicable_guidance_requires_no_action(self) -> None:
        finding = self.item(self.report("storage"), "host.minimum-storage-capacity", "findings")
        self.assertEqual((finding["result"], finding["severity"]), ("NOT_APPLICABLE", "INFO"))
        self.assertIn("No remediation is required", finding["remediation"]["guidance"])
        self.assertNotIn("Core", finding["remediation"]["guidance"])

    def test_storage_memory_guidance_uses_storage_workload(self) -> None:
        guidance = self.item(self.requirements("storage"), "host.minimum-memory", "requirements")["remediation"]["guidance"]
        self.assertIn("Storage-role services", guidance)
        self.assertIn("backup and retention workload", guidance)
        self.assertNotIn("model", guidance.lower())

    def test_core_storage_guidance_retains_staging_and_authority_boundary(self) -> None:
        guidance = self.item(self.report("core"), "host.minimum-storage-capacity", "findings")["remediation"]["guidance"]
        self.assertIn("Core application state", guidance)
        self.assertIn("staging", guidance)
        self.assertIn("without making Core the retention authority", guidance)

    def test_excluded_model_runtime_guidance_requires_no_remediation(self) -> None:
        finding = self.item(self.report("storage"), "model-runtime.compute-capacity", "findings")
        self.assertEqual((finding["requirement_state"], finding["result"], finding["severity"]), ("NOT_APPLICABLE", "NOT_APPLICABLE", "INFO"))
        self.assertIn("No remediation is required", finding["remediation"]["guidance"])
        self.assertNotIn("approve", finding["remediation"]["guidance"].lower())

    def test_all_requirement_and_drift_actions_remain_none(self) -> None:
        for profile in ("lab", "core", "storage"):
            requirements = self.requirements(profile)
            self.assertEqual(requirements["action_performed"], "NONE")
            self.assertTrue(all(item["remediation"]["action"] == "NONE" for item in requirements["requirements"]))
            report = self.report(profile)
            self.assertFalse(report["changes_performed"])
            self.assertTrue(all(item["action_performed"] == "NONE" for item in report["findings"]))
            self.assertTrue(all(item["remediation"]["action"] == "NONE" for item in report["findings"]))

    def test_profile_states_and_drift_counts_are_unchanged(self) -> None:
        expected_states = {
            "lab": Counter(REQUIRED=2, RECOMMENDED=3, OPTIONAL=4, HUMAN_DECISION_REQUIRED=5, NOT_APPLICABLE=1),
            "core": Counter(REQUIRED=4, RECOMMENDED=4, HUMAN_DECISION_REQUIRED=6, NOT_APPLICABLE=1),
            "storage": Counter(REQUIRED=6, RECOMMENDED=1, OPTIONAL=1, HUMAN_DECISION_REQUIRED=5, NOT_APPLICABLE=2),
        }
        expected_decisions = {"lab": 4, "core": 6, "storage": 5}
        for profile in ("lab", "core", "storage"):
            states = Counter(item["state"] for item in self.requirements(profile)["requirements"])
            self.assertEqual(states, expected_states[profile])
            summary = self.report(profile)["summary"]
            self.assertEqual((summary["blocking_count"], summary["warning_count"]), (0, 0))
            self.assertEqual(summary["decision_pending_count"], expected_decisions[profile])

    def test_core_external_readiness_remains_blocked(self) -> None:
        report = self.report("core")
        self.assertEqual(report["production_readiness"], "BLOCKED_EXTERNAL_GATE")
        self.assertIn("kal.rag-status-durable", {gate["id"] for gate in report["external_readiness_summary"]["gates"]})

    def test_storage_remains_free_of_application_compute(self) -> None:
        report = self.report("storage")
        self.assertFalse(set(report["resolved_plan_summary"]["components"]) & {"kal", "beepy", "model-runtime"})
        self.assertEqual(self.item(report, "model-runtime.compute-capacity", "findings")["result"], "NOT_APPLICABLE")

    def test_text_and_json_preserve_profile_guidance_and_no_action(self) -> None:
        requirements = self.requirements("storage")
        report = self.report("storage")
        requirements_rendered = requirements_text(requirements)
        drift_rendered = drift_text(report)
        json_rendered = stable_json(report)
        self.assertIn("Profile: storage", requirements_rendered)
        self.assertIn("Storage-role services", requirements_rendered)
        self.assertIn("No remediation is required", drift_rendered)
        self.assertIn('"action":"NONE"', json_rendered)
        self.assertIn('"action_performed":"NONE"', json_rendered)


class OperatorGuidanceTests(unittest.TestCase):
    def setUp(self) -> None:
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.policy = architecture.catalogs["host-requirements"]
        self.observed = json.loads((FIXTURES / "synthetic-observed-host.json").read_text(encoding="utf-8"))

    def plan(self, profile: str, *, enabled_optional: tuple[str, ...] = ()) -> dict:
        return resolve_plan(
            profile,
            FIXTURES / f"synthetic-{profile}.lock.json",
            root=ROOT,
            enabled_optional=enabled_optional,
        )

    def report(
        self,
        profile: str,
        *,
        observed: dict | None = None,
        enabled_optional: tuple[str, ...] = (),
    ) -> dict:
        return evaluate_host_drift(self.plan(profile, enabled_optional=enabled_optional), observed or self.observed, self.policy)

    @staticmethod
    def finding(report: dict, requirement_id: str) -> dict:
        return next(item for item in report["findings"] if item["id"] == requirement_id)

    @staticmethod
    def rendered_finding(report: dict, requirement_id: str) -> str:
        marker = f"  - {requirement_id}:"
        rendered = drift_text(report).split(marker, 1)[1]
        return rendered.split("\n  - ", 1)[0].split("\n\n", 1)[0]

    def test_satisfied_finding_uses_informational_guidance_label(self) -> None:
        block = self.rendered_finding(self.report("core"), "runtime.python-version")
        self.assertIn("    Guidance:", block)

    def test_satisfied_finding_does_not_suggest_remediation(self) -> None:
        block = self.rendered_finding(self.report("core"), "runtime.python-version")
        self.assertNotIn("Suggested remediation:", block)

    def test_not_applicable_finding_uses_informational_guidance_label(self) -> None:
        block = self.rendered_finding(self.report("storage"), "model-runtime.compute-capacity")
        self.assertIn("    Guidance: No remediation is required", block)
        self.assertNotIn("Suggested remediation:", block)

    def test_decision_pending_finding_uses_decision_guidance_label(self) -> None:
        block = self.rendered_finding(self.report("storage"), "host.minimum-memory")
        self.assertIn("    Decision guidance:", block)

    def test_unsatisfied_finding_keeps_remediation_label(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["executables"]["git"]["present"] = False
        block = self.rendered_finding(self.report("core", observed=observed), "capability.git")
        self.assertIn("    Suggested remediation:", block)

    def test_unknown_finding_uses_investigation_guidance_label(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["executables"]["git"].update(status="UNAVAILABLE", present=None)
        block = self.rendered_finding(self.report("core", observed=observed), "capability.git")
        self.assertIn("    Investigation guidance:", block)

    def test_json_remediation_contract_is_unchanged(self) -> None:
        report = self.report("core")
        schema = json.loads((ROOT / "schemas/host-drift.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)
        self.assertTrue(all(item["remediation"]["action"] == "NONE" for item in report["findings"]))
        self.assertTrue(all(item["action_performed"] == "NONE" for item in report["findings"]))

    def test_lab_without_model_runtime_has_model_free_memory_guidance(self) -> None:
        finding = self.finding(self.report("lab"), "host.minimum-memory")
        self.assertNotIn("model", finding["remediation"]["guidance"].lower())

    def test_lab_with_model_runtime_has_model_aware_memory_guidance(self) -> None:
        finding = self.finding(
            self.report("lab", enabled_optional=("model-runtime",)),
            "host.minimum-memory",
        )
        self.assertIn("selected model-runtime", finding["remediation"]["guidance"])
        self.assertIn("model workload", finding["remediation"]["guidance"])

    def test_storage_memory_guidance_remains_model_free(self) -> None:
        guidance = self.finding(self.report("storage"), "host.minimum-memory")["remediation"]["guidance"]
        self.assertIn("Storage-role services", guidance)
        self.assertIn("backup and retention workload", guidance)
        self.assertNotIn("model", guidance.lower())

    def test_core_memory_guidance_reflects_selected_model_runtime(self) -> None:
        guidance = self.finding(self.report("core"), "host.minimum-memory")["remediation"]["guidance"]
        self.assertIn("selected model-runtime", guidance)
        self.assertIn("model workload", guidance)

    def test_core_memory_guidance_omits_unselected_model_runtime(self) -> None:
        plan = copy.deepcopy(self.plan("core"))
        plan["components"] = [item for item in plan["components"] if item["id"] != "model-runtime"]
        guidance = self.finding(evaluate_host_drift(plan, self.observed, self.policy), "host.minimum-memory")["remediation"]["guidance"]
        self.assertNotIn("model", guidance.lower())

    def test_core_docker_decision_has_no_approved_expected_value(self) -> None:
        finding = self.finding(self.report("core"), "host.docker-requirement")
        self.assertEqual((finding["requirement_state"], finding["result"]), ("HUMAN_DECISION_REQUIRED", "DECISION_PENDING"))
        self.assertEqual((finding["comparison"], finding["expected"]), ("DECISION_PENDING", None))

    def test_storage_docker_decision_has_no_approved_expected_value(self) -> None:
        finding = self.finding(self.report("storage"), "host.docker-requirement")
        self.assertEqual((finding["requirement_state"], finding["result"]), ("HUMAN_DECISION_REQUIRED", "DECISION_PENDING"))
        self.assertEqual((finding["comparison"], finding["expected"]), ("DECISION_PENDING", None))
        self.assertNotIn("model", finding["remediation"]["guidance"].lower())

    def test_lab_docker_optional_semantics_remain_concrete_and_unchanged(self) -> None:
        requirement = next(
            item for item in requirements_for_profile(self.policy, "lab")["requirements"]
            if item["id"] == "host.docker-requirement"
        )
        self.assertEqual((requirement["state"], requirement["comparison"], requirement["expected"]), ("OPTIONAL", "EQUALS", True))

    def test_no_numeric_sizing_threshold_is_introduced(self) -> None:
        numeric_decisions = {
            "host.minimum-logical-cpu",
            "host.minimum-memory",
            "host.minimum-storage-capacity",
            "storage.retention-capacity",
            "model-runtime.compute-capacity",
        }
        for profile in ("lab", "core", "storage"):
            requirements = requirements_for_profile(self.policy, profile)["requirements"]
            for item in requirements:
                if item["id"] in numeric_decisions and item["state"] == "HUMAN_DECISION_REQUIRED":
                    self.assertEqual((item["comparison"], item["expected"]), ("DECISION_PENDING", None))

    def test_core_readiness_and_rag_gate_remain_external(self) -> None:
        report = self.report("core")
        self.assertEqual(report["production_readiness"], "BLOCKED_EXTERNAL_GATE")
        gates = {item["id"]: item["status"] for item in report["external_readiness_summary"]["gates"]}
        self.assertEqual(gates["kal.rag-status-durable"], "REQUIRED_EXTERNAL_UNVERIFIED")

    def test_storage_compute_boundary_and_readiness_remain_unchanged(self) -> None:
        report = self.report("storage")
        self.assertFalse(set(report["resolved_plan_summary"]["components"]) & {"kal", "beepy", "model-runtime"})
        self.assertEqual(self.finding(report, "model-runtime.compute-capacity")["result"], "NOT_APPLICABLE")
        self.assertEqual(report["production_readiness"], "BLOCKED_EXTERNAL_GATE")


if __name__ == "__main__":
    unittest.main()
