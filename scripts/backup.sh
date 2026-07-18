#!/usr/bin/env bash
# Nightly Postgres backup. Invoked by mt5bridge-backup.timer. See docs/DISASTER_RECOVERY.md.
set -euo pipefail

BACKUP_DIR="/var/backups/mt5bridge/postgres"
RETENTION_DAYS=14
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
ARCHIVE="${BACKUP_DIR}/mt5bridge-${TIMESTAMP}.dump"

mkdir -p "${BACKUP_DIR}"

echo "==> Dumping database to ${ARCHIVE}"
docker compose exec -T postgres pg_dump -U "${POSTGRES_USER:-mt5bridge}" -F c "${POSTGRES_DB:-mt5bridge}" \
  > "${ARCHIVE}"

echo "==> Pruning backups older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}" -name 'mt5bridge-*.dump' -mtime "+${RETENTION_DAYS}" -delete

if [[ -n "${BACKUP_REMOTE:-}" ]]; then
  echo "==> Syncing backups to ${BACKUP_REMOTE}"
  rsync -az "${BACKUP_DIR}/" "${BACKUP_REMOTE}/"
else
  echo "==> BACKUP_REMOTE not set — skipping off-box sync (backups stay local only)"
fi

echo "==> Backup complete: ${ARCHIVE}"
