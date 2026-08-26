# Deployment Profiles

Status: **TARGET role contract; profile schemas and service definitions are PLANNED.**

## Profile purpose

A profile will declare which capabilities are required, optional, or forbidden on a host; which state and backup responsibilities the host accepts; which exposure policy applies; and which readiness gates must pass. It will not contain credentials, private machine identifiers, or application source.

Profiles remain composable through explicit overlays. They do not silently merge because services happen to be installed on a host.

## Capability matrix

| Capability | `lab` | `core` | `storage` |
| --- | --- | --- | --- |
| Platform profile validation | Required | Required | Required |
| Kal | Optional, when selected for a test | Required for the assistant deployment | Forbidden by default |
| Beepy | Optional, when selected for a test | Required when business service is selected | Forbidden by default |
| Model hosting | Optional | Selected according to application requirements; may be remote by explicit design | Forbidden by default |
| Health integration | Required for selected components | Required | Required |
| Monitoring dashboard | Optional | Optional; cannot be the only external observer | Optional, preferred when resilience requirements support it |
| Backup client | Optional/test-only | Required; sends authoritative backups outward | Optional for Storage's own control state |
| Master backup repository and retention | Disposable test target only | Forbidden as the master role | Required |
| NAS/storage exports | Optional fixture | Consumer only | Selected storage responsibility |
| Temporary public testing | Default off; separate sanitized test gate | Default off and not a production default | Forbidden |
| Private transport extension | Optional | Optional | Optional |
| External RMM | Optional and separately privileged | Optional and separately privileged | Optional and separately privileged |

## `lab`

`lab` supports experimentation, compatibility testing, and selected platform/application components. Its state should be synthetic, resettable, or separately approved. Compatibility aliases may be enabled only by explicit test configuration and must not become production defaults because the current lab happens to use them.

A successful lab test proves only the conditions recorded by that test. It does not establish production data handling, authorization, backup, performance, or recovery readiness.

## `core`

`core` is the future primary application and compute role. It hosts the selected Kalvin platform services, pinned Kal and Beepy deployments, application dependencies, and model/runtime compute as appropriate. It sends authoritative backup sets to a separate destination.

`core` does not automatically own:

- the authoritative backup repository;
- application schemas or migrations;
- business or retrieval authorization;
- optional monitoring dashboards, public exposure, desktop controls, or RMM privileges.

Production readiness is defined in [Portability and Readiness](portability-and-readiness.md).

## `storage`

`storage` is the backup, NAS, retention, and recovery-source role. The legacy T420 is an intended future candidate for this role after a separately validated transition. Storage receives application-consistent backup sets, verifies them, applies retention, and protects additional copies.

It does not run Kal, Beepy, general model compute, or live application databases by default. Capacity and existing files do not authorize application compute or turn mounted backups into live state.

## Composition rules

1. Select one primary role for a host.
2. Add an optional capability only through an explicit, reviewed overlay.
3. Treat absence from the selected profile as not deployed.
4. Reject forbidden combinations before any mutation.
5. Preserve per-service data and identity boundaries even on one host.
6. Record exposure, backup, and readiness policy alongside service selection.
7. Keep profile semantics independent of whether later implementation uses Compose, native services, or another mechanism.

No profile file or orchestrator is implemented in Phase 4B.
