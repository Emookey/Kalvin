# SPDX-License-Identifier: AGPL-3.0-or-later
"""Architecture validation tests using only in-memory synthetic mutations."""

from __future__ import annotations

import copy
import unittest
from pathlib import Path

from kalvin.loader import load_architecture
from kalvin.validation import sensitive_value_reason, validate_architecture, validate_bundle


ROOT = Path(__file__).resolve().parents[1]


class ArchitectureTestCase(unittest.TestCase):
    def setUp(self) -> None:
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.assertIsNotNone(architecture)
        self.architecture = copy.deepcopy(architecture)

    def codes(self) -> set[str]:
        return {item.code for item in validate_bundle(self.architecture).findings}

    def components(self) -> list[dict]:
        return self.architecture.catalogs["components"]["components"]

    def component(self, component_id: str) -> dict:
        return next(item for item in self.components() if item["id"] == component_id)


class PositiveArchitectureTests(ArchitectureTestCase):
    def test_repository_architecture_validates(self) -> None:
        _, result = validate_architecture(ROOT)
        self.assertTrue(result.valid, [item.render() for item in result.ordered()])

    def test_exact_profiles_are_present(self) -> None:
        self.assertEqual({item["id"] for item in self.architecture.profiles.values()}, {"lab", "core", "storage"})

    def test_state_classes_are_preserved(self) -> None:
        classes = {item["id"] for item in self.architecture.catalogs["vocabularies"]["state_classes"]}
        self.assertEqual(classes, {"AUTHORITATIVE", "DERIVED", "EPHEMERAL", "CONFIGURATION", "SECRET", "LOG"})

    def test_backup_classes_are_preserved(self) -> None:
        self.assertEqual(set(self.architecture.catalogs["vocabularies"]["backup_classes"]), {"REQUIRED", "REBUILDABLE", "EXCLUDED"})

    def test_core_requires_durable_rag_gate(self) -> None:
        self.assertIn("kal.rag-status-durable", self.architecture.profiles["core"]["required_readiness_gates"])

    def test_storage_excludes_application_compute(self) -> None:
        policy = {item["id"]: item["requirement"] for item in self.architecture.profiles["storage"]["components"]}
        self.assertTrue(all(policy[item] == "FORBIDDEN" for item in ("kal", "beepy", "model-runtime")))

    def test_public_test_exposure_is_default_off(self) -> None:
        policy = {item["id"]: item for item in self.architecture.profiles["lab"]["components"]}
        self.assertFalse(policy["public-test-exposure"]["default_enabled"])

    def test_model_runtime_is_provider_neutral(self) -> None:
        model = self.component("model-runtime")
        self.assertEqual(model["version"], {"source": "IMPLEMENTATION_LOCK", "repository_id": None, "immutable_resolution": True})
        self.assertNotIn("ollama", model["purpose"].lower())

    def test_application_identity_is_not_administrative(self) -> None:
        for component_id in ("kal", "beepy"):
            component = self.component(component_id)
            self.assertNotIn(component["identity_class"], {"PLATFORM_ADMINISTRATION", "FUTURE_RMM"})
            self.assertEqual(component["privilege_class"], "UNPRIVILEGED_APPLICATION")

    def test_configuration_precedence_is_exact(self) -> None:
        self.assertEqual(
            self.architecture.catalogs["vocabularies"]["configuration_source_layers"],
            ["REPOSITORY_SAFE_DEFAULTS", "PROFILE_CONFIGURATION", "HOST_LOCAL_CONFIGURATION", "DESIGNATED_GENERATED_VALUES"],
        )

    def test_schemas_use_draft_2020_12(self) -> None:
        self.assertTrue(all(schema["$schema"] == "https://json-schema.org/draft/2020-12/schema" for schema in self.architecture.schemas.values()))

    def test_core_storage_backup_identities_are_distinct(self) -> None:
        self.assertEqual(self.component("backup-client")["identity_class"], "BACKUP_SUBMISSION")
        self.assertEqual(self.component("storage-backup-target")["identity_class"], "STORAGE_RETENTION")


class NegativeArchitectureTests(ArchitectureTestCase):
    def test_unknown_component_rejected(self) -> None:
        self.architecture.profiles["lab"]["components"][0]["id"] = "unknown-component"
        self.assertIn("unknown-component", self.codes())

    def test_duplicate_component_id_rejected(self) -> None:
        duplicate = copy.deepcopy(self.components()[0])
        self.components().append(duplicate)
        self.assertIn("duplicate-component", self.codes())

    def test_missing_dependency_rejected(self) -> None:
        self.component("kal")["dependencies"][0]["component"] = "absent-component"
        self.assertIn("missing-dependency", self.codes())

    def test_dependency_cycle_rejected(self) -> None:
        self.component("monitoring")["dependencies"].append(
            {"component": "backup-client", "kind": "STARTUP", "required": True, "partial_operation": "Synthetic cycle edge."}
        )
        self.component("backup-client")["dependencies"].append(
            {"component": "monitoring", "kind": "STARTUP", "required": True, "partial_operation": "Synthetic cycle edge."}
        )
        self.assertIn("dependency-cycle", self.codes())

    def test_unknown_state_class_rejected(self) -> None:
        self.component("kal")["state_requirements"][0]["class"] = "UNKNOWN"
        self.assertIn("schema-validation", self.codes())

    def test_unknown_backup_class_rejected(self) -> None:
        self.component("kal")["state_requirements"][0]["backup"] = "UNKNOWN"
        self.assertIn("schema-validation", self.codes())

    def test_authoritative_rebuildable_rejected(self) -> None:
        self.component("kal")["state_requirements"][0]["backup"] = "REBUILDABLE"
        self.assertIn("authoritative-backup", self.codes())

    def test_derived_required_rejected(self) -> None:
        self.component("kal")["state_requirements"][1]["backup"] = "REQUIRED"
        self.assertIn("derived-promoted-to-authority", self.codes())

    def test_ephemeral_required_without_justification_rejected(self) -> None:
        runtime = next(item for item in self.component("kal")["state_requirements"] if item["class"] == "EPHEMERAL")
        runtime["backup"] = "REQUIRED"
        self.assertIn("ephemeral-required-backup", self.codes())

    def test_storage_application_component_rejected(self) -> None:
        selection = next(item for item in self.architecture.profiles["storage"]["components"] if item["id"] == "kal")
        selection.update(requirement="REQUIRED", default_enabled=True)
        self.assertIn("storage-application-compute", self.codes())

    def test_forbidden_public_exposure_rejected(self) -> None:
        self.component("monitoring")["exposure"]["allowed"].append("PUBLIC")
        self.assertIn("implicit-public-service", self.codes())

    def test_invalid_privilege_escalation_rejected(self) -> None:
        self.component("kal")["privilege_class"] = "HOST_ADMINISTRATIVE"
        self.assertIn("administrative-component", self.codes())

    def test_unknown_readiness_gate_rejected(self) -> None:
        self.component("kal")["readiness_gates"].append("unknown.gate")
        self.assertIn("unknown-readiness-gate", self.codes())

    def test_malformed_compatibility_declaration_rejected(self) -> None:
        self.architecture.catalogs["compatibility"]["entries"].append(
            {"id": "synthetic-legacy", "legacy_identifier": "GoodWill", "canonical_replacement": "Kalvin"}
        )
        self.assertIn("schema-validation", self.codes())

    def test_secret_looking_manifest_value_rejected(self) -> None:
        self.component("kal")["purpose"] = "token=" + "synthetic-sensitive-looking-value"
        self.assertIn("secret-looking-value", self.codes())

    def test_legacy_absolute_runtime_path_rejected(self) -> None:
        self.component("kal")["state_requirements"][0]["path"] = "/opt/" + "odysseus-ai/synthetic"
        self.assertIn("schema-validation", self.codes())

    def test_private_key_looking_fixture_rejected(self) -> None:
        marker = "-----BEGIN " + "PRIVATE KEY-----"
        self.assertEqual(sensitive_value_reason(marker), "private-key-looking material")


if __name__ == "__main__":
    unittest.main()
