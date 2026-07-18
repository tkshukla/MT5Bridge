#!/usr/bin/env bash
# Provisions the MT5Bridge stack: docker compose up, systemd units, Nginx + Certbot,
# and runs a final healthcheck. Idempotent — safe to re-run.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./scripts/setup.sh" >&2
  exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_DIR="/opt/mt5bridge"
ENV_FILE="/etc/mt5bridge/mt5bridge.env"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Run: cp .env.example .env, edit it, then:" >&2
  echo "  mkdir -p /etc/mt5bridge && mv .env ${ENV_FILE} && chmod 600 ${ENV_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

echo "==> Linking repo into ${INSTALL_DIR}"
mkdir -p "${INSTALL_DIR}"
if [[ "${REPO_DIR}" != "${INSTALL_DIR}" ]]; then
  rsync -a --delete --exclude '.git' "${REPO_DIR}/" "${INSTALL_DIR}/"
fi

echo "==> Ensuring Prometheus metrics token exists"
if [[ ! -f "${INSTALL_DIR}/monitoring/metrics_token" ]]; then
  python3 -m venv /tmp/mt5bridge-venv
  /tmp/mt5bridge-venv/bin/pip install -q -r "${INSTALL_DIR}/backend/requirements.txt"
  (cd "${INSTALL_DIR}/backend" && /tmp/mt5bridge-venv/bin/python ../scripts/mint_metrics_token.py)
fi

echo "==> Starting docker compose stack"
cd "${INSTALL_DIR}"
docker compose --env-file "${ENV_FILE}" up -d --build

echo "==> Installing systemd units"
cp systemd/*.service systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mt5bridge.service
systemctl enable --now mt5bridge-backup.timer
systemctl enable --now mt5bridge-retention.timer

echo "==> Installing Nginx site config"
DOMAIN_VALUE="${DOMAIN:-_}"
sed "s/server_name _;/server_name ${DOMAIN_VALUE};/" nginx/mt5bridge.conf > /etc/nginx/sites-available/mt5bridge.conf
if [[ -n "${MT5_STATIC_IP:-}" ]]; then
  sed -i "s|# ${MT5_STATIC_IP} 1;|${MT5_STATIC_IP} 1;|; s|# 203.0.113.10 1;|${MT5_STATIC_IP} 1;|" \
    /etc/nginx/sites-available/mt5bridge.conf || true
fi
ln -sf /etc/nginx/sites-available/mt5bridge.conf /etc/nginx/sites-enabled/mt5bridge.conf
nginx -t
systemctl reload nginx

if [[ -n "${DOMAIN:-}" ]]; then
  echo "==> Requesting/renewing Certbot certificate for ${DOMAIN}"
  certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos -m "${CERTBOT_EMAIL:-admin@${DOMAIN}}" || \
    echo "Certbot failed — check DNS for ${DOMAIN} points at this VM's static IP, then re-run scripts/setup.sh"
else
  echo "DOMAIN not set in ${ENV_FILE} — skipping Certbot, serving plain HTTP only"
fi

echo "==> Running healthcheck"
bash "${INSTALL_DIR}/scripts/healthcheck.sh"

echo "==> Setup complete"
