# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 4G.1 decision/action and profile-aware planning regressions."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from kalvin.drift import evaluate_host_drift
from kalvin.loader import load_architecture
from kalvin.output import remediation_plan_text, stable_json
from kalvin.remediation import generate_remediation_plan, planning_policy_errors
from kalvin.resolver import resolve_plan


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


class PlanningSemanticCleanupTests(unittest.TestCase):
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

    def plan(
        self,
        profile: str,
        *,
        observed: dict | None = None,
        requirement_policy: dict | None = None,
        planning_policy: dict | None = None,
    ) -> dict:
        requirements = requirement_policy or self.requirement_policy
        policy = planning_policy or self.planning_policy
        resolved = resolve_plan(
            profile, FIXTURES / f"synthetic-{profile}.lock.json", root=ROOT
        )
        drift = evaluate_host_drift(resolved, observed or self.observed, requirements)
        return generate_remediation_plan(
            resolved,
            drift,
            requirements,
            policy,
            plan_schema=self.plan_schema,
        )

    @staticmethod
    def decision(plan: dict, requirement_id: str) -> dict:
        return next(
            item for item in plan["decisions"]
            if item["requirement_id"] == requirement_id
        )

    def required_missing_docker(self, *, git_missing: bool = False) -> dict:
        requirements = copy.deepcopy(self.requirement_policy)
        docker = next(
            item for item in requirements["requirements"]
            if item["id"] == "host.docker-requirement"
        )
        docker["profiles"]["core"] = "REQUIRED"
        docker["profile_overrides"]["core"] = {
            "comparison": "EQUALS",
            "expected": True,
        }
        docker["decision_state"] = "APPROVED"
        requirements["policy_version"] = "1.1.0"
        observed = copy.deepcopy(self.observed)
        observed["docker"]["cli"]["present"] = False
        if git_missing:
            observed["executables"]["git"]["present"] = False
        return self.plan(
            "core", observed=observed, requirement_policy=requirements
        )

    def test_docker_decision_uses_policy_identity_not_action_identity(self) -> None:
        decision = self.decision(self.plan("core"), "host.docker-requirement")
        self.assertEqual(decision["id"], "approve-container-runtime-policy")
        self.assertNotEqual(decision["id"], "provision-approved-container-runtime")

    def test_docker_decision_wording_is_policy_only(self) -> None:
        plan = self.plan("core")
        decision = self.decision(plan, "host.docker-requirement")
        self.assertIn("Decide whether this profile requires", decision["what"])
        self.assertIn("approve the supported runtime policy", decision["what"])
        self.assertIn("has not yet been approved", decision["why"])
        for verb in ("provision", "install", "repair"):
            self.assertNotIn(verb, decision["what"].lower())
        rendered = remediation_plan_text(plan)
        self.assertIn("approve-container-runtime-policy", stable_json(decision))
        self.assertIn(decision["what"], rendered)

    def test_docker_decision_proposes_no_host_mutation(self) -> None:
        decision = self.decision(self.plan("storage"), "host.docker-requirement")
        self.assertFalse(decision["host_mutation_proposed"])
        self.assertEqual(decision["status"], "HUMAN_POLICY_DECISION_REQUIRED")

    def test_future_container_runtime_action_remains_distinct(self) -> None:
        rule = next(
            item for item in self.planning_policy["finding_rules"]
            if item["requirement_id"] == "host.docker-requirement"
        )
        self.assertEqual(rule["decision"]["id"], "approve-container-runtime-policy")
        self.assertEqual(rule["proposal_id"], "provision-approved-container-runtime")
        self.assertEqual(rule["action_class"], "PACKAGE_OR_RUNTIME_PROVISION")

    def test_container_runtime_action_requires_required_unsatisfied_drift(self) -> None:
        current = self.plan("core")
        self.assertNotIn(
            "provision-approved-container-runtime",
            {item["id"] for item in current["actions"]},
        )
        required = self.required_missing_docker()
        action = next(
            item for item in required["actions"]
            if item["id"] == "provision-approved-container-runtime"
        )
        self.assertEqual(action["source_finding_ids"], ["host.docker-requirement"])
        self.assertEqual(action["action_class"], "PACKAGE_OR_RUNTIME_PROVISION")
        self.assertFalse(action["execution_available"])
        self.assertNotIn(
            "host.docker-requirement",
            {item["requirement_id"] for item in required["decisions"]},
        )

    def test_lab_capacity_decision_is_experiment_specific(self) -> None:
        decision = self.decision(
            self.plan("lab"), "host.minimum-storage-capacity"
        )
        combined = f"{decision['what']} {decision['why']}"
        self.assertIn("selected experimental components", combined)
        self.assertIn("local experimental working set", combined)
        self.assertIn("production sizing", combined)
        self.assertNotIn("Core", combined)
        self.assertNotIn("retention authority", combined)

    def test_core_capacity_decision_retains_recovery_boundary(self) -> None:
        decision = self.decision(
            self.plan("core"), "host.minimum-storage-capacity"
        )
        combined = f"{decision['what']} {decision['why']}"
        self.assertIn("application working set", combined)
        self.assertIn("migration and backup staging", combined)
        self.assertIn("recovery workflow", combined)
        self.assertIn("long-term retention", combined)
        self.assertIn("authoritative elsewhere", combined)

    def test_storage_retention_capacity_semantics_remain_separate(self) -> None:
        plan = self.plan("storage")
        retention = self.decision(plan, "storage.retention-capacity")
        self.assertEqual(retention["id"], "approve-storage-retention-policy")
        self.assertIn("Storage retention", retention["what"])
        self.assertIn("backup working set", retention["why"])
        self.assertNotIn(
            "host.minimum-storage-capacity",
            {item["requirement_id"] for item in plan["decisions"]},
        )
        self.assertFalse(
            {"kal", "beepy", "model-runtime"}
            & set(resolve_plan(
                "storage", FIXTURES / "synthetic-storage.lock.json", root=ROOT
            )["dependency_order"])
        )

    def test_actionable_git_action_structure_is_unchanged(self) -> None:
        observed = copy.deepcopy(self.observed)
        observed["executables"]["git"]["present"] = False
        current = self.plan("core", observed=observed)
        prior_policy = copy.deepcopy(self.planning_policy)
        prior_policy["policy_version"] = "1.0.0"
        for requirement_id in (
            "host.docker-requirement",
            "host.minimum-storage-capacity",
        ):
            rule = next(
                item for item in prior_policy["finding_rules"]
                if item["requirement_id"] == requirement_id
            )
            rule.pop("decision")
        prior = self.plan(
            "core", observed=observed, planning_policy=prior_policy
        )
        self.assertEqual(current["action_count"], 1)
        self.assertEqual(current["actions"], prior["actions"])
        action = current["actions"][0]
        self.assertEqual(action["id"], "provision-approved-git-tooling")
        self.assertEqual(action["source_finding_ids"], ["capability.git"])
        self.assertEqual(action["risk"], "MODERATE")
        self.assertEqual(action["scopes"], ["HOST_RUNTIME", "HOST_TOOLING"])
        self.assertEqual(action["approval"]["state"], "REQUIRED")
        self.assertEqual(action["approval"]["classes"], ["OPERATOR_APPROVAL"])
        self.assertEqual(
            action["approval"]["plan_binding"],
            "EXACT_PLAN_FINGERPRINT_REQUIRED",
        )
        self.assertTrue(action["preconditions"])
        self.assertTrue(action["validation"])
        self.assertEqual(action["rollback"]["class"], "DEFINED_REQUIRED")
        self.assertEqual(action["failure_behavior"], "ROLLBACK_REQUIRED")
        self.assertFalse(action["execution_available"])
        forbidden = {"command", "argv", "script", "shell", "sudo_command"}
        self.assertFalse(forbidden & set(action))

    def test_all_generated_actions_keep_execution_unavailable(self) -> None:
        plan = self.required_missing_docker(git_missing=True)
        self.assertGreaterEqual(plan["action_count"], 2)
        self.assertFalse(plan["execution_available"])
        self.assertTrue(all(item["execution_available"] is False for item in plan["actions"]))

    def test_action_rule_rejects_decision_action_identity_collision(self) -> None:
        policy = copy.deepcopy(self.planning_policy)
        rule = next(
            item for item in policy["finding_rules"]
            if item["requirement_id"] == "host.docker-requirement"
        )
        rule["decision"]["id"] = rule["proposal_id"]
        codes = {
            code
            for code, _, _ in planning_policy_errors(policy, self.requirement_policy)
        }
        self.assertIn("decision-action-identity-collision", codes)


if __name__ == "__main__":
    unittest.main()
