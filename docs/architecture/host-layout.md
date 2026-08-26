# Conceptual Host Layout

Status: **TARGET namespace model; no live directories have been created.**

## Repository layout is not host layout

This Git repository contains documentation today and may later contain declarative definitions and tooling. It must never be used as the writable home for application databases, secrets, caches, logs, uploads, or backups.

The paths below describe a future deployed host namespace. They are not instructions to modify a host during this phase, and an application may use a different internal container path while the host preserves the same ownership boundary.

## Reviewed namespace

```text
/opt/kalvin/
  platform/                 # administrator-owned Kalvin release
  apps/
    kal/                    # independent Kal release checkout
    beepy/                  # independent Beepy release checkout

/etc/kalvin/
  platform/                 # rendered non-secret platform configuration
  kal/                      # rendered Kal configuration
  beepy/                    # rendered Beepy configuration
  uptime-kuma/              # only when selected
  open-webui/               # only when selected
  secrets/
    platform/               # service-partitioned secret source, not Git
    kal/
    beepy/

/var/lib/kalvin/
  platform/                 # non-secret deployment metadata
  kal/                      # Kal-owned persistent state
  beepy/                    # Beepy-owned file state; database remains service-owned
  uptime-kuma/              # independently classified third-party state
  open-webui/               # optional, independently classified state

/var/cache/kalvin/
  kal/
    chromadb/               # Kal-derived vector state only
  beepy/                    # only explicitly rebuildable Beepy caches
  model-hosting/
    ollama/
    huggingface/

/run/kalvin/
  platform/
  kal/
  beepy/
  credentials/              # ephemeral credential views

/var/log/kalvin/
  platform/                 # only when file logs are justified
  kal/
  beepy/

/srv/kalvin-backups/
  sources/
    <source-id>/             # storage profile or explicit repository mount only
```

## Ownership rules

- Release trees under `/opt` are administrator-owned and read-only to runtime services.
- Kal, Beepy, monitoring, optional UI, model-hosting, and backup components use distinct unprivileged identities.
- No common writable application group may let one service alter another service's code or persistent state.
- A service receives only its own configuration and secret material; an entire secrets hierarchy is never mounted into an application.
- File logs are used only where journald or another selected logging interface is insufficient, and log directories remain service-separated.

## State and cache rules

- `/var/lib` contains persistent service-owned state and is classified before backup.
- `/var/cache` contains only state proven disposable or reproducible.
- Kal vector state is nested under Kal's cache namespace rather than a platform-wide Chroma directory.
- Model assets are caches only when pinned information and an accessible source can recreate them.
- Runtime services never write into Git checkouts under `/opt`.

## Backup repository rule

`/srv/kalvin-backups` exists only on a host or mounted filesystem explicitly assigned the backup-repository responsibility. The `core` role uses an outbound backup client and bounded staging where needed; it is not the master backup store. The `storage` role protects backup sets with verification, retention, snapshots as appropriate, and off-host replication.

RAID or a local snapshot improves availability but is not, by itself, a backup.

## Portability and compatibility

Host configuration uses logical service names and external values, not committed addresses. Old application paths may appear only in historical documentation or a documented one-way compatibility adapter with consumer evidence and a retirement gate. New installations use canonical namespaces by default.
