# SPDX-License-Identifier: AGPL-3.0-or-later
"""Local-only, sanitized observed-host assembly."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .host_parsers import (
    HostParseError,
    parse_cpu_info,
    parse_default_route,
    parse_findmnt,
    parse_ip_links,
    parse_lsblk,
    parse_meminfo,
    parse_os_release,
)
from .probes import LocalProbeRunner, ProbeId, ProbeResult, ProbeStatus, executable_capabilities


OBSERVATION_STATUSES = {"OBSERVED", "UNAVAILABLE", "INSUFFICIENT_PERMISSION", "UNSUPPORTED", "UNKNOWN"}


@dataclass(frozen=True)
class SourceResult:
    status: str
    text: str = ""


@dataclass(frozen=True)
class HostFacts:
    architecture: str
    kernel_release: str
    logical_cpu_count: int | None
    python_version: str
    systemd_booted: bool
    docker_socket_present: bool
    docker_socket_readable: bool

    @classmethod
    def current(cls) -> "HostFacts":
        socket_path = Path("/var/run/docker.sock")
        return cls(
            architecture=platform.machine(),
            kernel_release=platform.release(),
            logical_cpu_count=os.cpu_count(),
            python_version=platform.python_version(),
            systemd_booted=Path("/run/systemd/system").is_dir(),
            docker_socket_present=socket_path.exists(),
            docker_socket_readable=socket_path.exists() and os.access(socket_path, os.R_OK),
        )


class HostSources(Protocol):
    def os_release(self) -> SourceResult: ...

    def cpu_info(self) -> SourceResult: ...

    def mem_info(self) -> SourceResult: ...


class ProbeRunner(Protocol):
    def run(self, probe_id: ProbeId) -> ProbeResult: ...


class LocalHostSources:
    """Read only three explicit, non-secret local capability files."""

    @staticmethod
    def _read(path: Path) -> SourceResult:
        try:
            return SourceResult("OBSERVED", path.read_text(encoding="utf-8"))
        except PermissionError:
            return SourceResult("INSUFFICIENT_PERMISSION")
        except FileNotFoundError:
            return SourceResult("UNAVAILABLE")
        except (OSError, UnicodeError):
            return SourceResult("UNKNOWN")

    def os_release(self) -> SourceResult:
        return self._read(Path("/etc/os-release"))

    def cpu_info(self) -> SourceResult:
        return self._read(Path("/proc/cpuinfo"))

    def mem_info(self) -> SourceResult:
        return self._read(Path("/proc/meminfo"))


def _observation_status(result: ProbeResult) -> str:
    return {
        ProbeStatus.SUCCESS: "OBSERVED",
        ProbeStatus.COMMAND_MISSING: "UNAVAILABLE",
        ProbeStatus.PERMISSION_DENIED: "INSUFFICIENT_PERMISSION",
        ProbeStatus.TIMEOUT: "UNKNOWN",
        ProbeStatus.FAILED: "UNKNOWN",
        ProbeStatus.OUTPUT_LIMIT_EXCEEDED: "UNKNOWN",
    }[result.status]


def _parsed_probe(result: ProbeResult, parser: object, key: str) -> dict[str, object]:
    status = _observation_status(result)
    if status != "OBSERVED":
        return {"status": status, key: []}
    try:
        value = parser(result.stdout)  # type: ignore[operator]
    except (HostParseError, TypeError, ValueError):
        return {"status": "UNKNOWN", key: []}
    return {"status": "OBSERVED", key: value}


def _service_state(active: ProbeResult, enabled: ProbeResult) -> dict[str, object]:
    def active_value(result: ProbeResult) -> tuple[str, str]:
        if result.status == ProbeStatus.SUCCESS and result.stdout.strip() == "active":
            return "OBSERVED", "ACTIVE"
        if result.status == ProbeStatus.PERMISSION_DENIED:
            return "INSUFFICIENT_PERMISSION", "UNKNOWN"
        if result.status == ProbeStatus.COMMAND_MISSING:
            return "UNAVAILABLE", "UNKNOWN"
        if result.returncode == 4 or result.stdout.strip() == "unknown":
            return "OBSERVED", "NOT_INSTALLED"
        if result.stdout.strip() in {"inactive", "failed", "activating", "deactivating"}:
            return "OBSERVED", "INACTIVE"
        return "UNKNOWN", "UNKNOWN"

    def enabled_value(result: ProbeResult) -> str:
        value = result.stdout.strip()
        if result.status == ProbeStatus.SUCCESS and value in {"enabled", "enabled-runtime", "static", "indirect"}:
            return "ENABLED"
        if value in {"disabled", "masked"}:
            return value.upper()
        return "UNKNOWN"

    status, state = active_value(active)
    return {"status": status, "state": state, "enablement": enabled_value(enabled)}


class HostInspector:
    """Assemble a sanitized snapshot; it has no persistence or correction behavior."""

    def __init__(
        self,
        *,
        runner: ProbeRunner | None = None,
        sources: HostSources | None = None,
        facts: HostFacts | None = None,
        executables: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.runner = runner or LocalProbeRunner()
        self.sources = sources or LocalHostSources()
        self.facts = facts or HostFacts.current()
        self.executables = executables or executable_capabilities()

    def inspect(self) -> dict[str, object]:
        os_source = self.sources.os_release()
        operating_system: dict[str, object] = {
            "status": os_source.status,
            "family": None,
            "version": None,
            "related_families": [],
            "kernel_release": self.facts.kernel_release,
            "architecture": self.facts.architecture,
        }
        if os_source.status == "OBSERVED":
            try:
                operating_system.update(parse_os_release(os_source.text))
            except HostParseError:
                operating_system["status"] = "UNKNOWN"

        cpu_source = self.sources.cpu_info()
        cpu: dict[str, object] = {
            "status": cpu_source.status,
            "architecture": self.facts.architecture,
            "logical_cpu_count": self.facts.logical_cpu_count,
            "physical_package_count": None,
            "physical_core_count": None,
            "model_class": None,
        }
        if cpu_source.status == "OBSERVED":
            cpu.update(parse_cpu_info(cpu_source.text, architecture=self.facts.architecture, logical_count=self.facts.logical_cpu_count))

        memory_source = self.sources.mem_info()
        memory: dict[str, object] = {"status": memory_source.status, "total_bytes": None, "available_bytes": None}
        if memory_source.status == "OBSERVED":
            try:
                memory.update(parse_meminfo(memory_source.text))
            except HostParseError:
                memory["status"] = "UNKNOWN"

        block_storage = _parsed_probe(self.runner.run(ProbeId.LSBLK), parse_lsblk, "devices")
        filesystems = _parsed_probe(self.runner.run(ProbeId.FINDMNT), parse_findmnt, "mounts")
        links = _parsed_probe(self.runner.run(ProbeId.IP_LINK), parse_ip_links, "links")
        route_result = self.runner.run(ProbeId.IP_DEFAULT_ROUTE)
        network: dict[str, object] = {"status": links["status"], "links": links["links"], "default_route": {"status": _observation_status(route_result), "present": None, "interfaces": []}}
        if route_result.status == ProbeStatus.SUCCESS:
            try:
                network["default_route"] = {"status": "OBSERVED", **parse_default_route(route_result.stdout)}
            except HostParseError:
                network["default_route"] = {"status": "UNKNOWN", "present": None, "interfaces": []}

        systemd_available = bool(self.facts.systemd_booted and self.executables["systemctl"]["present"])
        systemd = {
            "status": "OBSERVED",
            "available": systemd_available,
            "booted_as_service_manager": self.facts.systemd_booted,
        }
        if systemd_available:
            services = {
                "docker": _service_state(self.runner.run(ProbeId.DOCKER_ACTIVE), self.runner.run(ProbeId.DOCKER_ENABLED)),
                "tailscale": _service_state(self.runner.run(ProbeId.TAILSCALE_ACTIVE), self.runner.run(ProbeId.TAILSCALE_ENABLED)),
            }
        else:
            services = {
                "docker": {"status": "UNAVAILABLE", "state": "UNKNOWN", "enablement": "UNKNOWN"},
                "tailscale": {"status": "UNAVAILABLE", "state": "UNKNOWN", "enablement": "UNKNOWN"},
            }

        docker = {
            "status": "OBSERVED",
            "cli": self.executables["docker"],
            "service": services["docker"],
            "socket": {
                "status": "OBSERVED",
                "present": self.facts.docker_socket_present,
                "readable": self.facts.docker_socket_readable if self.facts.docker_socket_present else False,
            },
            "daemon_details": "NOT_PROBED",
        }
        return {
            "schema_version": "1.0.0",
            "kind": "KALVIN_OBSERVED_HOST",
            "operating_system": operating_system,
            "cpu": cpu,
            "memory": memory,
            "block_storage": block_storage,
            "filesystems": filesystems,
            "systemd": systemd,
            "services": services,
            "executables": {key: self.executables[key] for key in sorted(self.executables)},
            "runtimes": {"python": {"status": "OBSERVED", "version": self.facts.python_version}},
            "docker": docker,
            "network": network,
        }
