#!/usr/bin/env bash
# Idempotent base package install for a fresh Ubuntu 24.04 VM. Safe to re-run.
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo ./scripts/install.sh" >&2
  exit 1
fi

echo "==> Updating apt package index"
apt-get update -y

echo "==> Installing base packages"
apt-get install -y --no-install-recommends \
  python3.12 python3.12-venv python3-pip \
  git curl ca-certificates gnupg lsb-release \
  nginx certbot python3-certbot-nginx \
  redis-tools postgresql-client \
  ufw

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker Engine (official Docker apt repo)"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  echo "==> Docker already installed, skipping"
fi

echo "==> Enabling docker service"
systemctl enable --now docker

echo "==> Configuring ufw (allow SSH, HTTP, HTTPS; deny everything else inbound)"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "==> Base install complete. Next: cp .env.example .env, edit it, then run scripts/setup.sh"
