# Repository Boundaries

Status: **CURRENT ownership contract; TARGET deployment relationship.**

## Responsibility matrix

| Concern | Kalvin | Kal | Beepy |
| --- | --- | --- | --- |
| Host prerequisites and role definitions | Owns | Declares application requirements | Declares application requirements |
| Deployment orchestration and service wiring | Owns | Publishes supported runtime interface | Publishes supported runtime interface |
| Assistant UI, behavior, sessions, Memory, Library | Must not implement | Owns | Must not implement |
| RAG and retrieval authorization | Provides infrastructure isolation only | Owns | Uses approved scoped contract; owns Beepy-local retrieval |
| Model abstraction and assistant model selection | Wires infrastructure without assuming one provider | Owns | Does not select Kal's model/provider through the scoped contract |
| Tickets, projects, email, and business records | Must not inspect or implement | Must not receive through the technical contract | Owns |
| Kal–Beepy technical contract | Provisions endpoint and credential boundary | Owns server routes, scopes, and authorization | Owns client and call-site discipline |
| Application schema/migrations/tests | Sequences documented commands and records gates | Owns | Owns |
| Secrets | Defines injection and isolation architecture | Defines required secret contract and use | Defines required secret contract and use |
| Backups and restores | Coordinates destinations, policy, verification, and ordering | Owns consistent Kal snapshot/restore behavior | Owns consistent Beepy snapshot/restore behavior |
| Monitoring and readiness | Defines integration/profile policy | Exposes safe application signals | Exposes safe application signals |
| Host migration | Owns orchestration and evidence format | Owns Kal data compatibility | Owns Beepy data compatibility |

## Kal boundary

Kal owns:

- assistant behavior and UI/application logic;
- sessions, Memory, and Library;
- RAG, retrieval, and application-level retrieval authorization;
- model abstraction and provider behavior;
- authentication and application authorization;
- the server side of the scoped Beepy service contract;
- application migrations, integrity checks, and tests;
- research and multimodal workflows;
- controlled agent and tool capabilities.

Kalvin can select, configure, start, stop, and observe a reviewed Kal release only through later approved platform implementation. It cannot import Kal modules, fork Kal routes, rewrite Kal schemas, or use infrastructure reachability as user authorization.

## Beepy boundary

Beepy owns:

- business records, tickets, projects, and email workflows;
- work-specific frontend and backend behavior;
- business integrations and authorization;
- Beepy database state and file-backed authoritative objects;
- migrations, integrity checks, and tests;
- the client side of the scoped Beepy-to-Kal contract.

Business evidence stays in Beepy. A technical request to Kal is limited to the payload allowed by the application-owned contract; Kalvin may wire the connection and secret but may not broaden its data or route scope.

## Cross-repository rules

1. Repositories are fetched independently and pinned by reviewed identifiers.
2. No application source is vendored, copied, or imported through a submodule.
3. A platform manifest identifies a release but does not change application ownership.
4. App-specific development Compose or packaging remains app-owned; future Kalvin production wiring must consume documented interfaces rather than internal source assumptions.
5. Application migrations are invoked through the owning repository and are never reimplemented as platform SQL or filesystem mutation.
6. Health probes return bounded operational status, not sessions, documents, business rows, indexed text, environment values, or secrets.
7. Rollback is version- and data-aware. Reverting platform code alone must not be presented as an application data rollback.

## GoodWill boundary

GoodWill is **HISTORICAL**. It remains a provenance source for previous host configuration, experiments, mock corpora, and migration evidence. It is not a parent repository, upstream source tree, or current operational manual for Kalvin.

Phase 4A assigned all legacy content to platform rewrite, application ownership, history, or retirement and approved no verbatim copying. This candidate therefore contains newly written boundary documents and no GoodWill source, mock data, scripts, Git objects, or commits.

## Host-role boundary

Host roles select infrastructure responsibilities; they do not reassign application ownership. `core` hosting Kal and Beepy does not make their state platform-owned. `storage` receiving backups does not make restored data a live application database. `lab` compatibility behavior does not become a production contract by observation alone.

## Extension boundary

RMM, private-network transport, temporary public testing, desktop controls, and monitoring exporters remain optional extensions. They must have separate identity, privilege, exposure, and retirement policy. In particular, no host-management integration may confer agent/tool authority on Kal.
