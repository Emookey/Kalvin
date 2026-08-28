# SPDX-License-Identifier: AGPL-3.0-or-later
"""Static evidence for the bounded Phase 4D runtime implementation."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "kalvin"


class HostMutationBoundaryTests(unittest.TestCase):
    def sources(self) -> list[Path]:
        return sorted(RUNTIME.glob("*.py"))

    def test_process_execution_is_confined_to_phase4e_probe_module(self) -> None:
        forbidden = {"socket", "requests", "urllib", "http", "paramiko", "docker", "systemd", "fabric"}
        found: list[str] = []
        for path in self.sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    found.extend(alias.name for alias in node.names if alias.name.split(".")[0] in forbidden)
                if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in forbidden:
                    found.append(node.module)
        self.assertEqual(found, [])
        subprocess_importers = []
        for path in self.sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(alias.name == "subprocess" for alias in node.names):
                    subprocess_importers.append(path.name)
        self.assertEqual(subprocess_importers, ["probes.py"])

    def test_no_runtime_filesystem_write_calls(self) -> None:
        forbidden_methods = {"write_text", "write_bytes", "mkdir", "touch", "unlink", "rename", "replace", "chmod", "chown"}
        found: list[str] = []
        for path in self.sources():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_methods:
                    found.append(f"{path.name}:{node.func.attr}")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                    if len(node.args) > 1 or any(keyword.arg == "mode" for keyword in node.keywords):
                        found.append(f"{path.name}:open-with-mode")
        self.assertEqual(found, [])

    def test_no_host_mutation_or_network_execution_symbols(self) -> None:
        forbidden = ("os.system", "shell=True", "create_subprocess", "Popen(", "socket.")
        text = "\n".join(path.read_text(encoding="utf-8") for path in self.sources())
        self.assertEqual([item for item in forbidden if item in text], [])

    def test_cli_has_no_apply_deploy_install_or_service_commands(self) -> None:
        from kalvin.cli import build_parser

        help_text = build_parser().format_help()
        self.assertNotIn("--apply", help_text)
        for command in ("deploy", "install", "start", "stop", "restart"):
            self.assertNotIn(f"  {command}", help_text)


if __name__ == "__main__":
    unittest.main()
