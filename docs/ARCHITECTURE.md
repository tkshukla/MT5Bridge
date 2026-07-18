# Architecture

## Component diagram

```
                              ┌─────────────────────────────────────────────┐
                              │              Kotak Neo                     │
                              │  REST Trade API   │   WebSocket Feed        │
                              └─────────┬──────────────────┬────────────────┘
                                        │ HTTPS            │ WSS
                                        ▼                  ▼
┌───────────────────────────────────────────────────────────────────────────┐
│  Ubuntu 24.04 VM                                                          │
│                                                                           │
│   ┌──────────────┐      ┌─────────────────────────────────────────────┐  │
│   │   Nginx      │◄────►│  FastAPI app (uvicorn workers)              │  │
│   │  TLS/Certbot │      │  - REST routers (health, quotes, positions, │  │
│   │  reverse     │      │    holdings, margins, portfolio, ohlc,      │  │
│   │  proxy       │      │    symbols, manual-order, modify-order,     │  │
│   └──────────────┘      │    close-position)                         │  │
│                          │  - WebSocket routers (/ws/ticks,           │  │
│                          │    /ws/portfolio, /ws/orders)              │  │
│                          │  - kotak/ client: REST wrapper, TOTP auth, │  │
│                          │    WebSocket feed consumer                 │  │
│                          │  - security: JWT + API key auth, audit log │  │
│                          └───────┬───────────────────┬────────────────┘  │
│                                  │                    │                   │
│                          ┌───────▼───────┐   ┌────────▼────────┐         │
│                          │  PostgreSQL   │   │      Redis      │         │
│                          │  (durable:    │   │  (hot cache +   │         │
│                          │  symbols,     │   │   pub/sub for   │         │
│                          │  ticks,       │   │   WS fan-out)   │         │
│                          │  candles,     │   └─────────────────┘         │
│                          │  positions,   │                               │
│                          │  holdings,    │   ┌─────────────────┐         │
│                          │  orders,      │   │   Prometheus    │         │
│                          │  portfolio_   │   │   + Grafana     │         │
│                          │  snapshots,   │   │   (metrics,     │         │
│                          │  audit_logs)  │   │   dashboards)   │         │
│                          └───────────────┘   └─────────────────┘         │
└───────────────────────────────────┬───────────────────────────────────────┘
                                     │ HTTPS + WSS (static IP, JWT/API key)
                                     ▼
                        ┌─────────────────────────────┐
                        │   MT5 Desktop (Windows 11)  │
                        │  BridgeClient.mqh (WinHTTP  │
                        │  + WebSocket via DLL calls) │
                        │  MT5BridgeDashboard.mq5:    │
                        │   - custom symbols/charts   │
                        │   - holdings/positions/P&L  │
                        │     panel                   │
                        │   - BUY/SELL/EXIT/CLOSE/    │
                        │     MODIFY buttons, each     │
                        │     gated by a confirm       │
                        │     dialog + order preview   │
                        └─────────────────────────────┘
```

## Data flow

### Market data (read path)

1. `kotak/websocket_feed.py` maintains a persistent WSS connection to Kotak Neo's tick
   feed, subscribing to symbols present in the `symbols` table.
2. Each tick is: (a) written to Redis (latest-tick cache, key `tick:{symbol}`), (b)
   appended to the `ticks` table, (c) published to the Redis channel `ticks:{symbol}`,
   which fans out to any `/ws/ticks` subscribers, and (d) folded into the in-progress
   OHLC candle for that symbol's configured timeframes.
3. `GET /quotes/{symbol}` reads the Redis hot cache (falls back to the latest DB row on
   a cache miss). `GET /ohlc/{symbol}` reads the `candles` table.

### Portfolio data (read path)

1. A background poller (`kotak/client.py`) refreshes positions/holdings/margins from
   Kotak Neo's REST API on a fixed interval (default 5s; configurable) and on-demand
   after any confirmed order action.
2. Each refresh is diffed against the last snapshot; changes are written to
   `positions`/`holdings`/`portfolio_snapshots` and published to `/ws/portfolio`.

### Manual order path (write path — see [SECURITY.md](SECURITY.md))

1. MT5 EA builds an order preview locally (symbol, side, qty, order type, price) and
   shows a confirmation dialog.
2. On user confirmation, the EA calls the relevant REST endpoint
   (`POST /manual-order`, `/modify-order`, or `/close-position`) with the preview
   payload plus a client-generated `confirmation_token` and `confirmed_at` timestamp.
3. The backend validates the token was generated within a short TTL (anti-replay),
   validates quantity/symbol against current holdings/lot rules, forwards the order to
   Kotak Neo's REST API, writes an `orders` row and an `audit_logs` row, and publishes
   the result to `/ws/orders`.
4. There is no code path that reaches step 2 without a human click in MT5 — the backend
   has no scheduler, no strategy engine, and no mechanism to originate an order itself.

## Why Redis *and* Postgres

Redis is a cache/fan-out layer only — nothing is durable there. Postgres is the source
of truth for everything (ticks, candles, positions, holdings, orders, audit). If Redis
is flushed or restarted, the system re-hydrates from Postgres + a fresh Kotak Neo poll;
no data is lost, only a brief cache-warm delay.

## Why Nginx in front of FastAPI

TLS termination (via Certbot-issued certs), request size/rate limiting, and a stable
place to add IP allowlisting for the MT5 desktop's static egress IP, independent of the
FastAPI app itself.
