# API Reference

Base URL (production): `https://<vm-host>/api/v1`
Base URL (dev): `http://localhost:8000`

All endpoints except `/health` require `Authorization: Bearer <jwt>` or `X-API-Key:
<key>`. See [SECURITY.md](SECURITY.md) for roles.

## Health

### `GET /health`

No auth required. Returns liveness of the app and its dependencies.

```json
{
  "status": "ok",
  "kotak_feed": "connected",
  "db": "ok",
  "redis": "ok",
  "version": "0.1.0"
}
```

## Read endpoints (role: `viewer` or above)

| Method | Path                 | Description                                    |
|--------|----------------------|-------------------------------------------------|
| GET    | `/quotes/{symbol}`   | Latest tick for `symbol` (from Redis cache)     |
| GET    | `/positions`         | Current open positions from Kotak Neo           |
| GET    | `/holdings`          | Current holdings (delivery) from Kotak Neo       |
| GET    | `/margins`           | Available/used margin                            |
| GET    | `/portfolio`         | Aggregated portfolio value, day P&L, open P&L    |
| GET    | `/ohlc/{symbol}`     | OHLC candles; query params `timeframe`, `from`, `to` |
| GET    | `/symbols`           | Configured tradable symbols + MT5 mapping/lot size |

Example:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://vm-host/api/v1/ohlc/NIFTY?timeframe=5m&from=2026-07-18T03:45:00Z&to=2026-07-19T10:00:00Z"
```

## Manual order endpoints (role: `trader` or above)

These **require** `confirmation_token` — see
[SECURITY.md#no-automated-execution](SECURITY.md#no-automated-execution). Requests
without a valid, unexpired, unused token are rejected with `422`.

### `POST /manual-order`

```json
{
  "symbol": "NIFTY24JULFUT",
  "side": "BUY",
  "quantity": 50,
  "order_type": "LIMIT",
  "price": 24500.5,
  "product": "MIS",
  "confirmation_token": "b9e1...",
  "confirmed_at": "2026-07-19T10:15:03Z"
}
```

Response: `201` with the created `orders` row (including Kotak Neo order id), or `409`
with `reject_reason` if Kotak Neo rejected it.

### `POST /modify-order`

```json
{
  "order_id": "KN-88213",
  "quantity": 25,
  "price": 24510.0,
  "confirmation_token": "c71a...",
  "confirmed_at": "2026-07-19T10:16:40Z"
}
```

### `POST /close-position`

```json
{
  "symbol": "NIFTY24JULFUT",
  "product": "MIS",
  "confirmation_token": "d02f...",
  "confirmed_at": "2026-07-19T10:20:11Z"
}
```

Closes the entire position at market by default; pass `"quantity"` to partially close.

## WebSocket endpoints

| Path              | Auth                          | Payload                                   |
|-------------------|--------------------------------|--------------------------------------------|
| `/ws/ticks`        | `?token=<jwt>` in query string | `{"symbol": "...", "ltp": ..., "ts": ...}` per subscribed symbol, subscribe via first message `{"subscribe": ["NIFTY", ...]}` |
| `/ws/portfolio`     | `?token=<jwt>`                | Portfolio snapshot on change: positions/holdings/margins delta |
| `/ws/orders`        | `?token=<jwt>`                | Order lifecycle events: `placed`, `filled`, `rejected`, `modified`, `closed` |

## Error format

```json
{"error": "invalid_confirmation_token", "detail": "token expired or already used"}
```

Standard HTTP status codes: `400` validation, `401` auth, `403` role, `404` not found,
`409` conflict (e.g. broker rejection), `422` business-rule rejection (e.g. missing
confirmation token), `500` unexpected.
