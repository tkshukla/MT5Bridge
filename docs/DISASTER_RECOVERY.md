# Disaster Recovery

## Recovery point / time objectives

| Component  | RPO                          | RTO        |
|------------|-------------------------------|------------|
| Postgres   | ≤ 15 min (WAL + nightly base) | ≤ 30 min   |
| Redis      | 0 (cache only, rebuildable)    | ≤ 5 min    |
| Backend    | N/A (stateless containers)     | ≤ 10 min   |
| MT5 config | manual, user-owned             | N/A        |

## Backups

`scripts/backup.sh` (see also [systemd/mt5bridge-backup.timer](../systemd/mt5bridge-backup.timer)):

- `pg_dump` (custom format) of the `mt5bridge` database, nightly at 02:00 local, retained
  14 days in `/var/backups/mt5bridge/postgres/`.
- Postgres WAL archiving to `/var/backups/mt5bridge/wal/` for point-in-time recovery
  between nightly dumps.
- `.env` (secrets) is **not** included in backups — it is regenerated/restored from the
  secret manager, never from a backup archive, to avoid stale-secret rollbacks.
- Backups are additionally rsynced off-box (configure `BACKUP_REMOTE` in `.env`; the
  script no-ops the rsync step if unset, with a warning).

## Restore procedure

`scripts/restore.sh <backup_file>`:

1. Stops the `mt5bridge` systemd unit (`docker compose down`).
2. Drops and recreates the `mt5bridge` database (prompts for confirmation unless
   `--force` is passed).
3. Restores from the given `pg_dump` archive via `pg_restore`.
4. Replays WAL segments newer than the dump, if present, for point-in-time recovery.
5. Restarts the `mt5bridge` systemd unit (`docker compose up -d`) and runs
   `scripts/healthcheck.sh` to verify.

Redis requires no restore step — it is purely a cache and repopulates from Postgres +
a fresh Kotak Neo poll on next backend start.

## Full VM loss

1. Provision a new Ubuntu 24.04 VM, assign the same static IP (or update DNS/Nginx
   allowlist on the MT5 side if the IP changes).
2. Run `scripts/install.sh` then `scripts/setup.sh` (see
   [UBUNTU_SETUP.md](UBUNTU_SETUP.md)).
3. Restore `.env` from the secret manager (not from any backup archive).
4. Copy the latest backup archive onto the VM and run `scripts/restore.sh`.
5. `docker compose up -d` and verify `GET /health` plus the Grafana "API health"
   dashboard before reconnecting MT5.

## Kotak Neo session loss

The Kotak Neo TOTP session/token can expire or be revoked independent of any VM issue.
`kotak/auth.py` retries login with exponential backoff and raises a `kotak_auth_down`
Prometheus alert (see [monitoring](../monitoring/)) after 3 consecutive failures — this
does not require a restore, just re-entry of TOTP if it's a manual-seed rotation, or
waiting out a transient broker-side outage.

## Runbook cross-reference

Day-to-day operational procedures (not disaster scenarios) are in
[OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md).
