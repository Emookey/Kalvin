# Deployment Profiles

Status: **CURRENT declarative role contracts; no runtime implementation.**

## Profile purpose

A profile declares which components are required, optional, or forbidden on a host; which state and backup responsibilities the host accepts; which exposure ceiling applies; and which readiness gates must pass. It contains no credentials, private machine identifiers, application source, or execution procedures.

Exactly three initial profiles exist: `lab`, `core`, and `storage`. A host selects exactly one primary profile. Future overlays may refine optional choices but must not weaken a base profile's forbidden components, exposure ceiling, production pinning rule, or readiness gates without a separately reviewed contract change. Profiles do not silently merge because services happen to be installed.

## Capability matrix

| Capability | `lab` | `core` | `storage` |
| --- | --- | --- | --- |
| Platform profile validation | Required | Required | Required |
| Kal | Optional, when selected for a test | Required for the assistant deployment | Forbidden by default |
| Beepy | Optional, when selected for a test | Required when business service is selected | Forbidden by default |
| Model-runtime interface | Optional | Required interface; implementation may be local or remote by explicit design | Forbidden |
| Health integration | Required for selected components | Required | Required |
| Monitoring | Required contract for selected services | Required | Required |
| Backup client | Optional/test-only | Required; sends authoritative backups outward | Optional for Storage's own control state |
| Master backup repository and retention | Disposable test target only | Forbidden as the master role | Required |
| NAS/storage exports | Optional fixture | Consumer only | Selected storage responsibility |
| Temporary public testing | Optional and default off; separate sanitized test gate | Forbidden in the initial profile | Forbidden |
| Private transport extension | Optional | Optional | Optional |
| External RMM | Outside the component catalog | Outside the component catalog | Outside the component catalog |

## `lab`

`lab` supports experimentation, compatibility testing, and selected platform/application components. Kal, Beepy, a model runtime, backup-client exercises, a network overlay, legacy Open WebUI compatibility, and temporary public testing are optional selections. Monitoring is required so selected services have bounded health/readiness evidence. State should be synthetic, resettable, or separately approved. Compatibility aliases may be enabled only by explicit test configuration and must not become production defaults because the current lab happens to use them.

A successful lab test proves only the conditions recorded by that test. It does not establish production data handling, authorization, backup, performance, or recovery readiness.

## `core`

`core` is the future primary application and compute role. It requires pinned Kal and Beepy deployments, the replaceable model-runtime interface, monitoring, and an outbound backup client. It may select a network overlay and the explicitly legacy Open WebUI compatibility component. It sends application-consistent authoritative backup sets to a separate Storage role.

`core` does not automatically own:

- the authoritative backup repository;
- application schemas or migrations;
- business or retrieval authorization;
- optional monitoring dashboards, public exposure, desktop controls, or RMM privileges.

Production readiness is defined in [Portability and Readiness](portability-and-readiness.md).

## `storage`

`storage` is the backup, NAS, retention, and recovery-source role. The legacy T420 is an intended future candidate for this role after a separately validated transition. Storage requires a backup-repository target and monitoring; a network overlay and a backup client for Storage's own state remain optional. Storage receives application-consistent backup sets, verifies them, applies retention, and protects additional copies.

It does not run Kal, Beepy, general model compute, or live application databases by default. Capacity and existing files do not authorize application compute or turn mounted backups into live state.

## Composition rules

1. Select one primary role for a host.
2. Enable an optional component only through an explicit, validated desired deployment.
3. Treat absence from the selected profile as not deployed.
4. Reject forbidden combinations before any mutation.
5. Preserve per-service data and identity boundaries even on one host.
6. Record exposure, backup, and readiness policy alongside service selection.
7. Treat a profile exposure class as a maximum, never an instruction to expose.
8. Keep profile semantics independent of whether later implementation uses Compose, native services, or another mechanism.

The reference files under `deploy/profiles/` are machine-readable architecture contracts. They are not accepted by an orchestrator and contain no commands. Their shared vocabulary and component IDs come from `manifests/`, and their shape is defined under `schemas/`.
