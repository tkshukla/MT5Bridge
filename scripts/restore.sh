#!/usr/bin/env bash
# Restores a Postgres backup produced by scripts/backup.sh. See docs/DISASTER_RECOVERY.md.
#
# Usage: scripts/restore.sh <backup_file.dump> [--force]
set -euo pipefail

BACKUP_FILE="${1:?Usage: scripts/restore.sh <backup_file.dump> [--force]}"
FORCE="${2:-}"

if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "Backup file not found: ${BACKUP_FILE}" >&2
  exit 1
fi

if [[ "${FORCE}" != "--force" ]]; then
  read -r -p "This will DROP and recreate the ${POSTGRES_DB:-mt5bridge} database. Continue? [y/N] " confirm
  if [[ "${confirm}" != "y" && "${confirm}" != "Y" ]]; then
    echo "Aborted."
    exit 1
  fi
fi

echo "==> Stopping mt5bridge stack"
systemctl stop mt5bridge.service

echo "==> Starting postgres only for restore"
docker compose up -d postgres
sleep 5

echo "==> Dropping and recreating database"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-mt5bridge}" -d postgres \
  -c "DROP DATABASE IF EXISTS ${POSTGRES_DB:-mt5bridge};"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-mt5bridge}" -d postgres \
  -c "CREATE DATABASE ${POSTGRES_DB:-mt5bridge} OWNER ${POSTGRES_USER:-mt5bridge};"

echo "==> Restoring from ${BACKUP_FILE}"
docker compose exec -T postgres pg_restore -U "${POSTGRES_USER:-mt5bridge}" -d "${POSTGRES_DB:-mt5bridge}" \
  < "${BACKUP_FILE}"

echo "==> Restarting full stack"
systemctl start mt5bridge.service

echo "==> Verifying"
bash "$(dirname "${BASH_SOURCE[0]}")/healthcheck.sh"

echo "==> Restore complete"
