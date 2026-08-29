# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthetic, model-only approval binding and stale-plan tests."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from kalvin.drift import evaluate_host_drift
from kalvin.loader import load_architecture
from kalvin.models import UserInputError
from kalvin.remediation import (
    approval_state_for_plan,
    generate_remediation_plan,
    validate_approval_record,
)
from kalvin.resolver import resolve_plan


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


class ApprovalContractTests(unittest.TestCase):
    def setUp(self) -> None:
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.architecture = architecture
        self.requirement_policy = architecture.catalogs["host-requirements"]
        self.planning_policy = architecture.catalogs["remediation-actions"]
        self.plan_schema = architecture.schemas["remediation-plan.schema.json"]
        self.approval_schema = architecture.schemas["approval-record.schema.json"]
        self.observed = json.loads(
            (FIXTURES / "synthetic-observed-host.json").read_text(encoding="utf-8")
        )
        self.observed["executables"]["git"]["present"] = False

    def make_plan(self, planning_policy: dict | None = None) -> dict:
        resolved = resolve_plan("core", FIXTURES / "synthetic-core.lock.json", root=ROOT)
        drift = evaluate_host_drift(resolved, self.observed, self.requirement_policy)
        return generate_remediation_plan(
            resolved,
            drift,
            self.requirement_policy,
            planning_policy or self.planning_policy,
            plan_schema=self.plan_schema,
        )

    def record(self, plan: dict, **changes: object) -> dict:
        record = {
            "schema_version": "1.0.0",
            "kind": "KALVIN_REMEDIATION_APPROVAL_RECORD",
            "plan_fingerprint": plan["plan_fingerprint"],
            "plan_policy_version": plan["plan_policy_version"],
            "approval_class": "OPERATOR_APPROVAL",
            "approver_role_type": "SYNTHETIC_TEST_ROLE",
            "decision": "APPROVE",
            "state": "APPROVED",
            "scope": ["HOST_RUNTIME", "HOST_TOOLING"],
            "constraints": ["synthetic-model-validation-only"],
            "validity": {"mode": "UNTIL_STATE_CHANGE", "expires_at": None},
            "reason": "Synthetic approval contract fixture.",
            "synthetic_model_only": True,
        }
        record.update(changes)
        return record

    def test_approval_references_exact_plan_fingerprint(self) -> None:
        plan = self.make_plan()
        record = self.record(plan)
        validate_approval_record(record, approval_schema=self.approval_schema)
        self.assertEqual(record["plan_fingerprint"], plan["plan_fingerprint"])
        self.assertEqual(
            approval_state_for_plan(plan, record, approval_schema=self.approval_schema),
            "APPROVED",
        )

    def test_approval_targeting_different_plan_is_stale(self) -> None:
        plan = self.make_plan()
        record = self.record(
            plan, plan_fingerprint="sha256:" + ("0" * 64)
        )
        self.assertEqual(
            approval_state_for_plan(plan, record, approval_schema=self.approval_schema),
            "STALE",
        )

    def test_material_planning_policy_change_makes_old_approval_stale(self) -> None:
        old_plan = self.make_plan()
        old_record = self.record(old_plan)
        policy = copy.deepcopy(self.planning_policy)
        policy["policy_version"] = "1.0.1"
        action_class = next(
            item for item in policy["action_classes"]
            if item["id"] == "PACKAGE_OR_RUNTIME_PROVISION"
        )
        action_class["description"] += " Synthetic policy revision."
        new_plan = self.make_plan(policy)
        self.assertNotEqual(old_plan["plan_fingerprint"], new_plan["plan_fingerprint"])
        self.assertEqual(
            approval_state_for_plan(new_plan, old_record, approval_schema=self.approval_schema),
            "STALE",
        )

    def test_expiry_semantics_are_modelled(self) -> None:
        plan = self.make_plan()
        record = self.record(
            plan,
            validity={"mode": "EXPIRES", "expires_at": "SYNTHETIC-VALIDITY-BOUNDARY"},
            state="EXPIRED",
        )
        validate_approval_record(record, approval_schema=self.approval_schema)
        self.assertEqual(
            approval_state_for_plan(plan, record, approval_schema=self.approval_schema),
            "EXPIRED",
        )

    def test_unknown_approval_class_is_rejected(self) -> None:
        with self.assertRaisesRegex(UserInputError, "Invalid approval record schema|Unknown approval"):
            validate_approval_record(
                self.record(self.make_plan(), approval_class="SYNTHETIC_UNKNOWN"),
                approval_schema=self.approval_schema,
            )

    def test_real_identity_or_credentials_are_not_allowed(self) -> None:
        record = self.record(self.make_plan())
        record["hostname"] = "synthetic-private-host"
        with self.assertRaisesRegex(UserInputError, "private host identity"):
            validate_approval_record(record, approval_schema=self.approval_schema)
        record = self.record(self.make_plan(), reason="password=synthetic-sensitive")
        with self.assertRaisesRegex(UserInputError, "credential-like"):
            validate_approval_record(record, approval_schema=self.approval_schema)


if __name__ == "__main__":
    unittest.main()
