# Ubuntu 24.04 VM Setup

Target: a fresh Ubuntu 24.04 LTS VM with a static IP, reachable from the Windows 11
desktop running MT5.

## 1. Automated install

```bash
git clone https://github.com/tkshukla/MT5Bridge.git
cd MT5Bridge
sudo ./scripts/install.sh
```

`scripts/install.sh` installs, idempotently (safe to re-run):

- `python3.12`, `python3.12-venv`, `python3-pip`
- Docker Engine + Docker Compose plugin (official Docker apt repo, not the Ubuntu repo
  package, to get current Compose v2)
- `git`
- `nginx`
- `certbot` + `python3-certbot-nginx`
- `redis-tools` (client only — Redis server itself runs in Docker)
- `postgresql-client` (client only — Postgres server itself runs in Docker)
- `ufw` (firewall — see below)

It does **not** install Prometheus/Grafana on the host; those run as Docker services
(see `docker-compose.yml`) to keep the host minimal.

## 2. Configure

```bash
cp .env.example .env
$EDITOR .env
```

Required values — see `.env.example` for the full annotated list:

- `KOTAK_NEO_API_KEY`, `KOTAK_NEO_API_SECRET`, `KOTAK_NEO_TOTP_SECRET`,
  `KOTAK_NEO_CLIENT_ID` — from your Kotak Neo API developer console.
- `POSTGRES_PASSWORD`, `REDIS_PASSWORD` — generate with `openssl rand -hex 32`.
- `JWT_SECRET_KEY` — generate with `openssl rand -hex 32`.
- `MT5_STATIC_IP` — the Windows desktop's egress IP, for the Nginx allowlist.
- `DOMAIN` — the domain/subdomain pointed at this VM's static IP, for Certbot.

Move `.env` out of the repo checkout for production:

```bash
sudo mkdir -p /etc/mt5bridge
sudo mv .env /etc/mt5bridge/mt5bridge.env
sudo chmod 600 /etc/mt5bridge/mt5bridge.env
```

(The systemd units in `systemd/` reference this path via `EnvironmentFile=`.)

## 3. Provision services

```bash
sudo ./scripts/setup.sh
```

`scripts/setup.sh`:

1. Runs `docker compose up -d --build` (Postgres, Redis, backend, Prometheus, Grafana).
   The backend is a single FastAPI process; the Kotak Neo WebSocket feed consumer and
   the portfolio poller run as background asyncio tasks inside that same process (see
   `backend/app/main.py` lifespan) — there is no separate worker process to manage.
2. Applies `db/schema.sql` (idempotent — uses `CREATE TABLE IF NOT EXISTS`).
3. Installs the systemd units from `systemd/` and enables them: `mt5bridge.service`
   (wraps `docker compose up`/`down` for the whole stack, so the stack survives a VM
   reboot), `mt5bridge-backup.timer`, `mt5bridge-retention.timer`.
4. Installs `nginx/mt5bridge.conf`, requests a Certbot cert for `$DOMAIN`, reloads Nginx.
5. Configures `ufw`: allow 22 (SSH), 80/443 (Nginx), deny everything else inbound by
   default; Postgres/Redis ports are only bound to the Docker bridge network, not the
   host, so they need no firewall rule.
6. Runs `scripts/healthcheck.sh` and prints a pass/fail summary.

## 4. Verify

```bash
curl -k https://$DOMAIN/api/v1/health
```

Should return `{"status": "ok", ...}` (see [API.md](API.md#health)).

## 5. Point MT5 at the bridge

See [mql5/README.md](../mql5/README.md) — set `InpBridgeBaseUrl` and `InpAuthToken`
inputs on the `MT5BridgeDashboard` EA to `https://$DOMAIN/api/v1` and a JWT obtained via
your operator login flow.

## Manual step-by-step (if you don't want to run the scripts blind)

Every step above is a normal `apt install` / `docker compose` / `systemctl enable`
command — read `scripts/install.sh` and `scripts/setup.sh` directly, they're plain bash
with comments, not opaque. Running them is equivalent to typing the commands yourself.
