# Platform Overview

Status: **CURRENT charter and declarative contracts; TARGET runtime; no operational implementation.**

## Charter

Kalvin is the infrastructure and orchestration repository for a platform composed of separately maintained applications and host roles. It defines how a supported environment can be described, reconstructed, checked, backed up, restored, and migrated. It does not become the implementation authority for the applications it deploys.

The platform is intended to own:

- host prerequisites and bootstrap contracts;
- declarative deployment profiles;
- application and infrastructure service wiring;
- model-hosting infrastructure without binding applications to one provider;
- external configuration and secret delivery contracts;
- network and service-exposure policy;
- persistent-state placement and service identities;
- backup, restore, and derived-state reconciliation coordination;
- monitoring and health integration;
- host-role and host-migration procedures;
- compatibility transitions with evidence and retirement gates;
- optional, separately reviewed privileged host helpers.

It explicitly does not own:

- Kal or Beepy source, tests, schemas, or business behavior;
- application authorization or application migrations;
- production data, secrets, caches, model blobs, database dumps, or container volumes in Git;
- a general shell or host-control API for assistant agents;
- a disk image or legacy absolute-path reconstruction method.

## Architecture state language

Kalvin documentation uses these labels:

- **CURRENT** — present and directly inspectable in the repository or validated environment;
- **TARGET** — intended architecture accepted as a design boundary;
- **HISTORICAL** — provenance that must not be read as current instructions;
- **PLANNED** — future work without an implementation or validation claim.

An implementation document must identify both the implemented revision and its validation evidence. A target statement alone is not an operational guarantee.

## Platform invariants

1. Kalvin, Kal, and Beepy remain separate repositories with independently pinned revisions.
2. A host profile is explicitly selected; hostnames, addresses, or existing services do not infer a role.
3. Each runtime service has a separate identity and writable-state boundary.
4. Secrets remain outside Git and are made visible only to their intended consumer.
5. Application authorization remains active even on a trusted or local network.
6. Git describes reconstruction and policy; it is not the backup destination for runtime state.
7. Authoritative data is restored before derived indexes and caches are reconciled.
8. Compatibility behavior is explicit, testable, and temporary—not a silent production fallback.
9. A privileged host helper, if later justified, is fixed-purpose, allowlisted, auditable, and unavailable to ordinary Kal agents/tools.
10. A service being reachable or healthy does not prove its data, authorization, backup, or migration boundaries are correct.

## Platform security principles

### Least privilege and identity separation

Human operators, application services, model-hosting services, backup operators, monitoring components, and optional host-management systems use separate identities. Application processes do not receive Docker, systemd, firewall, backup-administration, RMM, or unrestricted host privileges.

### Secret boundaries

Git contains schemas, names, placeholders, and injection requirements only. Secret values, credential files, decryption material, private keys, and recovery credentials are provisioned out of band. Health and diagnostic output must not reveal them.

### Data-domain boundaries

Infrastructure isolation reinforces but does not replace Kal's retrieval authorization or Beepy's business authorization. Kalvin must not simplify deployment by mounting all application data into a shared writable directory.

### Exposure boundaries

Profiles will state which services may be exposed and through which class of interface. Local or private-network reachability is not authorization. Administrative, model, vector, monitoring, and host-control endpoints remain private unless a later reviewed profile states a narrower exception.

### Compatibility boundaries

Legacy aliases are accepted only when a current consumer is documented. Conflicts fail closed. Every alias has an owner, warning behavior, test coverage, retirement condition, and rollback procedure. Production must not silently choose a legacy path or identity because canonical configuration is missing.

## Optional extensions

The following are outside the platform core unless a later phase defines a narrow adapter:

- Datto or another RMM system is an external management plane. Its credentials and privileges never grant capabilities to Kal agents/tools.
- Tailscale is an optional transport/exposure mechanism, not an identity or authorization bypass.
- Temporary public testing or Funnel-style exposure is a default-off lab extension requiring its own risk gate and approved application authentication.
- Desktop or Waybar controls are external clients of a narrow authenticated interface, not direct consumers of host-control sockets.
- Monitoring exporters are optional components with bounded, non-sensitive output.

No extension is implemented in this bootstrap.

## Deployment philosophy

Future deployment work should pin application and dependency revisions, render host-local configuration from public templates and external values, apply one service change at a time, preserve rollback sources, and validate data and authorization boundaries in addition to liveness.

Phase 4C represents that philosophy as non-operational JSON catalogs, profiles, and schemas. The architecture is layered as:

1. shared vocabularies and a component catalog;
2. one explicit host-role profile;
3. a desired deployment with human-friendly refs;
4. immutable repository/component resolution plus host-local configuration and external secret references;
5. a resolved deployment record describing what actually ran and which gates passed.

Validation rejects unknown vocabulary, undeclared components, unresolved revisions, forbidden exposure, and incomplete readiness. Phase 4D may implement against these interfaces after human review; Phase 4C performs no host mutation.
