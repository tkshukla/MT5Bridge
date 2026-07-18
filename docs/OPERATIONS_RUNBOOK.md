# Operations Runbook

## Daily checks

- Grafana "API health" dashboard: p50/p95 latency, error rate, uptime.
- Grafana "Tick rate" dashboard: ticks/sec per subscribed symbol — a flatline during
  market hours indicates a stalled Kotak Neo WS feed (see below).
- `GET /health` returns `{"status": "ok", "kotak_feed": "connected", "db": "ok",
  "redis": "ok"}` — any field other than the happy value needs investigation before it
  becomes a user-facing issue.

## Common incidents

### Kotak Neo WebSocket feed disconnected

Symptoms: tick-rate dashboard flatlines; `/health` shows `kotak_feed: "disconnected"`.

1. Check `docker compose logs backend | grep kotak_ws` for the disconnect reason.
2. The feed consumer auto-reconnects with backoff (`kotak/websocket_feed.py`); if it
   hasn't recovered in 2 minutes, restart the backend container (the feed loop and
   portfolio poller both run as background tasks inside it):
   `docker compose restart backend`.
3. If Kotak Neo itself is down, there's nothing to do but wait — check their status
   page/support channel. MT5 will show stale (last-known) quotes, clearly timestamped.

### JWT/API key auth failures spiking

1. Check `audit_logs` for the source IP/user of the failures.
2. If it's the MT5 desktop itself, its token likely expired — the EA should silently
   refresh; if not, restart the EA (`OnInit` re-authenticates).
3. If it's an unrecognized source, treat as a security event: rotate the affected API
   key/JWT signing secret and check Nginx access logs for the source IP, tighten the
   `allow`/`deny` allowlist in `nginx/mt5bridge.conf`.

### Order rejected by Kotak Neo

1. Check the `orders` table row's `reject_reason` column and the corresponding
   `audit_logs` entry.
2. Common causes: insufficient margin, market/segment closed, lot-size validation
   mismatch between MT5's custom symbol config and Kotak Neo's actual lot size — verify
   `symbols` table `lot_size` matches Kotak Neo's contract master.
3. This is always visible to the user in MT5 as a rejected-order dialog; there is no
   silent-failure path for order placement.

### Database disk pressure

1. `ticks` and `candles` grow continuously. Check
   `scripts/healthcheck.sh --disk` output or the Grafana "VM health" dashboard.
2. Retention: a nightly job (`db/migrations` includes a partition-drop for `ticks`
   older than `TICK_RETENTION_DAYS`, default 90) should be keeping this bounded — if
   disk pressure appears anyway, verify that job is actually running
   (`systemctl status mt5bridge-retention.timer`).

## Routine maintenance

- **Certificate renewal**: automatic via `certbot renew` systemd timer
  (`scripts/setup.sh` installs it); verify monthly that it actually ran
  (`certbot certificates`).
- **Dependency updates**: `backend/requirements.txt` pinned versions, bumped via a
  scheduled Dependabot PR (`.github/workflows/`), reviewed and merged manually — never
  auto-merged given this touches a broker connection.
- **Kotak Neo API changes**: the client wraps the official `neo-api-client` SDK — watch
  for SDK version bumps (`pip index versions neo-api-client`) and re-check
  `kotak/websocket_feed.py`'s message-field assumptions (still `# UNVERIFIED`, see
  README) the first time you observe a live tick.

## Escalation

This is a single-operator personal trading bridge, not a team system — "escalation"
means: stop the affected systemd unit, do not place manual orders through MT5 until the
`/health` endpoint is fully green again, and fix at your own pace. There is no
automated trading to "fail open" into, by design.
