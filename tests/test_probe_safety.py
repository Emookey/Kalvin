# SPDX-License-Identifier: AGPL-3.0-or-later
"""Allowlist, failure, privacy, and no-mutation boundary tests."""

from __future__ import annotations

import ast
import copy
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from kalvin.cli import main
from kalvin.models import UserInputError
from kalvin.probes import LocalProbeRunner, PROBE_ALLOWLIST, ProbeId, ProbeStatus


ROOT = Path(__file__).resolve().parents[1]
HOST_RUNTIME = tuple(sorted(ROOT.joinpath("kalvin").glob("host_*.py"))) + (
    ROOT / "kalvin/probes.py",
    ROOT / "kalvin/preflight.py",
)


def synthetic_observed() -> dict:
    return json.loads((ROOT / "tests/fixtures/synthetic-observed-host.json").read_text())


class ProbeRunnerTests(unittest.TestCase):
    def test_arbitrary_command_cannot_be_requested(self) -> None:
        with self.assertRaisesRegex(UserInputError, "arbitrary command execution"):
            LocalProbeRunner().run("synthetic-command")  # type: ignore[arg-type]

    def test_unknown_probe_rejected(self) -> None:
        self.assertEqual(set(PROBE_ALLOWLIST), set(ProbeId))
        with self.assertRaises(UserInputError):
            LocalProbeRunner().run(object())  # type: ignore[arg-type]

    @patch("kalvin.probes.find_trusted_executable", return_value="/usr/bin/lsblk")
    @patch("kalvin.probes.subprocess.run")
    def test_runner_uses_exact_argv_timeout_environment_and_no_shell(self, run_mock: object, _which: object) -> None:
        run_mock.return_value = subprocess.CompletedProcess([], 0, b'{"blockdevices": []}', b"")  # type: ignore[attr-defined]
        LocalProbeRunner().run(ProbeId.LSBLK)
        args, kwargs = run_mock.call_args  # type: ignore[attr-defined]
        self.assertEqual(args[0], ["/usr/bin/lsblk", "--json", "--bytes", "--output", "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,ROTA,TRAN"])
        self.assertIs(kwargs["shell"], False)
        self.assertEqual(kwargs["timeout"], 3.0)
        self.assertEqual(set(kwargs["env"]), {"LC_ALL", "LANG", "PATH"})

    @patch("kalvin.probes.find_trusted_executable", return_value="/usr/bin/lsblk")
    @patch("kalvin.probes.subprocess.run", side_effect=subprocess.TimeoutExpired(["lsblk"], 3))
    def test_probe_timeout_handled(self, _run: object, _which: object) -> None:
        self.assertEqual(LocalProbeRunner().run(ProbeId.LSBLK).status, ProbeStatus.TIMEOUT)

    @patch("kalvin.probes.find_trusted_executable", return_value=None)
    def test_command_missing_handled(self, _which: object) -> None:
        self.assertEqual(LocalProbeRunner().run(ProbeId.LSBLK).status, ProbeStatus.COMMAND_MISSING)

    @patch("kalvin.probes.find_trusted_executable", return_value="/usr/bin/lsblk")
    @patch("kalvin.probes.subprocess.run")
    def test_permission_denied_handled_without_escalation(self, run_mock: object, _which: object) -> None:
        run_mock.return_value = subprocess.CompletedProcess([], 1, b"", b"permission denied")  # type: ignore[attr-defined]
        self.assertEqual(LocalProbeRunner().run(ProbeId.LSBLK).status, ProbeStatus.PERMISSION_DENIED)

    @patch("kalvin.probes.find_trusted_executable", return_value="/usr/bin/lsblk")
    @patch("kalvin.probes.subprocess.run")
    def test_output_limit_is_enforced(self, run_mock: object, _which: object) -> None:
        run_mock.return_value = subprocess.CompletedProcess([], 0, b"x" * 262145, b"")  # type: ignore[attr-defined]
        self.assertEqual(LocalProbeRunner().run(ProbeId.LSBLK).status, ProbeStatus.OUTPUT_LIMIT_EXCEEDED)


class MutationBoundaryTests(unittest.TestCase):
    def parsed_sources(self) -> list[tuple[Path, ast.AST]]:
        return [(path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path))) for path in HOST_RUNTIME]

    def test_subprocess_import_is_centralized(self) -> None:
        imports: list[str] = []
        for path, tree in self.parsed_sources():
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                    if any(name.split(".")[0] == "subprocess" for name in names):
                        imports.append(path.name)
        self.assertEqual(imports, ["probes.py"])

    def test_shell_true_os_system_eval_and_exec_calls_absent(self) -> None:
        forbidden: list[str] = []
        for path, tree in self.parsed_sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                        forbidden.append(f"{path.name}:{node.func.id}")
                    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "system":
                        forbidden.append(f"{path.name}:os.system")
                    if any(keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in node.keywords):
                        forbidden.append(f"{path.name}:shell=True")
        self.assertEqual(forbidden, [])

    def test_no_network_or_ssh_client_imports(self) -> None:
        forbidden_roots = {"socket", "requests", "urllib", "http", "paramiko", "fabric", "asyncssh"}
        hits: list[str] = []
        for path, tree in self.parsed_sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    hits.extend(alias.name for alias in node.names if alias.name.split(".")[0] in forbidden_roots)
                if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in forbidden_roots:
                    hits.append(node.module)
        self.assertEqual(hits, [])

    def test_allowlist_contains_only_read_only_commands(self) -> None:
        self.assertEqual({item.executable for item in PROBE_ALLOWLIST.values()}, {"lsblk", "findmnt", "ip", "systemctl"})
        self.assertNotIn("OPTIONS", {argument for item in PROBE_ALLOWLIST.values() for argument in item.arguments})
        for probe, definition in PROBE_ALLOWLIST.items():
            if definition.executable == "systemctl":
                self.assertIn(definition.arguments[0], {"is-active", "is-enabled"}, probe)
            if definition.executable == "ip":
                self.assertEqual(definition.arguments[0], "-j")

    def test_privilege_escalation_and_mutation_verbs_absent_from_allowlist(self) -> None:
        argv = {word for definition in PROBE_ALLOWLIST.values() for word in (definition.executable, *definition.arguments)}
        forbidden = {"sudo", "su", "doas", "run", "start", "stop", "restart", "exec", "rm", "up", "down", "enable", "disable", "install", "remove", "mount", "umount", "mkfs", "parted", "fdisk", "chown", "chmod", "useradd", "usermod", "groupadd", "passwd", "ssh", "scp", "rsync", "curl", "wget"}
        self.assertEqual(argv & forbidden, set())

    def test_no_runtime_filesystem_write_calls(self) -> None:
        methods = {"write_text", "write_bytes", "mkdir", "touch", "unlink", "rename", "replace", "chmod", "chown"}
        hits: list[str] = []
        for path, tree in self.parsed_sources():
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in methods:
                    hits.append(f"{path.name}:{node.func.attr}")
        self.assertEqual(hits, [])

    def test_secret_bearing_sources_absent(self) -> None:
        text = "\n".join(path.read_text(encoding="utf-8") for path in HOST_RUNTIME)
        fragments = ("/." + "env", "/" + "environ", "docker " + "inspect", "Environment" + "=", "PRIVATE " + "KEY")
        self.assertEqual([fragment for fragment in fragments if fragment in text], [])

    def test_cli_has_no_mutating_host_subcommands(self) -> None:
        from kalvin.cli import build_parser

        help_text = build_parser().format_help()
        for command in ("apply", "fix", "repair", "install", "configure", "bootstrap"):
            self.assertNotIn(command, help_text)

    def test_inspect_command_creates_no_files(self) -> None:
        observed = synthetic_observed()
        with tempfile.TemporaryDirectory() as temp, patch("kalvin.cli.HostInspector.inspect", return_value=observed):
            before = set(Path(temp).iterdir())
            previous = Path.cwd()
            try:
                os.chdir(temp)
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    exit_code = main(["host", "inspect", "--format", "json"])
            finally:
                os.chdir(previous)
            self.assertEqual(exit_code, 0)
            self.assertEqual(set(Path(temp).iterdir()), before)

    def test_preflight_command_creates_no_files(self) -> None:
        observed = synthetic_observed()
        lock = ROOT / "tests/fixtures/synthetic-core.lock.json"
        with tempfile.TemporaryDirectory() as temp, patch("kalvin.cli.HostInspector.inspect", return_value=copy.deepcopy(observed)):
            before = set(Path(temp).iterdir())
            previous = Path.cwd()
            try:
                os.chdir(temp)
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    exit_code = main(["host", "preflight", "--profile", "core", "--lock", str(lock), "--format", "json"])
            finally:
                os.chdir(previous)
            self.assertEqual(exit_code, 0)
            self.assertEqual(set(Path(temp).iterdir()), before)


if __name__ == "__main__":
    unittest.main()
