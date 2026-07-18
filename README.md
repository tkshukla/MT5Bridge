# MT5Bridge

MetaTrader 5 as a charting / analytics / portfolio dashboard for **Kotak Neo**, with
**manual-confirmation-only** order execution. MT5 never places an order on its own —
every trade is a deliberate, user-clicked, confirmed action.

> **Kotak Neo API disclaimer**: the Kotak Neo client in `backend/app/kotak/` is written
> against Kotak Securities' publicly documented Neo Trade API / TOTP login flow / WebSocket
> feed *as generally known*, not against a live-verified current spec. Endpoint paths,
> field names, and WS message shapes are marked `# UNVERIFIED` in code and **must be
> checked against your own Kotak Neo API credentials/docs in a sandbox before going live**.
> Do not point this at a funded account until you've done that verification pass.

## Why this exists

- MT5 is a best-in-class charting/dashboard shell. Kotak Neo is the broker with the actual
  account. This bridge streams Kotak Neo market data and portfolio state into MT5, and
  relays *manually-confirmed* order actions from MT5 back to Kotak Neo.
- Automated/algorithmic order placement is intentionally out of scope and disabled by
  default (see [Safety model](#safety-model)).

## Architecture

```
Kotak Neo REST + WebSocket
        │
        ▼
┌───────────────────────────────┐
│   Ubuntu 24.04 VM (Docker)    │
│                               │
│  FastAPI bridge service ──────┼──► PostgreSQL (symbols, ticks, candles,
│    - REST endpoints           │      positions, holdings, orders,
│    - /ws/ticks /ws/portfolio  │      portfolio_snapshots, audit_logs)
│    - /ws/orders               │
│    - Kotak Neo client (TOTP,  │──► Redis (hot cache, pub/sub for WS fan-out)
│      REST, WebSocket feed)    │
│  Nginx (TLS termination,      │
│    reverse proxy)             │
│  Prometheus + Grafana         │
└───────────────┬───────────────┘
                │  HTTPS + WebSocket
                ▼
      MT5 Desktop (Windows 11)
      - MQL5 connector library (BridgeClient.mqh)
      - Dashboard EA (quotes, positions, holdings, P&L)
      - Manual-only order panel: BUY / SELL / EXIT / CLOSE / MODIFY
        (each requires an explicit click + confirmation dialog)
```

Full diagram and component breakdown: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Safety model

This is a hard requirement, not a suggestion:

1. **No unattended trading.** The bridge has no concept of a "strategy" or "signal" —
   there is no code path from a price update to an order. See
   [docs/SECURITY.md](docs/SECURITY.md#no-automated-execution) for how this is enforced.
2. Every order-placing endpoint (`POST /manual-order`, `POST /modify-order`,
   `POST /close-position`) requires a `confirmation_token` that the MQL5 client only
   generates *after* the user clicks a confirmation dialog showing the order preview.
3. All order actions are audit-logged (`audit_logs` table) with the originating MT5
   client, user, and confirmation timestamp.
4. Read endpoints (quotes, positions, holdings, margins, portfolio) require no such
   token and can be polled/streamed freely.

## Repository layout

```
backend/            FastAPI bridge service (Python 3.12)
db/                  PostgreSQL schema
mql5/                MQL5 include library + dashboard Expert Advisor
nginx/               Reverse proxy config
systemd/             systemd unit files for the backend services
monitoring/          Prometheus + Grafana provisioning
scripts/             install/setup/backup/restore/healthcheck automation
docs/                Architecture, API, setup, security, DR, runbook docs
.github/workflows/   CI, Docker build, deploy pipelines
```

## Quick start (development)

```bash
cp .env.example .env        # fill in Kotak Neo credentials, DB/Redis passwords, JWT secret
docker compose up -d --build
curl http://localhost:8000/health
```

Then in MT5: copy `mql5/Include/MT5Bridge/*` into `MQL5/Include/MT5Bridge/` and
`mql5/Experts/MT5BridgeDashboard.mq5` into `MQL5/Experts/`, compile, and attach the EA
to a chart. See [docs/API.md](docs/API.md) for endpoint reference and
[mql5/README.md](mql5/README.md) for MT5-side setup.

## Production deployment (Ubuntu 24.04 VM)

See [docs/UBUNTU_SETUP.md](docs/UBUNTU_SETUP.md) — automated via `scripts/install.sh`
and `scripts/setup.sh`.

## Documentation index

- [Architecture](docs/ARCHITECTURE.md)
- [API reference](docs/API.md)
- [Ubuntu installation guide](docs/UBUNTU_SETUP.md)
- [Security](docs/SECURITY.md)
- [Disaster recovery](docs/DISASTER_RECOVERY.md)
- [Operations runbook](docs/OPERATIONS_RUNBOOK.md)

## License

MIT — see [LICENSE](LICENSE).
