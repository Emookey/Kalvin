# Host Requirements and Drift Policy

Status: **CURRENT Phase 4F read-only policy and reporting; no remediation capability.**

## Purpose

Phase 4F answers which host capabilities each profile requires, why each rule exists, and how a sanitized Phase 4E observation differs from the approved policy. It emits requirements or a drift report to stdout/stderr. It does not persist inventory, change desired/resolved/observed state, or perform remediation.

```text
DESIRED / RESOLVED
  + VERSIONED HOST REQUIREMENTS
  + SANITIZED OBSERVED HOST
  -> DRIFT FINDINGS
  -> GUIDANCE ONLY
  -> NO ACTION
```

## Commands

Requirements display performs no host inspection:

```text
python3 -m kalvin host requirements --profile lab --format text
python3 -m kalvin host requirements --profile core --format json
python3 -m kalvin host requirements --profile storage --format text
```

Drift uses the existing local-only Phase 4E inspector. Running either command below intentionally observes the executing host; automated tests patch the inspector and never perform this live step.

```text
python3 -m kalvin host drift --profile core --lock LOCK.json --format text
python3 -m kalvin host drift --profile storage --lock LOCK.json --format json
```

There is no apply, fix, repair, install, configure, service-control, output-file, or remote-host command.

## Policy contract

`manifests/host-requirements.json` uses schema version `2.0.0` and policy version `1.0.2`. Requirement definitions live only there. Each records an ID, profile state, category, comparison/expected value, evidence class and source, rationale, lifecycle, decision state, component applicability, and one guidance-only remediation reference. Remediation definitions may provide profile-specific explanatory guidance without changing requirement semantics. A narrowly scoped profile override may keep an optional concrete comparison for one profile while leaving another profile's human decision genuinely unspecified.

Requirement states are:

- `REQUIRED` — an observed mismatch blocks host compliance;
- `OPTIONAL` — absence does not create host drift;
- `RECOMMENDED` — mismatch is warning drift, not a blocker;
- `NOT_APPLICABLE` — the profile/component set does not use the capability;
- `HUMAN_DECISION_REQUIRED` — policy is unapproved and evaluates as `DECISION_PENDING`, not host failure.

Evidence classes are `ARCHITECTURE_REQUIRED`, `IMPLEMENTATION_REQUIRED`, `APPLICATION_REQUIRED`, `RECOMMENDED`, and `HUMAN_DECISION_REQUIRED`. A rule does not become mandatory merely because it appears useful.

## Initial supported-host policy

The documented reconstruction contract supports Ubuntu Server as the initial production OS family. Core and Storage require observed family `ubuntu`; Lab recommends it. Exact releases remain a human decision because no compatibility matrix exists. This does not claim other distributions can never be supported.

x86_64 is the initial tested architecture. Core and Storage require it and Lab recommends it until another architecture has application/platform compatibility evidence. Python 3.11+ is required wherever Kalvin tooling runs. Git is required at bootstrap/version-management time on all profiles, not claimed as a steady-state application service dependency.

systemd is recommended for the current Ubuntu-oriented design while its long-term platform status remains open. Docker is optional in Lab with availability as the optional comparison. Core and Storage record Docker as decision-pending with no expected value because the decision is whether a container runtime is required at all; the repository has no operational container deployment implementation. Storage does not inherit a Docker requirement merely from Core's possible runtime selection.

## Profile differences

| State count | Lab | Core | Storage |
| --- | ---: | ---: | ---: |
| Required | 2 | 4 | 6 |
| Recommended | 3 | 4 | 1 |
| Optional | 4 | 0 | 1 |
| Human decision required | 5 | 6 | 5 |
| Not applicable | 1 | 1 | 2 |

Storage requires block and mount observability but not application compute. Observability does not prove capacity, disk health, topology, backup repository readiness, or retention readiness. Core local capacity remains separate from Storage retention authority.

## Numeric and model-compute policy

No CPU, memory, local storage, retention capacity, GPU, or VRAM minimum is enforced. Those findings are `DECISION_PENDING`. Core sizing must derive from selected applications and staging needs. Storage capacity should derive from protected working sets, retention, replication, and safety margin. Model compute must derive from the selected provider/model without making the logical `model-runtime` synonymous with Ollama or one GPU.

See [Hardware Requirement Decisions](hardware-requirement-decisions.md) for the approval work that remains.

## Drift and severity

Comparison results are `SATISFIED`, `UNSATISFIED`, `UNKNOWN`, `NOT_APPLICABLE`, and `DECISION_PENDING`. An unavailable required observation is `UNKNOWN`; a positively observed required mismatch is `UNSATISFIED`.

Severity is `INFO`, `WARNING`, or `BLOCKING`. Unsatisfied required capabilities are blocking. Unknown required evidence and unsatisfied recommendations are warnings. Decision-pending and optional outcomes are informational. A decision pending is not disguised as a failed host.

Host compliance is `SATISFIED`, `UNSATISFIED`, or `UNKNOWN`. Drift status separately reports `DRIFT_FREE`, `DRIFT_DETECTED`, or `EVIDENCE_INCOMPLETE`. A host can be compliant and drift-free while production readiness remains blocked by external application/platform gates.

## Remediation boundary

Every remediation has an ID, plain-language guidance, and literal action `NONE`. Guidance is selected for the active profile where a declarative override exists and may append context only for components in the resolved set. A `NOT_APPLICABLE` result always explains that no remediation is required for the selected profile/component set. Human drift output labels satisfied/not-applicable policy context as `Guidance`, unresolved choices as `Decision guidance`, unavailable evidence as `Investigation guidance`, and only unsatisfied findings as `Suggested remediation`. Policy validation rejects shell-like executable guidance, including profile/component variants, and any action other than `NONE`. The report repeats `DRIFT REPORT ONLY — NO CHANGES PERFORMED`.

Guidance is not authorization. It does not install packages, change services, alter containers, mount storage, configure networking, resolve secrets, or modify a host. Controlled remediation is a future, separately authorized design.

## Exit behavior

- `0`: valid requirements display or drift with satisfied required host compliance;
- `2`: invalid profile, lock, manifest, or requirement policy;
- `3`: unexpected internal failure;
- `4`: blocking host drift (`UNSATISFIED`);
- `5`: required host compliance is `UNKNOWN` because evidence is unavailable.

Decision-pending requirements do not cause a failure exit by themselves.

## Host compliance is not production readiness

Host drift excludes application migrations, authorization, application health, secret/configuration provider resolution, backup evidence, and `kal.rag-status-durable`. Core retains those external gates and remains `BLOCKED_EXTERNAL_GATE` even with zero blocking host drift. Storage retains its own repository/retention/readiness gates and remains application-compute-free.

## Determinism and privacy

The same profile, policy, resolved plan, and synthetic observed host produce byte-identical JSON with stable finding order. Live reality may change between runs, but each report remains stably ordered. Output includes only sanitized observation values used by findings and never includes hostnames, addresses, MACs, gateways, mount sources/options, disk serials, secrets, or raw probe output.
