# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthetic parser and observed-host assembly tests; no live inspection."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from kalvin.host_inspector import HostFacts, HostInspector, SourceResult
from kalvin.host_parsers import (
    HostParseError,
    parse_cpu_info,
    parse_default_route,
    parse_findmnt,
    parse_ip_links,
    parse_lsblk,
    parse_meminfo,
    parse_os_release,
)
from kalvin.probes import ProbeId, ProbeResult, ProbeStatus


ROOT = Path(__file__).resolve().parents[1]


class SyntheticSources:
    def __init__(self, os_status: str = "OBSERVED") -> None:
        self.os_status = os_status

    def os_release(self) -> SourceResult:
        return SourceResult(self.os_status, 'ID="ubuntu"\nVERSION_ID="24.04"\nID_LIKE="debian"\n')

    def cpu_info(self) -> SourceResult:
        return SourceResult(
            "OBSERVED",
            "processor : 0\nphysical id : 0\ncore id : 0\nmodel name : Synthetic CPU\n\n"
            "processor : 1\nphysical id : 0\ncore id : 1\nmodel name : Synthetic CPU\n",
        )

    def mem_info(self) -> SourceResult:
        return SourceResult("OBSERVED", "MemTotal:       16777216 kB\nMemAvailable:   12582912 kB\n")


class SyntheticRunner:
    def __init__(self, overrides: dict[ProbeId, ProbeResult] | None = None) -> None:
        self.results = {
            ProbeId.LSBLK: ProbeResult(
                ProbeId.LSBLK,
                ProbeStatus.SUCCESS,
                json.dumps({"blockdevices": [{"name": "vd-synthetic", "type": "disk", "size": 1000000, "fstype": None, "mountpoints": [None], "rota": False, "tran": "virtio"}]}),
            ),
            ProbeId.FINDMNT: ProbeResult(
                ProbeId.FINDMNT,
                ProbeStatus.SUCCESS,
                json.dumps({"filesystems": [{"target": "/", "fstype": "ext4", "options": "rw,relatime"}]}),
            ),
            ProbeId.IP_LINK: ProbeResult(
                ProbeId.IP_LINK,
                ProbeStatus.SUCCESS,
                json.dumps([{"ifname": "lo", "flags": ["LOOPBACK", "UP"], "operstate": "UP", "address": "discarded"}, {"ifname": "synthetic0", "flags": ["UP"], "operstate": "UP", "address": "discarded"}]),
            ),
            ProbeId.IP_DEFAULT_ROUTE: ProbeResult(
                ProbeId.IP_DEFAULT_ROUTE,
                ProbeStatus.SUCCESS,
                json.dumps([{"dst": "default", "dev": "synthetic0", "gateway": "discarded"}]),
            ),
            ProbeId.DOCKER_ACTIVE: ProbeResult(ProbeId.DOCKER_ACTIVE, ProbeStatus.SUCCESS, "active\n", returncode=0),
            ProbeId.DOCKER_ENABLED: ProbeResult(ProbeId.DOCKER_ENABLED, ProbeStatus.SUCCESS, "enabled\n", returncode=0),
            ProbeId.TAILSCALE_ACTIVE: ProbeResult(ProbeId.TAILSCALE_ACTIVE, ProbeStatus.FAILED, "inactive\n", returncode=3),
            ProbeId.TAILSCALE_ENABLED: ProbeResult(ProbeId.TAILSCALE_ENABLED, ProbeStatus.FAILED, "disabled\n", returncode=1),
        }
        self.results.update(overrides or {})

    def run(self, probe_id: ProbeId) -> ProbeResult:
        return self.results[probe_id]


EXECUTABLES = {
    key: {"status": "OBSERVED", "present": True}
    for key in ("docker", "findmnt", "git", "ip", "lsblk", "python", "systemctl")
}
FACTS = HostFacts("x86_64", "6.8.0-synthetic", 2, "3.12.0", True, True, False)


class ParserTests(unittest.TestCase):
    def test_os_parsing(self) -> None:
        self.assertEqual(parse_os_release('ID="ubuntu"\nVERSION_ID="24.04"\nID_LIKE="debian linux"\n')["family"], "ubuntu")

    def test_cpu_parsing_and_model(self) -> None:
        result = parse_cpu_info(SyntheticSources().cpu_info().text, architecture="x86_64", logical_count=2)
        self.assertEqual(result["model_class"], "Synthetic CPU")
        self.assertEqual(result["physical_core_count"], 2)

    def test_memory_parsing(self) -> None:
        result = parse_meminfo("MemTotal: 1024 kB\nMemAvailable: 512 kB\n")
        self.assertEqual(result, {"total_bytes": 1048576, "available_bytes": 524288})

    def test_block_storage_parsing_omits_unique_ids(self) -> None:
        raw = {"blockdevices": [{"name": "vd-synthetic", "type": "disk", "size": "4096", "fstype": None, "mountpoints": ["/srv/kalvin-backups"], "rota": 0, "tran": "virtio", "serial": "SYNTHETIC-SERIAL", "wwn": "SYNTHETIC-WWN"}]}
        rendered = json.dumps(parse_lsblk(json.dumps(raw)), sort_keys=True)
        self.assertNotIn("serial", rendered.lower())
        self.assertNotIn("wwn", rendered.lower())
        self.assertIn("KALVIN_BACKUP_NAMESPACE", rendered)

    def test_mount_parsing_omits_source_and_options(self) -> None:
        private_source = "//" + "synthetic-private-endpoint/share"
        options = "rw," + "username=synthetic-user,password=synthetic-value"
        raw = {"filesystems": [{"target": "/mnt/synthetic-private", "source": private_source, "fstype": "cifs", "options": options}]}
        rendered = json.dumps(parse_findmnt(json.dumps(raw)), sort_keys=True)
        self.assertNotIn("synthetic-private-endpoint", rendered)
        self.assertNotIn("username", rendered)
        self.assertNotIn("password", rendered)

    def test_network_link_parsing_omits_addresses_and_mac(self) -> None:
        private_address = "192." + "168.50.10"
        mac = "aa:bb:" + "cc:dd:ee:ff"
        raw = [{"ifname": "synthetic0", "flags": ["UP"], "operstate": "UP", "addr_info": [{"local": private_address}], "address": mac}]
        rendered = json.dumps(parse_ip_links(json.dumps(raw)), sort_keys=True)
        self.assertNotIn(private_address, rendered)
        self.assertNotIn(mac, rendered)

    def test_default_route_parsing_omits_gateway(self) -> None:
        private_gateway = "10." + "20.30.1"
        rendered = json.dumps(parse_default_route(json.dumps([{"dst": "default", "gateway": private_gateway, "dev": "synthetic0"}])), sort_keys=True)
        self.assertNotIn(private_gateway, rendered)
        self.assertEqual(json.loads(rendered)["interfaces"], ["synthetic0"])

    def test_malformed_probe_output_is_rejected(self) -> None:
        with self.assertRaises(HostParseError):
            parse_lsblk("not-json")


class InspectorTests(unittest.TestCase):
    def inspect(self, overrides: dict[ProbeId, ProbeResult] | None = None, os_status: str = "OBSERVED") -> dict:
        return HostInspector(
            runner=SyntheticRunner(overrides),
            sources=SyntheticSources(os_status),
            facts=FACTS,
            executables=EXECUTABLES,
        ).inspect()

    def test_synthetic_observed_host_matches_schema(self) -> None:
        schema = json.loads((ROOT / "schemas/observed-host.schema.json").read_text())
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(self.inspect())), [])

    def test_systemd_availability_and_service_state(self) -> None:
        observed = self.inspect()
        self.assertTrue(observed["systemd"]["available"])
        self.assertEqual(observed["services"]["docker"]["state"], "ACTIVE")
        self.assertEqual(observed["services"]["tailscale"]["state"], "INACTIVE")

    def test_executable_capabilities_are_injected_and_bounded(self) -> None:
        observed = self.inspect()
        self.assertEqual(set(observed["executables"]), set(EXECUTABLES))
        self.assertTrue(observed["executables"]["git"]["present"])

    def test_docker_capabilities_do_not_probe_daemon_details(self) -> None:
        docker = self.inspect()["docker"]
        self.assertEqual(docker["daemon_details"], "NOT_PROBED")
        self.assertTrue(docker["cli"]["present"])
        self.assertFalse(docker["socket"]["readable"])

    def test_permission_denied_is_distinct(self) -> None:
        result = self.inspect({ProbeId.LSBLK: ProbeResult(ProbeId.LSBLK, ProbeStatus.PERMISSION_DENIED)})
        self.assertEqual(result["block_storage"]["status"], "INSUFFICIENT_PERMISSION")

    def test_command_missing_is_unavailable(self) -> None:
        result = self.inspect({ProbeId.FINDMNT: ProbeResult(ProbeId.FINDMNT, ProbeStatus.COMMAND_MISSING)})
        self.assertEqual(result["filesystems"]["status"], "UNAVAILABLE")

    def test_timeout_is_unknown(self) -> None:
        result = self.inspect({ProbeId.IP_LINK: ProbeResult(ProbeId.IP_LINK, ProbeStatus.TIMEOUT)})
        self.assertEqual(result["network"]["status"], "UNKNOWN")

    def test_malformed_output_is_unknown_without_traceback(self) -> None:
        result = self.inspect({ProbeId.LSBLK: ProbeResult(ProbeId.LSBLK, ProbeStatus.SUCCESS, "malformed")})
        self.assertEqual(result["block_storage"]["status"], "UNKNOWN")

    def test_unavailable_os_is_not_false(self) -> None:
        result = self.inspect(os_status="UNAVAILABLE")
        self.assertEqual(result["operating_system"]["status"], "UNAVAILABLE")
        self.assertIsNone(result["operating_system"]["family"])


if __name__ == "__main__":
    unittest.main()
