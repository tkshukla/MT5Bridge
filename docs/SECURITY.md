# Security

## No automated execution

This is the single most important property of this system. It is enforced structurally,
not just by convention:

- The backend has **no scheduler, no cron, no strategy/signal engine, and no code path
  that calls the Kotak Neo order-placement client except from inside the three
  order-related HTTP handlers** (`manual_order`, `modify_order`, `close_position` in
  `backend/app/routers/orders.py`). Grep the codebase for `kotak_client.place_order(`,
  `kotak_client.modify_order(`, and `kotak_client.cancel_order(` — every call site is in
  that one file, each behind the confirmation-token check below.
- Every order endpoint requires a `confirmation_token` in the request body. The token is
  minted client-side by the MQL5 EA **only** inside the `OnChartEvent` handler for a
  button click, after the user dismisses a confirmation `MessageBox`. The backend does
  not mint tokens and cannot originate a request that contains one.
- Tokens are single-use (checked against the `audit_logs` table) and expire after 60
  seconds (`ORDER_TOKEN_TTL_SECONDS` in `.env`), so a captured/replayed request cannot
  execute a second time or execute long after the user saw the preview.
- `AUTOMATED_TRADING_ENABLED` in `.env` defaults to `false` and there is presently no
  code that reads it to do anything — it exists as an explicit, auditable kill-switch
  placeholder if this constraint is ever deliberately revisited; it does not enable any
  automation today.

## AuthN/AuthZ

- **JWT** (`backend/app/security.py`) for the MT5 desktop client and any operator
  tooling. Short-lived access tokens (default 15 min) + refresh tokens.
- **API keys** for service-to-service calls (Prometheus scraping `/metrics`, health
  checks). API keys are hashed (SHA-256) at rest in Postgres, never stored plaintext.
- Role-based access: `viewer` (GET endpoints only), `trader` (GET + order endpoints),
  `admin` (+ symbol/config management). Enforced via FastAPI dependencies
  (`require_role("trader")`).

## Transport security

- Nginx terminates TLS (Let's Encrypt via Certbot, auto-renewed via systemd timer).
- Internal traffic (FastAPI ↔ Postgres/Redis) stays on the Docker Compose bridge
  network, not exposed on the host.
- The MT5 desktop's static egress IP should be allowlisted in Nginx
  (`nginx/mt5bridge.conf`, `allow`/`deny` directives) in addition to JWT auth —
  defense in depth, not a substitute for auth.

## Secrets management

- All secrets (Kotak Neo API key/secret, TOTP seed, DB password, Redis password, JWT
  signing key) live in `.env`, which is git-ignored. `.env.example` documents every key
  with a placeholder, never a real value.
- Production deployments should source `.env` from a secret manager (e.g. a
  systemd-loaded `EnvironmentFile=` sourced from `/etc/mt5bridge/mt5bridge.env`,
  root-only readable) rather than keeping it in the repo checkout.

## Replay protection

- Order endpoints: `confirmation_token` + TTL + single-use, as above.
- REST endpoints generally: Nginx rate limiting (`limit_req` zone in
  `nginx/mt5bridge.conf`) to blunt brute-force/replay floods.
- WebSocket endpoints require a valid JWT in the connection query string/subprotocol at
  handshake time; the connection is dropped if the token expires mid-session.

## Audit logging

Every order action (attempted or executed, successful or rejected) writes a row to
`audit_logs`: actor, role, endpoint, request payload (secrets redacted), confirmation
token hash, result, and timestamp. This table is append-only at the application layer
(no UPDATE/DELETE routes exist for it).

## Read-only by default

Kotak Neo API credentials should be scoped to the minimum permission set Kotak Neo's API
offers (read-only market data + portfolio, trading enabled only on the specific
key/segment actually needed for manual order routes) — see
[UBUNTU_SETUP.md](UBUNTU_SETUP.md) for where credentials are configured.
