#!/usr/bin/env bash
# Drops ticks/candles partitions and rows older than TICK_RETENTION_DAYS.
# Invoked daily by mt5bridge-retention.timer.
set -euo pipefail

RETENTION_DAYS="${TICK_RETENTION_DAYS:-90}"

echo "==> Deleting ticks older than ${RETENTION_DAYS} days"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-mt5bridge}" -d "${POSTGRES_DB:-mt5bridge}" \
  -c "DELETE FROM ticks WHERE ts < now() - INTERVAL '${RETENTION_DAYS} days';"

echo "==> Deleting candles older than ${RETENTION_DAYS} days"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-mt5bridge}" -d "${POSTGRES_DB:-mt5bridge}" \
  -c "DELETE FROM candles WHERE ts_open < now() - INTERVAL '${RETENTION_DAYS} days';"

echo "==> Reclaiming space (VACUUM)"
docker compose exec -T postgres psql -U "${POSTGRES_USER:-mt5bridge}" -d "${POSTGRES_DB:-mt5bridge}" \
  -c "VACUUM (ANALYZE) ticks, candles;"

echo "==> Retention pass complete"
