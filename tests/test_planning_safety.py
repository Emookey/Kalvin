# SPDX-License-Identifier: AGPL-3.0-or-later
"""Negative Phase 4G schema, graph, publication, and mutation-boundary tests."""

from __future__ import annotations

import ast
import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from kalvin.drift import evaluate_host_drift
from kalvin.loader import load_architecture
from kalvin.models import UserInputError
from kalvin.remediation import generate_remediation_plan, validate_action_graph, validate_remediation_plan
from kalvin.resolver import resolve_plan


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
RUNTIME = ROOT / "kalvin"


class PlanningSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        architecture, findings = load_architecture(ROOT)
        self.assertEqual(findings, [])
        self.architecture = architecture
        self.requirement_policy = architecture.catalogs["host-requirements"]
        self.planning_policy = architecture.catalogs["remediation-actions"]
        self.plan_schema = architecture.schemas["remediation-plan.schema.json"]
        self.resolved = resolve_plan("core", FIXTURES / "synthetic-core.lock.json", root=ROOT)
        self.observed = json.loads(
            (FIXTURES / "synthetic-observed-host.json").read_text(encoding="utf-8")
        )
        self.observed["executables"]["git"]["present"] = False
        self.drift = evaluate_host_drift(
            self.resolved, self.observed, self.requirement_policy
        )
        self.plan = generate_remediation_plan(
            self.resolved,
            self.drift,
            self.requirement_policy,
            self.planning_policy,
            plan_schema=self.plan_schema,
        )

    def assert_plan_rejected(self, change) -> None:
        plan = copy.deepcopy(self.plan)
        change(plan)
        with self.assertRaises(UserInputError):
            validate_remediation_plan(
                plan, self.planning_policy, plan_schema=self.plan_schema
            )

    def test_executable_fields_are_rejected(self) -> None:
        for field in ("command", "shell", "argv", "script"):
            with self.subTest(field=field):
                self.assert_plan_rejected(
                    lambda plan, field=field: plan["actions"][0].__setitem__(field, "synthetic")
                )

    def test_automatic_remediation_flag_is_rejected(self) -> None:
        self.assert_plan_rejected(
            lambda plan: plan.__setitem__("automatic_remediation", True)
        )

    def test_execution_available_true_is_rejected(self) -> None:
        self.assert_plan_rejected(
            lambda plan: plan.__setitem__("execution_available", True)
        )

    def test_unknown_action_risk_and_approval_classes_are_rejected(self) -> None:
        self.assert_plan_rejected(
            lambda plan: plan["actions"][0].__setitem__("action_class", "SYNTHETIC_UNKNOWN")
        )
        self.assert_plan_rejected(
            lambda plan: plan["actions"][0].__setitem__("risk", "SYNTHETIC_UNKNOWN")
        )
        self.assert_plan_rejected(
            lambda plan: plan["actions"][0]["approval"].__setitem__(
                "classes", ["SYNTHETIC_UNKNOWN"]
            )
        )

    def test_missing_dependency_is_rejected(self) -> None:
        actions = copy.deepcopy(self.plan["actions"])
        actions[0]["depends_on"] = ["synthetic-missing"]
        with self.assertRaisesRegex(UserInputError, "missing dependency"):
            validate_action_graph(actions)

    def test_dependency_cycle_is_rejected(self) -> None:
        actions = copy.deepcopy(self.plan["actions"])
        actions[0]["depends_on"] = [actions[0]["id"]]
        with self.assertRaisesRegex(UserInputError, "dependency cycle"):
            validate_action_graph(actions)

    def test_destructive_action_cannot_become_automatic(self) -> None:
        def mutate(plan: dict) -> None:
            action = plan["actions"][0]
            action["risk"] = "CRITICAL"
            action["approval"]["classes"] = ["PROHIBITED_AUTOMATICALLY"]
            action["future_automatic_execution"] = "REQUIRES_SEPARATE_FUTURE_POLICY"

        self.assert_plan_rejected(mutate)

    def test_secret_credential_network_and_hostname_values_are_rejected(self) -> None:
        for field, value in (
            ("reason", "password=synthetic-sensitive"),
            ("reason", "api_key=synthetic-sensitive"),
            ("reason", "192.168.25.10"),
            ("reason", "aa:bb:cc:dd:ee:ff"),
        ):
            with self.subTest(value=value):
                plan = copy.deepcopy(self.plan)
                plan["actions"][0]["why"] = value
                with self.assertRaises(UserInputError):
                    validate_remediation_plan(plan, self.planning_policy)
        drift = copy.deepcopy(self.drift)
        drift["hostname"] = "synthetic-private-host"
        with self.assertRaisesRegex(UserInputError, "private host identity"):
            generate_remediation_plan(
                self.resolved,
                drift,
                self.requirement_policy,
                self.planning_policy,
            )

    def test_action_catalog_rejects_executable_recipe_fields(self) -> None:
        schema = self.architecture.schemas["remediation-action-catalog.schema.json"]
        for field in ("command", "shell", "argv", "script"):
            with self.subTest(field=field):
                policy = copy.deepcopy(self.planning_policy)
                policy["action_classes"][0][field] = "synthetic"
                self.assertTrue(list(Draft202012Validator(schema).iter_errors(policy)))

    def test_catalog_marks_destructive_classes_never_automatic(self) -> None:
        by_id = {item["id"]: item for item in self.planning_policy["action_classes"]}
        for action_id in (
            "STORAGE_CAPACITY_CHANGE",
            "NETWORK_CONFIGURATION_CHANGE",
            "APPLICATION_MIGRATION",
            "SECRET_OR_CONFIGURATION_RESOLUTION",
        ):
            self.assertEqual(by_id[action_id]["future_automatic_execution"], "NEVER")

    def test_no_new_process_network_privilege_or_write_capability(self) -> None:
        subprocess_importers: list[str] = []
        forbidden_imports: list[str] = []
        write_calls: list[str] = []
        mutation_symbols = {
            "apply_remediation",
            "execute_remediation",
            "rollback_remediation",
            "persist_approval",
            "run_command",
        }
        found_symbols: set[str] = set()
        for path in sorted(RUNTIME.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        if root == "subprocess":
                            subprocess_importers.append(path.name)
                        if root in {"socket", "requests", "urllib", "http", "docker", "systemd"}:
                            forbidden_imports.append(f"{path.name}:{root}")
                if isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".")[0]
                    if root in {"socket", "requests", "urllib", "http", "docker", "systemd"}:
                        forbidden_imports.append(f"{path.name}:{root}")
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name in mutation_symbols:
                        found_symbols.add(node.name)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in {"write_text", "write_bytes", "mkdir", "unlink", "rename", "replace", "chmod", "chown"}:
                        write_calls.append(f"{path.name}:{node.func.attr}")
        self.assertEqual(subprocess_importers, ["probes.py"])
        self.assertEqual(forbidden_imports, [])
        self.assertEqual(write_calls, [])
        self.assertEqual(found_symbols, set())

    def test_planner_has_no_host_mutation_or_privilege_library(self) -> None:
        path = RUNTIME / "remediation.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported_roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported_roots.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertFalse(
            imported_roots
            & {"subprocess", "os", "socket", "requests", "docker", "systemd", "shlex"}
        )
        call_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertFalse(
            call_names
            & {"exec", "eval", "compile", "system", "Popen", "run", "check_call"}
        )

    def test_no_phase4g_approval_or_plan_persistence(self) -> None:
        planner = (RUNTIME / "remediation.py").read_text(encoding="utf-8")
        self.assertNotIn("write_text", planner)
        self.assertNotIn("write_bytes", planner)
        self.assertNotIn("sqlite", planner.lower())
        self.assertNotIn("shelve", planner.lower())

    def test_cli_has_no_execution_or_approval_persistence_commands(self) -> None:
        from kalvin.cli import build_parser

        help_text = build_parser().format_help()
        for command in (
            "apply",
            "execute",
            "fix",
            "repair",
            "approve-and-run",
            "rollback",
        ):
            self.assertNotIn(command, help_text)


if __name__ == "__main__":
    unittest.main()
