# Repository and Version Pinning

Status: **CURRENT pinning contract; no repository acquisition tooling.**

## Required representation

Kalvin, Kal, and Beepy remain independent repositories. A desired deployment names each logical repository and a human-readable desired ref. Resolution binds that ref to a full immutable commit before any host change:

```text
repository ID + desired ref + verified full commit + source/mirror identity
```

The ref communicates intent; the commit provides reproducibility. A tag or branch name alone is insufficient. No submodule or vendored source is used.

## Profile policy

- `lab` may request a development branch or experimental ref, but the deployment record still captures the exact resolved commit.
- `core` requires a reviewed release identifier or reviewed stable ref plus a full immutable commit. A development application ref is a validation error in production mode.
- `storage` follows the same immutable rule for Kalvin and selected infrastructure implementations; it does not acquire Kal or Beepy because those components are forbidden.

This phase invents no release tags. A future release process may add signed/reviewed tags, while commit verification remains mandatory.

## Mirror independence

The public catalog uses logical repository IDs and an operator-configured source policy rather than embedding credentials or assuming one remote. Host-local configuration maps a logical repository ID to an approved public origin, internal mirror, or offline object source. Correctness depends on verifying the resolved object identity and review policy, not on the transport URL.

## Desired manifest and lock evidence

A desired manifest belongs with reviewed deployment intent when it contains only public-safe logical values. A future resolution lock binds that intent to immutable commits and component versions. The final resolved deployment record belongs under platform state, conceptually `/var/lib/kalvin/platform/deployments/`, because it describes a host observation and may include non-secret operational metadata.

Records may include profile, Kalvin/Kal/Beepy commits, non-Git implementation versions, configuration revision, application-exposed migration identifiers, host role, readiness results, and timestamp. They must never include credentials, secret values, database content, or private endpoint details.
