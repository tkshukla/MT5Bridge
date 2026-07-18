#!/usr/bin/env bash
# Verifies the MT5Bridge stack is healthy. Pass --disk to also report disk usage.
set -euo pipefail

FAILED=0

check() {
  local description="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "[OK]   ${description}"
  else
    echo "[FAIL] ${description}"
    FAILED=1
  fi
}

echo "== MT5Bridge healthcheck =="

check "docker is running" systemctl is-active --quiet docker
check "postgres container healthy" bash -c "docker compose ps postgres --format json | grep -q '\"Health\":\"healthy\"'"
check "redis container healthy" bash -c "docker compose ps redis --format json | grep -q '\"Health\":\"healthy\"'"

if curl -fsS http://127.0.0.1:8000/api/v1/health | grep -q '"status":"ok"'; then
  echo "[OK]   backend /health reports ok"
else
  echo "[FAIL] backend /health did not report ok"
  FAILED=1
fi

check "nginx active" systemctl is-active --quiet nginx

if [[ "${1:-}" == "--disk" ]]; then
  echo "== Disk usage =="
  df -h / /var/lib/docker 2>/dev/null || df -h /
fi

if [[ "${FAILED}" -eq 0 ]]; then
  echo "== All checks passed =="
else
  echo "== One or more checks FAILED — see above =="
  exit 1
fi
