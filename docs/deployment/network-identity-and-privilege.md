# Network, Identity, and Privilege

Status: **CURRENT policy vocabulary; no network or identity implementation.**

## Exposure classes

Exposure classes are ordered by increasing reach:

1. `PROCESS_LOCAL` — process namespace or loopback only;
2. `HOST_INTERNAL` — same-host consumers through a bounded interface;
3. `PLATFORM_INTERNAL` — explicitly joined Kalvin service network;
4. `LAN` — approved local-network listeners;
5. `OVERLAY` — approved private overlay participants;
6. `PUBLIC` — intentionally internet-reachable endpoint.

Every component declares a default and allowed set; every profile declares a ceiling. The effective setting must be both component-allowed and profile-allowed. Absence means least exposure, not “listen everywhere.” Local, LAN, or overlay reachability never substitutes for application authentication/authorization.

Temporary public testing is an explicit, default-off, lab-only component. A later implementation requires separate risk approval, application authentication, readiness, and retirement evidence. The network-overlay component is an optional transport; it does not grant identity or authorization. No firewall, proxy, Funnel, or Tailscale configuration exists here.

## Identity boundaries

Human operator, Kal service, Beepy service, Beepy-to-Kal scoped client, model runtime, backup client, backup repository, monitoring, platform administration, and future RMM identities are distinct. Sharing one host or deployment system does not collapse them.

Beepy's technical relationship remains:

```text
Beepy -> scoped service identity -> approved shared technical knowledge in Kal
```

Kalvin may provision the endpoint/credential boundary but cannot broaden the application-owned scope or expose business data to Kal.

## Privilege classes

- `UNPRIVILEGED_APPLICATION` — no general host-control authority; application-owned paths only.
- `LIMITED_PLATFORM_SERVICE` — narrowly bounded infrastructure capability such as backup transfer or monitoring collection.
- `HOST_ADMINISTRATIVE` — explicit, reviewed host mutation authority unavailable to ordinary services.
- `EXTERNAL_HOST_MANAGEMENT` — separate RMM/management-plane authority with its own credentials and audit.

A component being deployed by Kalvin does not receive Kalvin administrative privilege. Kal agents/tools never automatically inherit `HOST_ADMINISTRATIVE`, backup-administration, or `EXTERNAL_HOST_MANAGEMENT` authority. Future privileged helpers must be fixed-purpose, allowlisted, separately authenticated, and auditable.
