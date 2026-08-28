# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fail-closed requirement-policy, privacy, and no-remediation tests."""

from __future__ import annotations

import ast
import copy
import json
import unittest
from pathlib import Path

from kalvin.drift import requirement_by_id
from kalvin.loader import load_architecture
from kalvin.models import UserInputError
from kalvin.output import stable_json
from kalvin.probes import PROBE_ALLOWLIST, ProbeId
from kalvin.resolver import resolve_plan
from kalvin.drift import evaluate_host_drift
from kalvin.validation import validate_bundle


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


class RequirementPolicySafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.architecture = copy.deepcopy(architecture)

    @property
    def policy(self) -> dict:
        return self.architecture.catalogs["host-requirements"]

    def codes(self) -> set[str]:
        return {item.code for item in validate_bundle(self.architecture).findings}

    def requirement(self, requirement_id: str = "host.os-family") -> dict:
        return next(item for item in self.policy["requirements"] if item["id"] == requirement_id)

    def test_unknown_requirement_id_rejected(self) -> None:
        with self.assertRaisesRegex(UserInputError, "Unknown host requirement"):
            requirement_by_id(self.policy, "synthetic.unknown")

    def test_duplicate_requirement_id_rejected(self) -> None:
        self.policy["requirements"].append(copy.deepcopy(self.policy["requirements"][0]))
        self.assertIn("duplicate-host-requirement", self.codes())

    def test_unknown_requirement_state_rejected(self) -> None:
        self.requirement()["profiles"]["core"] = "SYNTHETIC_UNKNOWN"
        self.assertIn("schema-validation", self.codes())

    def test_unknown_evidence_class_rejected(self) -> None:
        self.requirement()["evidence_class"] = "SYNTHETIC_UNKNOWN"
        self.assertIn("schema-validation", self.codes())

    def test_unknown_severity_rejected(self) -> None:
        self.policy["severity_policy"]["required_unsatisfied"] = "SYNTHETIC_UNKNOWN"
        self.assertIn("schema-validation", self.codes())

    def test_malformed_comparison_rule_rejected(self) -> None:
        self.requirement()["comparison"] = "SYNTHETIC_COMPARE"
        self.assertIn("schema-validation", self.codes())

    def test_incompatible_expected_value_type_rejected(self) -> None:
        self.requirement("runtime.python-version")["expected"] = True
        self.assertIn("schema-validation", self.codes())

    def test_unknown_observed_capability_rejected(self) -> None:
        self.requirement()["observation_path"] = "synthetic.private.capability"
        self.assertIn("schema-validation", self.codes())

    def test_executable_shell_in_remediation_rejected(self) -> None:
        self.policy["remediations"][0]["guidance"] = "systemctl restart synthetic.service"
        self.assertIn("executable-remediation", self.codes())

    def test_executable_shell_in_profile_guidance_rejected(self) -> None:
        remediation = next(item for item in self.policy["remediations"] if "guidance_by_profile" in item)
        remediation["guidance_by_profile"]["storage"] = "systemctl restart synthetic.service"
        self.assertIn("executable-remediation", self.codes())

    def test_executable_shell_in_component_guidance_rejected(self) -> None:
        remediation = next(item for item in self.policy["remediations"] if "guidance_by_component" in item)
        remediation["guidance_by_component"]["model-runtime"] = "systemctl restart synthetic.service"
        self.assertIn("executable-remediation", self.codes())

    def test_unknown_component_guidance_scope_rejected(self) -> None:
        remediation = next(item for item in self.policy["remediations"] if "guidance_by_component" in item)
        remediation["guidance_by_component"]["synthetic-unknown"] = "Synthetic guidance only."
        self.assertIn("unknown-guidance-component", self.codes())

    def test_human_decision_profile_override_cannot_set_expected_true(self) -> None:
        docker = self.requirement("host.docker-requirement")
        docker["profile_overrides"]["core"] = {"comparison": "EQUALS", "expected": True}
        self.assertIn("resolved-human-decision-expectation", self.codes())

    def test_automatic_fix_action_rejected(self) -> None:
        self.policy["remediations"][0]["action"] = "FIX"
        self.assertIn("schema-validation", self.codes())

    def test_arbitrary_command_execution_not_introduced(self) -> None:
        tree = ast.parse((ROOT / "kalvin/drift.py").read_text(encoding="utf-8"))
        imports = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        calls = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        self.assertFalse(imports & {"subprocess", "os", "socket"})
        self.assertFalse(calls & {"eval", "exec", "open"})

    def test_privilege_escalation_guidance_rejected(self) -> None:
        self.policy["remediations"][0]["guidance"] = "sudo approved-tool"
        self.assertIn("executable-remediation", self.codes())

    def test_network_probe_not_introduced(self) -> None:
        self.assertEqual(set(PROBE_ALLOWLIST), set(ProbeId))
        argv = {word for definition in PROBE_ALLOWLIST.values() for word in (definition.executable, *definition.arguments)}
        self.assertFalse(argv & {"ping", "curl", "wget", "nc", "nmap", "ssh"})

    def test_secret_bearing_path_rejected(self) -> None:
        self.requirement()["evidence_source"] = "/synthetic/secrets/policy.json"
        self.assertIn("secret-bearing-path", self.codes())

    def test_private_network_identity_not_emitted(self) -> None:
        observed = json.loads((FIXTURES / "synthetic-observed-host.json").read_text(encoding="utf-8"))
        private_value = "192." + "168.99.25"
        observed["network"]["links"][0]["address"] = private_value
        plan = resolve_plan("core", FIXTURES / "synthetic-core.lock.json", root=ROOT)
        report = evaluate_host_drift(plan, observed, self.policy)
        self.assertNotIn(private_value, stable_json(report))

    def test_live_observed_fixture_not_tracked(self) -> None:
        observed_fixtures = sorted(path.name for path in FIXTURES.glob("*observed-host*.json"))
        self.assertEqual(observed_fixtures, ["synthetic-observed-host.json"])

    def test_unsupported_policy_schema_rejected(self) -> None:
        self.policy["schema_version"] = "99.0.0"
        self.assertIn("schema-validation", self.codes())


if __name__ == "__main__":
    unittest.main()
