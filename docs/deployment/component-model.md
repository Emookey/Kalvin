# Component Model

Status: **CURRENT reference catalog; implementations are PLANNED.**

## Component contract

Every catalog entry declares:

- a stable canonical ID, owner, and purpose;
- allowed profiles and default requirement;
- immutable version-source policy;
- typed dependencies;
- default and permitted exposure classes;
- a coarse privilege class;
- classified state requirements and backup policy;
- health and readiness gates;
- canonical, optional, experimental, or legacy compatibility status.

Profile membership does not transfer ownership. Kal and Beepy own their code, database formats, migrations, authorization, and readiness interfaces. Kalvin selects versions, provisions boundaries, and later invokes owner-published lifecycle interfaces.

## Initial catalog

| ID | Owner | Role | Initial status |
| --- | --- | --- | --- |
| `kal` | Kal | General-purpose assistant application | Canonical |
| `beepy` | Beepy | Business/work intelligence application | Canonical |
| `model-runtime` | Kalvin interface / selected provider | Replaceable model execution capability | Canonical logical interface |
| `monitoring` | Kalvin | Bounded platform health/readiness integration | Canonical |
| `backup-client` | Kalvin | Outbound, application-consistent backup participation | Canonical |
| `storage-backup-target` | Kalvin Storage | Backup repository, verification, and retention boundary | Canonical Storage responsibility |
| `network-overlay` | External integration | Optional private transport | Optional |
| `legacy-open-webui-compatibility` | External compatibility | Legacy UI bridge, not a Kal authority | Legacy, default off |
| `public-test-exposure` | External integration | Temporary lab-only public test boundary | Experimental, default off |

Datto/RMM is not a normal component in this catalog. It is a future external host-management plane and cannot confer Kal agent or tool privileges. Desktop/Waybar controls remain external authenticated clients, and additional exporters remain optional integrations.

## Dependency semantics

- `STARTUP` means a prerequisite must be available before a dependent process is started.
- `HEALTH` means a dependency's self-health is required to claim the dependent is healthy.
- `READINESS` means the dependency must satisfy its intended-use gate before the dependent or profile is ready.
- `OPTIONAL_INTEGRATION` means degradation is reported but documented partial operation may continue.

Order alone does not satisfy a dependency. For example, Beepy's scoped Kal technical integration is optional to its local business modes: a Kal degradation is visible, while allowed local operation may continue. The application-owned contract still determines exact behavior.

## Model runtime

`model-runtime` is an interface, not a synonym for Ollama. A resolved deployment records the selected implementation and immutable version. Kal remains the owner of model abstraction and selection behavior; Kalvin supplies the declared endpoint/capability boundary and must not reimplement Kal's provider logic.
