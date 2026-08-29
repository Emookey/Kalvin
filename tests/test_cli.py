# SPDX-License-Identifier: AGPL-3.0-or-later
"""End-to-end CLI exit and presentation tests."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "kalvin", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


class CliTests(unittest.TestCase):
    def test_help_lists_only_read_only_commands(self) -> None:
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("validate", result.stdout)
        self.assertIn("resolve", result.stdout)
        self.assertNotIn("--apply", result.stdout)

    def test_validate_success_exit(self) -> None:
        result = run_cli("validate")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("VALID", result.stdout)

    def test_core_json_resolution_success_exit(self) -> None:
        result = run_cli("resolve", "--profile", "core", "--lock", "tests/fixtures/synthetic-core.lock.json", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["production_readiness"], "BLOCKED_EXTERNAL_GATE")

    def test_storage_text_resolution_success_exit(self) -> None:
        result = run_cli("resolve", "--profile", "storage", "--lock", "tests/fixtures/synthetic-storage.lock.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Operational deployment: NONE", result.stdout)

    def test_unknown_profile_is_user_failure(self) -> None:
        result = run_cli("resolve", "--profile", "coree", "--lock", "tests/fixtures/synthetic-core.lock.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Available profiles", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_malformed_lock_is_user_failure(self) -> None:
        result = run_cli("resolve", "--profile", "core", "--lock", "schemas/repository-lock.schema.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("SCHEMA ERROR", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_host_help_lists_plan_but_no_execution_command(self) -> None:
        result = run_cli("host", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("plan", result.stdout)
        for command in ("apply", "execute", "fix", "repair", "rollback"):
            self.assertNotIn(command, result.stdout)

    def test_synthetic_host_plan_cli_is_planning_only(self) -> None:
        observed = json.loads(
            (ROOT / "tests/fixtures/synthetic-observed-host.json").read_text(encoding="utf-8")
        )
        from kalvin.cli import main

        with patch("kalvin.cli.HostInspector.inspect", return_value=observed):
            from contextlib import redirect_stderr, redirect_stdout
            import io

            output, error = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                exit_code = main(
                    [
                        "host",
                        "plan",
                        "--profile",
                        "core",
                        "--lock",
                        str(ROOT / "tests/fixtures/synthetic-core.lock.json"),
                        "--format",
                        "json",
                    ]
                )
        self.assertEqual(exit_code, 0, error.getvalue())
        plan = json.loads(output.getvalue())
        self.assertFalse(plan["execution_available"])
        self.assertEqual(plan["action_count"], 0)


if __name__ == "__main__":
    unittest.main()
