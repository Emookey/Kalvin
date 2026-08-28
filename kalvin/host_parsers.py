# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pure parsers and sanitizers for fixed local host observation sources."""

from __future__ import annotations

import json
import re
from typing import Any


class HostParseError(ValueError):
    """A bounded probe returned data outside its documented parser contract."""


def parse_os_release(text: str) -> dict[str, Any]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        value = raw_value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    family = values.get("ID")
    if not family:
        raise HostParseError("os-release has no ID")
    related = sorted(filter(None, values.get("ID_LIKE", "").split()))
    return {"family": family.lower(), "version": values.get("VERSION_ID"), "related_families": related}


def parse_cpu_info(text: str, *, architecture: str, logical_count: int | None) -> dict[str, Any]:
    sections = [section for section in text.split("\n\n") if section.strip()]
    records: list[dict[str, str]] = []
    for section in sections:
        record: dict[str, str] = {}
        for line in section.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                record[key.strip().lower()] = value.strip()
        if record:
            records.append(record)
    model = next(
        (
            record.get("model name") or record.get("processor") or record.get("cpu")
            for record in records
            if record.get("model name") or record.get("processor") or record.get("cpu")
        ),
        None,
    )
    package_ids = {record["physical id"] for record in records if "physical id" in record}
    core_pairs = {
        (record.get("physical id", "0"), record["core id"])
        for record in records
        if "core id" in record
    }
    return {
        "architecture": architecture or None,
        "logical_cpu_count": logical_count,
        "physical_package_count": len(package_ids) or None,
        "physical_core_count": len(core_pairs) or None,
        "model_class": model,
    }


def parse_meminfo(text: str) -> dict[str, int | None]:
    values: dict[str, int] = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([A-Za-z_()]+):\s+(\d+)\s+kB", line.strip())
        if match:
            values[match.group(1)] = int(match.group(2)) * 1024
    if "MemTotal" not in values:
        raise HostParseError("meminfo has no MemTotal")
    return {"total_bytes": values["MemTotal"], "available_bytes": values.get("MemAvailable")}


def sanitize_mount_target(target: str | None) -> str:
    if target == "/":
        return "ROOT"
    if target in {"/boot", "/boot/efi"}:
        return "BOOT"
    if target and (target == "/srv/kalvin-backups" or target.startswith("/srv/kalvin-backups/")):
        return "KALVIN_BACKUP_NAMESPACE"
    if target and (target == "/var/lib/kalvin" or target.startswith("/var/lib/kalvin/")):
        return "KALVIN_DATA_NAMESPACE"
    if target and (target == "/var/cache/kalvin" or target.startswith("/var/cache/kalvin/")):
        return "KALVIN_CACHE_NAMESPACE"
    if target and (target == "/etc/kalvin" or target.startswith("/etc/kalvin/")):
        return "KALVIN_CONFIGURATION_NAMESPACE"
    if target and (target == "/run/kalvin" or target.startswith("/run/kalvin/")):
        return "KALVIN_RUNTIME_NAMESPACE"
    if target and (target == "/opt/kalvin" or target.startswith("/opt/kalvin/")):
        return "KALVIN_PLATFORM_NAMESPACE"
    if target and any(target == base or target.startswith(base + "/") for base in ("/proc", "/sys", "/dev", "/run")):
        return "SYSTEM_PSEUDO_FILESYSTEM"
    return "OTHER"


def _load_json(text: str, label: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise HostParseError(f"malformed {label} JSON") from exc


def parse_lsblk(text: str) -> list[dict[str, Any]]:
    document = _load_json(text, "lsblk")
    if not isinstance(document, dict) or not isinstance(document.get("blockdevices"), list):
        raise HostParseError("lsblk JSON has no blockdevices array")
    devices: list[dict[str, Any]] = []

    def visit(item: Any) -> None:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise HostParseError("lsblk device is malformed")
        mountpoints = item.get("mountpoints")
        if mountpoints is None:
            singular = item.get("mountpoint")
            mountpoints = [singular] if singular else []
        if not isinstance(mountpoints, list):
            raise HostParseError("lsblk mountpoints is malformed")
        devices.append(
            {
                "name": item["name"],
                "type": item.get("type"),
                "size_bytes": int(item["size"]) if item.get("size") is not None else None,
                "filesystem_type": item.get("fstype"),
                "mount_classes": sorted({sanitize_mount_target(value) for value in mountpoints if isinstance(value, str)}),
                "rotational": bool(item["rota"]) if item.get("rota") is not None else None,
                "transport": item.get("tran"),
            }
        )
        for child in item.get("children", []):
            visit(child)

    for device in document["blockdevices"]:
        visit(device)
    return sorted(devices, key=lambda item: (item["name"], item["type"] or ""))


def parse_findmnt(text: str) -> list[dict[str, Any]]:
    document = _load_json(text, "findmnt")
    filesystems = document.get("filesystems") if isinstance(document, dict) else None
    if not isinstance(filesystems, list):
        raise HostParseError("findmnt JSON has no filesystems array")
    mounts: list[dict[str, Any]] = []

    def visit(item: Any) -> None:
        if not isinstance(item, dict):
            raise HostParseError("findmnt entry is malformed")
        mounts.append(
            {
                "target_class": sanitize_mount_target(item.get("target")),
                "filesystem_type": item.get("fstype"),
            }
        )
        for child in item.get("children", []):
            visit(child)

    for filesystem in filesystems:
        visit(filesystem)
    return sorted(mounts, key=lambda item: (item["target_class"], item["filesystem_type"] or ""))


def parse_ip_links(text: str) -> list[dict[str, Any]]:
    document = _load_json(text, "ip link")
    if not isinstance(document, list):
        raise HostParseError("ip link JSON is not an array")
    links: list[dict[str, Any]] = []
    for item in document:
        if not isinstance(item, dict) or not isinstance(item.get("ifname"), str):
            raise HostParseError("ip link entry is malformed")
        flags = item.get("flags") if isinstance(item.get("flags"), list) else []
        loopback = item["ifname"] == "lo" or "LOOPBACK" in flags or item.get("link_type") == "loopback"
        operstate = str(item.get("operstate", "UNKNOWN")).upper()
        links.append(
            {
                "name": item["ifname"],
                "classification": "LOOPBACK" if loopback else "NON_LOOPBACK",
                "operational_state": operstate if operstate in {"UP", "DOWN", "UNKNOWN", "DORMANT", "LOWERLAYERDOWN", "NOTPRESENT"} else "UNKNOWN",
            }
        )
    return sorted(links, key=lambda item: item["name"])


def parse_default_route(text: str) -> dict[str, Any]:
    document = _load_json(text, "ip route")
    if not isinstance(document, list):
        raise HostParseError("ip route JSON is not an array")
    interfaces = sorted({item.get("dev") for item in document if isinstance(item, dict) and isinstance(item.get("dev"), str)})
    return {"present": bool(document), "interfaces": interfaces}
