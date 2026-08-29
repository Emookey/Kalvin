# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fail-closed remediation action catalog and planning-policy validation."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from kalvin.loader import load_architecture
from kalvin.validation import validate_bundle


ROOT = Path(__file__).resolve().parents[1]


class PlanningPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.architecture = copy.deepcopy(architecture)

    @property
    def policy(self) -> dict:
        return self.architecture.catalogs["remediation-actions"]

    def codes(self) -> set[str]:
        return {item.code for item in validate_bundle(self.architecture).findings}

    def action_class(self, action_id: str = "PACKAGE_OR_RUNTIME_PROVISION") -> dict:
        return next(item for item in self.policy["action_classes"] if item["id"] == action_id)

    def test_unknown_action_class_reference_rejected(self) -> None:
        rule = next(item for item in self.policy["finding_rules"] if item["disposition"] == "ACTION")
        rule["action_class"] = "SYNTHETIC_UNKNOWN"
        self.assertIn("unknown-action-class", self.codes())

    def test_unknown_risk_class_rejected(self) -> None:
        self.action_class()["default_risk"] = "SYNTHETIC_UNKNOWN"
        self.assertIn("schema-validation", self.codes())

    def test_unknown_approval_class_rejected(self) -> None:
        self.action_class()["required_approval_classes"] = ["SYNTHETIC_UNKNOWN"]
        self.assertIn("unknown-approval-class", self.codes())

    def test_unknown_scope_class_rejected(self) -> None:
        self.action_class()["scopes"] = ["SYNTHETIC_UNKNOWN"]
        self.assertIn("unknown-scope-class", self.codes())

    def test_unknown_rollback_and_failure_class_rejected(self) -> None:
        self.action_class()["rollback_class"] = "SYNTHETIC_UNKNOWN"
        self.assertIn("unknown-rollback-class", self.codes())
        self.action_class()["rollback_class"] = "DEFINED_REQUIRED"
        self.action_class()["failure_behavior"] = "SYNTHETIC_UNKNOWN"
        self.assertIn("unknown-failure-class", self.codes())

    def test_critical_action_cannot_be_automatic(self) -> None:
        action = self.action_class("STORAGE_CAPACITY_CHANGE")
        action["future_automatic_execution"] = "REQUIRES_SEPARATE_FUTURE_POLICY"
        codes = self.codes()
        self.assertIn("critical-automatic-action", codes)
        self.assertIn("prohibited-action-automatic", codes)

    def test_unknown_and_duplicate_finding_rules_rejected(self) -> None:
        self.policy["finding_rules"][0]["requirement_id"] = "synthetic.unknown"
        self.assertIn("unknown-rule-requirement", self.codes())
        self.policy["finding_rules"][0] = copy.deepcopy(self.policy["finding_rules"][1])
        self.assertIn("duplicate-finding-rule", self.codes())

    def test_policy_is_explicitly_non_operational(self) -> None:
        self.assertFalse(self.policy["operational"])
        self.assertFalse(self.policy["execution_available"])


if __name__ == "__main__":
    unittest.main()
