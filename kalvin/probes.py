# SPDX-License-Identifier: AGPL-3.0-or-later
"""Auditable execution of a fixed local read-only probe allowlist."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from .models import UserInputError


TRUSTED_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
MINIMAL_ENVIRONMENT = MappingProxyType({"LC_ALL": "C", "LANG": "C", "PATH": TRUSTED_PATH})


class ProbeId(str, Enum):
    LSBLK = "lsblk"
    FINDMNT = "findmnt"
    IP_LINK = "ip-link"
    IP_DEFAULT_ROUTE = "ip-default-route"
    DOCKER_ACTIVE = "docker-service-active"
    DOCKER_ENABLED = "docker-service-enabled"
    TAILSCALE_ACTIVE = "tailscale-service-active"
    TAILSCALE_ENABLED = "tailscale-service-enabled"


class ProbeStatus(str, Enum):
    SUCCESS = "SUCCESS"
    COMMAND_MISSING = "COMMAND_MISSING"
    TIMEOUT = "TIMEOUT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    FAILED = "FAILED"
    OUTPUT_LIMIT_EXCEEDED = "OUTPUT_LIMIT_EXCEEDED"


@dataclass(frozen=True)
class ProbeDefinition:
    executable: str
    arguments: tuple[str, ...]
    timeout_seconds: float = 3.0
    maximum_stdout_bytes: int = 262_144
    maximum_stderr_bytes: int = 8_192


@dataclass(frozen=True)
class ProbeResult:
    probe_id: ProbeId
    status: ProbeStatus
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None


PROBE_ALLOWLIST = MappingProxyType(
    {
        ProbeId.LSBLK: ProbeDefinition(
            "lsblk",
            ("--json", "--bytes", "--output", "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,ROTA,TRAN"),
        ),
        ProbeId.FINDMNT: ProbeDefinition("findmnt", ("--json", "--output", "TARGET,FSTYPE,OPTIONS")),
        ProbeId.IP_LINK: ProbeDefinition("ip", ("-j", "link", "show")),
        ProbeId.IP_DEFAULT_ROUTE: ProbeDefinition("ip", ("-j", "route", "show", "default")),
        ProbeId.DOCKER_ACTIVE: ProbeDefinition("systemctl", ("is-active", "docker.service")),
        ProbeId.DOCKER_ENABLED: ProbeDefinition("systemctl", ("is-enabled", "docker.service")),
        ProbeId.TAILSCALE_ACTIVE: ProbeDefinition("systemctl", ("is-active", "tailscaled.service")),
        ProbeId.TAILSCALE_ENABLED: ProbeDefinition("systemctl", ("is-enabled", "tailscaled.service")),
    }
)


def find_trusted_executable(name: str) -> str | None:
    """Resolve a named capability only through the fixed non-user PATH."""
    return shutil.which(name, path=TRUSTED_PATH)


class LocalProbeRunner:
    """Run one enum-selected definition; callers cannot provide argv or flags."""

    def run(self, probe_id: ProbeId) -> ProbeResult:
        if not isinstance(probe_id, ProbeId) or probe_id not in PROBE_ALLOWLIST:
            raise UserInputError(f"Unknown probe {probe_id!r}; arbitrary command execution is unavailable")
        definition = PROBE_ALLOWLIST[probe_id]
        executable = find_trusted_executable(definition.executable)
        if executable is None:
            return ProbeResult(probe_id, ProbeStatus.COMMAND_MISSING)
        command = [executable, *definition.arguments]
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                check=False,
                timeout=definition.timeout_seconds,
                cwd="/",
                env=dict(MINIMAL_ENVIRONMENT),
            )
        except subprocess.TimeoutExpired:
            return ProbeResult(probe_id, ProbeStatus.TIMEOUT)
        except PermissionError:
            return ProbeResult(probe_id, ProbeStatus.PERMISSION_DENIED)
        except OSError:
            return ProbeResult(probe_id, ProbeStatus.FAILED)

        if (
            len(completed.stdout) > definition.maximum_stdout_bytes
            or len(completed.stderr) > definition.maximum_stderr_bytes
        ):
            return ProbeResult(probe_id, ProbeStatus.OUTPUT_LIMIT_EXCEEDED, returncode=completed.returncode)
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        lowered = stderr.lower()
        if completed.returncode == 0:
            status = ProbeStatus.SUCCESS
        elif "permission denied" in lowered or "access denied" in lowered or "not authorized" in lowered:
            status = ProbeStatus.PERMISSION_DENIED
        else:
            status = ProbeStatus.FAILED
        return ProbeResult(probe_id, status, stdout, stderr, completed.returncode)


def executable_capabilities() -> dict[str, dict[str, object]]:
    """Observe only the presence of explicitly relevant executable capabilities."""
    capabilities: dict[str, dict[str, object]] = {}
    for identifier, executable in (
        ("docker", "docker"),
        ("findmnt", "findmnt"),
        ("git", "git"),
        ("ip", "ip"),
        ("lsblk", "lsblk"),
        ("python", "python3"),
        ("systemctl", "systemctl"),
    ):
        resolved = find_trusted_executable(executable)
        capabilities[identifier] = {
            "status": "OBSERVED" if resolved else "UNAVAILABLE",
            "present": bool(resolved),
        }
    return capabilities
