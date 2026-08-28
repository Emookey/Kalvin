# Read-Only Host Inspection and Preflight

Status: **CURRENT Phase 4E executable; local observation only and no host mutation.**

## Purpose and scope

Phase 4E answers two bounded questions:

1. What relevant capabilities does the local machine expose safely to an unprivileged inspector?
2. Do those observations satisfy the currently declared host requirements for a resolved profile?

It does not inventory a remote host, scan a LAN, probe a service endpoint, contact a repository, inspect application/process data, or correct a finding. The first intentional live smoke test belongs to a human operator after candidate review. Ordinary automated tests inject synthetic sources and probe results.

## Commands

```text
python3 -m kalvin host inspect --format text
python3 -m kalvin host inspect --format json
python3 -m kalvin host preflight --profile core --lock LOCK.json --format text
python3 -m kalvin host preflight --profile storage --lock LOCK.json --format json
```

Both commands keep input and result in memory and emit stdout/stderr only. There is no output path, cache, inventory database, deployment record, apply, fix, repair, bootstrap, or service-control option.

## Fixed local sources

Standard-library observation is limited to:

- `/etc/os-release` for selected OS family/version fields;
- `/proc/cpuinfo` for processor class and aggregate package/core counts;
- `/proc/meminfo` for aggregate physical memory capacity;
- platform APIs for kernel release, architecture, logical CPU count, and the running Python version;
- existence/readability metadata for `/var/run/docker.sock`, without opening it;
- executable presence through a fixed trusted path `/usr/bin:/bin:/usr/sbin:/sbin`;
- whether `/run/systemd/system` exists as a service-manager capability signal.

No other `/etc` or `/proc` tree is traversed. Process command lines/environments, secret paths, databases, shell history, user/browser data, Docker contents, systemd environment/credentials, and private keys are excluded.

## Exact subprocess allowlist

Only `kalvin/probes.py` imports subprocess. An enum selects one complete immutable definition; users cannot supply an executable, argument, flag, or shell fragment.

```text
lsblk --json --bytes --output NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,ROTA,TRAN
findmnt --json --output TARGET,FSTYPE
ip -j link show
ip -j route show default
systemctl is-active docker.service
systemctl is-enabled docker.service
systemctl is-active tailscaled.service
systemctl is-enabled tailscaled.service
```

Commands run as absolute executables resolved through the fixed trusted path, with `shell=False`, stdin disconnected, a three-second timeout, C locale, a three-variable environment, and explicit parsers. Dedicated pipe readers drain command output while retaining at most the configured stdout or stderr limit plus one byte; an over-limit result is discarded as `OUTPUT_LIMIT_EXCEEDED`. Other failures become `UNAVAILABLE`, `INSUFFICIENT_PERMISSION`, or `UNKNOWN`; the runner never elevates or falls back to another command.

No Docker CLI/daemon command, Tailscale CLI command, package manager, network client, SSH client, service mutation, mount/storage utility, privilege escalation, or generic command runner exists.

## Privacy and sanitization

The observed model never emits hostname, IP address, MAC address, route gateway, DNS data, mount source, mount options, disk serial/WWN/UUID, Docker container data, or unique hardware identifiers. Interface names and non-unique kernel block-device names may be emitted as bounded capability identifiers. Arbitrary mount targets are classified as `OTHER`; canonical Kalvin namespaces use category labels.

Raw probe stdout/stderr is never rendered in the observed document. The public repository contains only an explicitly synthetic fixture. Production inventory is not persisted automatically and must not be committed.

## Observed-host model

`schemas/observed-host.schema.json` defines kind `KALVIN_OBSERVED_HOST`, version `1.0.0`. Categories cover operating system, CPU, memory, block storage, filesystems, systemd, relevant services, executable/runtime capabilities, conservative Docker capability, and sanitized network capability.

Observation status is one of:

- `OBSERVED` — the bounded source was available and parsed;
- `UNAVAILABLE` — capability/command/source is absent;
- `INSUFFICIENT_PERMISSION` — the current user cannot perform the bounded read;
- `UNSUPPORTED` — the source is not supported on this platform;
- `UNKNOWN` — timeout, malformed output, or indeterminate result.

`UNKNOWN` is never silently converted to false.

## Preflight model

The separation is:

```text
DESIRED profile
  -> RESOLVED Phase 4D plan
  + OBSERVED Phase 4E host snapshot
  -> PREFLIGHT comparison
  -> host SATISFIED / UNSATISFIED / UNKNOWN / NOT_APPLICABLE
```

Profile requirements live in `manifests/host-requirements.json`. Current evidence supports Ubuntu for Core/Storage, Python 3.11+, Git presence, and observable storage/mount inventory for Storage. Default-route capability is optional. CPU architecture support and CPU/RAM/storage capacity minimums remain `NOT_YET_SPECIFIED`; Phase 4E does not invent numbers.

An unavailable required capability is `UNSATISFIED` only when absence is positively observed, such as a missing required executable. Missing/permission-denied/indeterminate evidence is `UNKNOWN`. Optional failures are reported without blocking required host status.

## Host versus production readiness

A Core host can satisfy every host requirement and still be `BLOCKED_EXTERNAL_GATE`. Phase 4E copies, rather than recalculates, Phase 4D production readiness and preserves application/platform gates including `kal.rag-status-durable` as external/unverified. Host compatibility never bypasses application readiness.

Storage checks observation capability without requiring Kal, Beepy, model compute, application identities, or application repository locks.

## Future boundaries

Possible later work includes a dedicated low-privilege inspector account/process, controlled private inventory persistence, remote-host architecture, richer evidence-backed hardware policy, and a separately authorized deployment engine. None exists in Phase 4E, and each requires its own security and privacy review.
