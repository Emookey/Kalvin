# SPDX-License-Identifier: AGPL-3.0-or-later
"""Positive deterministic remediation planning tests using synthetic state only."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from kalvin.drift import evaluate_host_drift
from kalvin.loader import load_architecture
from kalvin.output import remediation_plan_text, stable_json
from kalvin.remediation import generate_remediation_plan
from kalvin.resolver import resolve_plan


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


class RemediationPlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.architecture = architecture
        self.requirement_policy = architecture.catalogs["host-requirements"]
        self.planning_policy = architecture.catalogs["remediation-actions"]
        self.plan_schema = architecture.schemas["remediation-plan.schema.json"]
        self.observed = json.loads(
            (FIXTURES / "synthetic-observed-host.json").read_text(encoding="utf-8")
        )

    def resolved(self, profile: str = "core") -> dict:
        return resolve_plan(
            profile, FIXTURES / f"synthetic-{profile}.lock.json", root=ROOT
        )

    def remediation_plan(
        self,
        profile: str = "core",
        *,
        observed: dict | None = None,
        requirement_policy: dict | None = None,
        planning_policy: dict | None = None,
    ) -> dict:
        requirement_policy = requirement_policy or self.requirement_policy
        resolved = self.resolved(profile)
        drift = evaluate_host_drift(resolved, observed or self.observed, requirement_policy)
        return generate_remediation_plan(
            resolved,
            drift,
            requirement_policy,
            planning_policy or self.planning_policy,
            plan_schema=self.plan_schema,
        )

    @staticmethod
    def finding(plan: dict, requirement_id: str) -> dict:
        return next(item for item in plan["findings"] if item["requirement_id"] == requirement_id)

    def actionable(self) -> dict:
        observed = copy.deepcopy(self.observed)
        observed["executables"]["git"]["present"] = False
        return self.remediation_plan(observed=observed)

    def test_drift_free_host_produces_zero_mutation_actions(self) -> None:
        plan = self.remediation_plan()
        self.assertEqual(plan["action_count"], 0)
        self.assertEqual(plan["actions"], [])
        self.assertEqual(plan["plan_status"], "NO_ACTIONS_REQUIRED")
        self.assertFalse(plan["execution_available"])

    def test_unsatisfied_required_capability_produces_proposal(self) -> None:
        plan = self.actionable()
        self.assertEqual(plan["action_count"], 1)
        action = plan["actions"][0]
        self.assertEqual(action["id"], "provision-approved-git-tooling")
        self.assertEqual(action["action_class"], "PACKAGE_OR_RUNTIME_PROVISION")
        self.assertEqual(action["source_finding_ids"], ["capability.git"])
        self.assertEqual(action["approval"]["state"], "REQUIRED")
        self.assertFalse(action["execution_available"])

    def test_decision_pending_produces_decision_not_mutation(self) -> None:
        plan = self.remediation_plan()
        finding = self.finding(plan, "host.minimum-logical-cpu")
        self.assertEqual(finding["planning_classification"], "HUMAN_POLICY_DECISION_REQUIRED")
        self.assertIn(
            "host.minimum-logical-cpu",
            {item["requirement_id"] for item in plan["decisions"]},
        )
        self.assertNotIn(
            "host.minimum-logical-cpu",
            {source for action in plan["actions"] for source in action["source_finding_ids"]},
        )

    def test_unknown_produces_investigation_not_mutation(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["executables"]["git"].update(status="UNAVAILABLE", present=None)
        plan = self.remediation_plan(observed=observed)
        investigation = next(
            item for item in plan["investigations"] if item["requirement_id"] == "capability.git"
        )
        self.assertEqual(investigation["status"], "INVESTIGATION_REQUIRED")
        self.assertFalse(investigation["host_mutation_proposed"])
        self.assertNotIn(
            "capability.git",
            {source for action in plan["actions"] for source in action["source_finding_ids"]},
        )

    def test_not_applicable_and_satisfied_produce_no_action(self) -> None:
        storage = self.remediation_plan("storage")
        self.assertEqual(
            self.finding(storage, "model-runtime.compute-capacity")["planning_classification"],
            "NO_REMEDIATION",
        )
        core = self.remediation_plan("core")
        self.assertEqual(
            self.finding(core, "runtime.python-version")["planning_classification"],
            "NO_REMEDIATION",
        )

    def test_deterministic_plan_fingerprint_and_byte_identical_json(self) -> None:
        first = self.actionable()
        second = self.actionable()
        self.assertEqual(first["plan_fingerprint"], second["plan_fingerprint"])
        self.assertEqual(stable_json(first), stable_json(second))
        self.assertNotIn("created_at", first)

    def test_changed_requirement_policy_changes_fingerprint(self) -> None:
        first = self.actionable()
        requirement_policy = copy.deepcopy(self.requirement_policy)
        requirement_policy["policy_version"] = "1.0.3"
        second = self.remediation_plan(
            observed={
                **copy.deepcopy(self.observed),
                "executables": {
                    **copy.deepcopy(self.observed["executables"]),
                    "git": {"status": "OBSERVED", "present": False},
                },
            },
            requirement_policy=requirement_policy,
        )
        self.assertNotEqual(first["plan_fingerprint"], second["plan_fingerprint"])

    def test_changed_relevant_drift_changes_fingerprint(self) -> None:
        actionable = self.actionable()
        unknown_observed = copy.deepcopy(self.observed)
        unknown_observed["executables"]["git"].update(status="UNAVAILABLE", present=None)
        unknown = self.remediation_plan(observed=unknown_observed)
        self.assertNotEqual(actionable["source_drift_identity"], unknown["source_drift_identity"])
        self.assertNotEqual(actionable["plan_fingerprint"], unknown["plan_fingerprint"])

    def test_changed_action_definition_changes_fingerprint(self) -> None:
        first = self.actionable()
        policy = copy.deepcopy(self.planning_policy)
        action_class = next(
            item for item in policy["action_classes"]
            if item["id"] == "PACKAGE_OR_RUNTIME_PROVISION"
        )
        action_class["description"] += " Synthetic reviewed policy revision."
        policy["policy_version"] = "1.0.1"
        second = self.remediation_plan(
            observed={
                **copy.deepcopy(self.observed),
                "executables": {
                    **copy.deepcopy(self.observed["executables"]),
                    "git": {"status": "OBSERVED", "present": False},
                },
            },
            planning_policy=policy,
        )
        self.assertNotEqual(
            first["actions"][0]["action_definition_fingerprint"],
            second["actions"][0]["action_definition_fingerprint"],
        )
        self.assertNotEqual(first["plan_fingerprint"], second["plan_fingerprint"])

    def test_action_contract_assignments_are_explicit(self) -> None:
        action = self.actionable()["actions"][0]
        self.assertIn(action["risk"], {"LOW", "MODERATE", "HIGH", "CRITICAL"})
        self.assertTrue(action["scopes"])
        self.assertTrue(action["approval"]["classes"])
        self.assertTrue(action["preconditions"])
        self.assertTrue(action["validation"])
        self.assertIn("class", action["rollback"])
        self.assertIn(action["failure_behavior"], {"STOP", "ROLLBACK_REQUIRED", "MANUAL_RECOVERY_REQUIRED", "REASSESS_REQUIRED"})

    def test_multi_action_plan_has_stable_declarative_order(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["executables"]["git"]["present"] = False
        observed["runtimes"]["python"]["version"] = "3.10.0"
        plan = self.remediation_plan(observed=observed)
        self.assertEqual(plan["action_count"], 2)
        self.assertEqual(
            [item["id"] for item in plan["actions"]],
            ["provision-approved-git-tooling", "provision-approved-python-runtime"],
        )
        self.assertEqual(
            plan["action_dependencies"],
            [
                {"action_id": "provision-approved-git-tooling", "depends_on": []},
                {"action_id": "provision-approved-python-runtime", "depends_on": []},
            ],
        )

    def test_backup_first_policy_is_unverified_not_invented(self) -> None:
        configuration = next(
            item for item in self.planning_policy["action_classes"]
            if item["id"] == "CONFIGURATION_CHANGE"
        )
        backup = next(
            item for item in configuration["preconditions"]
            if item["id"] == "backup.pre-update-verified"
        )
        self.assertEqual(backup["initial_state"], "UNVERIFIED")

    def test_action_catalog_has_explicit_failure_and_rollback_contracts(self) -> None:
        for action_class in self.planning_policy["action_classes"]:
            self.assertIn(action_class["failure_behavior"], {"STOP", "ROLLBACK_REQUIRED", "MANUAL_RECOVERY_REQUIRED", "REASSESS_REQUIRED"})
            self.assertIn(
                action_class["rollback_class"],
                {"NOT_REQUIRED", "DEFINED_REQUIRED", "BACKUP_REQUIRED", "MANUAL_RECOVERY_REQUIRED", "NO_SAFE_AUTOMATIC_ROLLBACK"},
            )
            self.assertTrue(action_class["validation_expectations"])

    def test_storage_plan_contains_no_application_compute_action(self) -> None:
        plan = self.remediation_plan("storage")
        self.assertTrue(
            all("APPLICATION" not in action["scopes"] for action in plan["actions"])
        )
        self.assertFalse(
            {"kal", "beepy", "model-runtime"}
            & set(self.resolved("storage")["dependency_order"])
        )

    def test_core_external_and_durable_rag_gates_remain_external(self) -> None:
        plan = self.remediation_plan("core")
        gates = {item["id"]: item["status"] for item in plan["external_readiness"]["gates"]}
        self.assertEqual(gates["kal.rag-status-durable"], "REQUIRED_EXTERNAL_UNVERIFIED")
        self.assertNotIn(
            "kal.rag-status-durable",
            {source for action in plan["actions"] for source in action["source_finding_ids"]},
        )

    def test_docker_is_not_planned_while_decision_pending(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["docker"]["cli"]["present"] = False
        plan = self.remediation_plan(observed=observed)
        self.assertIn(
            "host.docker-requirement",
            {item["requirement_id"] for item in plan["decisions"]},
        )
        self.assertNotIn(
            "host.docker-requirement",
            {source for action in plan["actions"] for source in action["source_finding_ids"]},
        )

    def test_docker_can_be_planned_only_when_policy_is_required(self) -> None:
        requirement_policy = copy.deepcopy(self.requirement_policy)
        docker = next(
            item for item in requirement_policy["requirements"]
            if item["id"] == "host.docker-requirement"
        )
        docker["profiles"]["core"] = "REQUIRED"
        docker["profile_overrides"]["core"] = {"comparison": "EQUALS", "expected": True}
        docker["decision_state"] = "APPROVED"
        requirement_policy["policy_version"] = "1.1.0"
        observed = copy.deepcopy(self.observed)
        observed["docker"]["cli"]["present"] = False
        plan = self.remediation_plan(
            observed=observed, requirement_policy=requirement_policy
        )
        action = next(
            item for item in plan["actions"]
            if "host.docker-requirement" in item["source_finding_ids"]
        )
        self.assertEqual(action["id"], "provision-approved-container-runtime")

    def test_plan_matches_schema_and_operator_text(self) -> None:
        plan = self.actionable()
        self.assertEqual(list(Draft202012Validator(self.plan_schema).iter_errors(plan)), [])
        rendered = remediation_plan_text(plan)
        for label in (
            "REMEDIATION PLAN ONLY",
            "WHAT:",
            "WHY:",
            "RISK:",
            "WHAT COULD BE AFFECTED:",
            "WHAT MUST BE TRUE FIRST:",
            "HOW SUCCESS WOULD BE CHECKED:",
            "HOW RECOVERY WOULD WORK:",
            "EXECUTION NOT AVAILABLE",
            "NO CHANGES PERFORMED",
        ):
            self.assertIn(label, rendered)


if __name__ == "__main__":
    unittest.main()
