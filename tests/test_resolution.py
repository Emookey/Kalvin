# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deterministic resolution and immutable lock tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from kalvin.loader import load_architecture
from kalvin.lockfile import validate_lock_document
from kalvin.models import UserInputError
from kalvin.output import stable_json
from kalvin.resolver import resolve_plan


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


class ResolutionTests(unittest.TestCase):
    def plan(self, profile: str, *, enabled: tuple[str, ...] = ()) -> dict:
        return resolve_plan(profile, FIXTURES / f"synthetic-{profile}.lock.json", enabled_optional=enabled, root=ROOT)

    def test_lab_resolves_with_development_refs_bound_to_commits(self) -> None:
        plan = self.plan("lab", enabled=("kal", "beepy", "model-runtime"))
        self.assertEqual(plan["resolution_status"], "RESOLVED")
        self.assertTrue(all(len(item["resolved_commit"]) == 40 for item in plan["repository_locks"]))

    def test_core_structurally_resolves(self) -> None:
        self.assertEqual(self.plan("core")["resolution_status"], "RESOLVED")

    def test_storage_resolves_without_application_pins(self) -> None:
        plan = self.plan("storage")
        self.assertEqual(plan["repository_locks"], [])
        self.assertEqual({item["id"] for item in plan["components"]}, {"monitoring", "storage-backup-target"})

    def test_json_is_byte_identical_for_identical_inputs(self) -> None:
        first = stable_json(self.plan("core")).encode()
        second = stable_json(self.plan("core")).encode()
        self.assertEqual(first, second)

    def test_component_order_is_stable(self) -> None:
        plan = self.plan("core")
        self.assertEqual(plan["dependency_order"], sorted(plan["dependency_order"]))

    def test_required_components_are_included(self) -> None:
        selected = {item["id"] for item in self.plan("core")["components"]}
        self.assertTrue({"kal", "beepy", "model-runtime", "monitoring", "backup-client"} <= selected)

    def test_optional_components_remain_default_off(self) -> None:
        policy = {item["id"]: item["disposition"] for item in self.plan("core")["component_policy"]}
        self.assertEqual(policy["network-overlay"], "AVAILABLE_DEFAULT_OFF")

    def test_optional_components_can_be_explicitly_selected(self) -> None:
        document = json.loads((FIXTURES / "synthetic-core.lock.json").read_text())
        document["locks"].append(
            {"kind": "IMPLEMENTATION", "component_id": "network-overlay", "desired_ref": "overlay-contract", "resolved_version": "1.0.0"}
        )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.lock.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            plan = resolve_plan("core", path, enabled_optional=("network-overlay",), root=ROOT)
        self.assertIn("network-overlay", {item["id"] for item in plan["components"]})

    def test_state_and_backup_policy_are_preserved(self) -> None:
        state = {item["id"]: item for item in self.plan("core")["state_declarations"]}
        self.assertEqual(state["kal-authoritative"]["backup_policy"], "REQUIRED")
        self.assertEqual(state["kal-vector-index"]["state_class"], "DERIVED")
        self.assertEqual(state["kal-vector-index"]["backup_policy"], "REBUILDABLE")

    def test_secret_references_are_identifiers_only(self) -> None:
        refs = self.plan("core")["secret_references"]
        self.assertTrue(refs)
        self.assertTrue(all(set(item) == {"id", "component", "required", "resolution"} for item in refs))
        self.assertTrue(all(item["resolution"] == "REFERENCE_ONLY" for item in refs))

    def test_core_rag_gate_is_external_unverified(self) -> None:
        gates = {item["id"]: item for item in self.plan("core")["readiness_gates"]}
        self.assertEqual(gates["kal.rag-status-durable"]["verification_scope"], "EXTERNAL")
        self.assertEqual(gates["kal.rag-status-durable"]["status"], "UNVERIFIED")

    def test_core_is_not_production_ready(self) -> None:
        self.assertEqual(self.plan("core")["production_readiness"], "BLOCKED_EXTERNAL_GATE")

    def test_public_test_exposure_remains_unselected(self) -> None:
        policy = {item["id"]: item["disposition"] for item in self.plan("lab")["component_policy"]}
        self.assertEqual(policy["public-test-exposure"], "AVAILABLE_DEFAULT_OFF")

    def test_model_runtime_plan_remains_provider_neutral(self) -> None:
        component = next(item for item in self.plan("core")["components"] if item["id"] == "model-runtime")
        self.assertEqual(component["version_source"], "IMPLEMENTATION_LOCK")
        self.assertNotIn("ollama", stable_json(component).lower())

    def test_configuration_requirements_are_not_values(self) -> None:
        requirements = self.plan("core")["configuration_requirements"]
        self.assertTrue(requirements)
        self.assertTrue(all("value" not in item for item in requirements))

    def test_resolved_plan_matches_documented_schema(self) -> None:
        schema = json.loads((ROOT / "schemas/resolved-plan.schema.json").read_text())
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(self.plan("core"))), [])

    def test_observed_state_is_explicitly_not_evaluated(self) -> None:
        self.assertEqual(self.plan("core")["observed_or_deployed_state"], "NOT_EVALUATED_BY_PHASE_4D")


class NegativeResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.architecture = architecture
        self.core = json.loads((FIXTURES / "synthetic-core.lock.json").read_text())

    def validate(self, document: dict) -> None:
        validate_lock_document(document, self.architecture)

    def test_unknown_profile_rejected(self) -> None:
        with self.assertRaisesRegex(UserInputError, "Available profiles"):
            resolve_plan("coree", FIXTURES / "synthetic-core.lock.json", root=ROOT)

    def test_unknown_component_rejected(self) -> None:
        with self.assertRaisesRegex(UserInputError, "Unknown component"):
            resolve_plan("core", FIXTURES / "synthetic-core.lock.json", enabled_optional=("unknown",), root=ROOT)

    def test_forbidden_storage_component_rejected(self) -> None:
        with self.assertRaisesRegex(UserInputError, "Forbidden component"):
            resolve_plan("storage", FIXTURES / "synthetic-storage.lock.json", enabled_optional=("kal",), root=ROOT)

    def test_missing_repository_lock_rejected(self) -> None:
        document = {"schema_version": "1.0.0", "locks": self.core["locks"][2:]}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.lock.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(UserInputError, "Missing repository lock"):
                resolve_plan("core", path, root=ROOT)

    def test_unresolved_branch_as_commit_rejected(self) -> None:
        self.core["locks"][0]["resolved_commit"] = "refs/heads/development"
        with self.assertRaisesRegex(UserInputError, "full 40-hex"):
            self.validate(self.core)

    def test_short_commit_rejected(self) -> None:
        self.core["locks"][0]["resolved_commit"] = "1234abcd"
        with self.assertRaisesRegex(UserInputError, "full 40-hex"):
            self.validate(self.core)

    def test_malformed_commit_rejected(self) -> None:
        self.core["locks"][0]["resolved_commit"] = "z" * 40
        with self.assertRaisesRegex(UserInputError, "full 40-hex"):
            self.validate(self.core)

    def test_development_application_ref_in_core_rejected(self) -> None:
        self.core["locks"][0]["desired_ref"] = "refs/heads/development"
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.lock.json"
            path.write_text(json.dumps(self.core), encoding="utf-8")
            with self.assertRaisesRegex(UserInputError, "rejects development"):
                resolve_plan("core", path, root=ROOT)

    def test_missing_selected_dependency_rejected(self) -> None:
        with self.assertRaisesRegex(UserInputError, "Missing dependency"):
            resolve_plan("lab", FIXTURES / "synthetic-lab.lock.json", enabled_optional=("public-test-exposure",), root=ROOT)

    def test_ambiguous_head_ref_rejected(self) -> None:
        self.core["locks"][0]["desired_ref"] = "HEAD"
        with self.assertRaisesRegex(UserInputError, "ambiguous"):
            self.validate(self.core)

    def test_credential_bearing_source_url_rejected(self) -> None:
        self.core["locks"][0]["source_identity"] = "https://" + "synthetic:credential@" + "example.invalid/repo"
        with self.assertRaisesRegex(UserInputError, "SCHEMA ERROR"):
            self.validate(self.core)

    def test_secret_looking_lock_value_rejected(self) -> None:
        self.core["locks"][0]["desired_ref"] = "password=" + "synthetic-value"
        with self.assertRaisesRegex(UserInputError, "secret-looking"):
            self.validate(self.core)

    def test_duplicate_repository_lock_rejected(self) -> None:
        self.core["locks"].append(dict(self.core["locks"][0]))
        with self.assertRaisesRegex(UserInputError, "duplicate repository lock"):
            self.validate(self.core)


if __name__ == "__main__":
    unittest.main()
