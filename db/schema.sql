-- MT5Bridge PostgreSQL schema
-- Idempotent: safe to re-run (CREATE ... IF NOT EXISTS throughout).

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ---------------------------------------------------------------------------
-- symbols: tradable instrument master + MT5 custom-symbol mapping
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS symbols (
    symbol            TEXT PRIMARY KEY,          -- Kotak Neo trading_symbol, e.g. NIFTY24JULFUT — used as-is
                                                   -- in neo_api_client place_order/modify_order calls
    exchange          TEXT NOT NULL,              -- NSE, NFO, BSE, MCX... (informational)
    segment           TEXT NOT NULL,              -- EQ, FUT, OPT, INDEX (informational)
    kotak_exchange_segment TEXT NOT NULL,          -- neo_api_client exchange_segment code, e.g. "NSECM",
                                                   -- "NSEFO", "BSECM", "BSEFO", "MCXFO" — set per Kotak Neo's
                                                   -- own segment codes for this instrument, not inferred
    instrument_token  TEXT,                       -- Kotak Neo scrip/instrument token (from scrip_master/search_scrip)
    underlying        TEXT,                       -- e.g. NIFTY for an option/future
    expiry            DATE,                       -- NULL for equities/indices
    strike            NUMERIC(18, 4),             -- NULL unless an option
    option_type       TEXT CHECK (option_type IN ('CE', 'PE')),
    lot_size          INTEGER NOT NULL DEFAULT 1,
    tick_size         NUMERIC(18, 4) NOT NULL DEFAULT 0.05,
    mt5_symbol_name   TEXT NOT NULL,              -- name registered as a custom symbol in MT5
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_symbols_mt5_name ON symbols (mt5_symbol_name);
CREATE INDEX IF NOT EXISTS idx_symbols_underlying ON symbols (underlying);

-- ---------------------------------------------------------------------------
-- ticks: raw tick stream, partitioned by day for retention/drop efficiency
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticks (
    id          BIGSERIAL,
    symbol      TEXT NOT NULL REFERENCES symbols (symbol),
    ltp         NUMERIC(18, 4) NOT NULL,
    volume      BIGINT,
    bid         NUMERIC(18, 4),
    ask         NUMERIC(18, 4),
    ts          TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

CREATE INDEX IF NOT EXISTS idx_ticks_symbol_ts ON ticks (symbol, ts DESC);

-- A single default partition holds all ticks; scripts/retention.sh (run daily via
-- mt5bridge-retention.timer) DELETEs rows older than TICK_RETENTION_DAYS and VACUUMs.
-- If tick volume grows enough that DELETE-based retention becomes too slow, switch to
-- day-range partitions with DROP TABLE-based retention instead — the PARTITION BY
-- RANGE(ts) declaration above already supports adding those without a schema change.
CREATE TABLE IF NOT EXISTS ticks_default PARTITION OF ticks DEFAULT;

-- ---------------------------------------------------------------------------
-- candles: OHLC bars per symbol/timeframe
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candles (
    symbol     TEXT NOT NULL REFERENCES symbols (symbol),
    timeframe  TEXT NOT NULL,          -- '1m', '5m', '15m', '1h', '1d'
    ts_open    TIMESTAMPTZ NOT NULL,   -- candle open time
    open       NUMERIC(18, 4) NOT NULL,
    high       NUMERIC(18, 4) NOT NULL,
    low        NUMERIC(18, 4) NOT NULL,
    close      NUMERIC(18, 4) NOT NULL,
    volume     BIGINT NOT NULL DEFAULT 0,
    is_final   BOOLEAN NOT NULL DEFAULT FALSE,   -- true once the bar period has elapsed
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, timeframe, ts_open)
);

CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_ts ON candles (symbol, timeframe, ts_open DESC);

-- ---------------------------------------------------------------------------
-- positions: current open positions (upserted from Kotak Neo poll)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS positions (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol          TEXT NOT NULL REFERENCES symbols (symbol),
    product         TEXT NOT NULL,        -- MIS, CNC, NRML (UNVERIFIED against Kotak Neo's exact product codes)
    quantity        INTEGER NOT NULL,     -- signed: positive long, negative short
    avg_price       NUMERIC(18, 4) NOT NULL,
    ltp             NUMERIC(18, 4),
    unrealized_pnl  NUMERIC(18, 4),
    realized_pnl    NUMERIC(18, 4),
    kotak_position_ref TEXT,              -- Kotak Neo's own position identifier, if any
    snapshot_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol, product)
);

-- ---------------------------------------------------------------------------
-- holdings: delivery holdings (upserted from Kotak Neo poll)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS holdings (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol         TEXT NOT NULL REFERENCES symbols (symbol),
    quantity       INTEGER NOT NULL,
    avg_price      NUMERIC(18, 4) NOT NULL,
    ltp            NUMERIC(18, 4),
    current_value  NUMERIC(18, 4),
    pnl            NUMERIC(18, 4),
    snapshot_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (symbol)
);

-- ---------------------------------------------------------------------------
-- orders: every manual order action attempted through this bridge
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS orders (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kotak_order_id      TEXT,                      -- NULL until/unless Kotak Neo accepts it
    symbol              TEXT NOT NULL REFERENCES symbols (symbol),
    side                TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    order_type          TEXT NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'SL', 'SL-M')),
    product             TEXT NOT NULL,
    quantity            INTEGER NOT NULL CHECK (quantity > 0),
    price               NUMERIC(18, 4),
    action              TEXT NOT NULL CHECK (action IN ('PLACE', 'MODIFY', 'CLOSE')),
    status              TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING', 'PLACED', 'FILLED', 'PARTIALLY_FILLED',
                                           'REJECTED', 'CANCELLED', 'MODIFIED')),
    reject_reason       TEXT,
    confirmation_token_hash TEXT NOT NULL,          -- SHA-256 of the token; raw token never stored
    confirmed_at        TIMESTAMPTZ NOT NULL,       -- when the MT5 user clicked confirm
    placed_by           TEXT NOT NULL,              -- JWT subject / operator identity
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders (symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_token_hash ON orders (confirmation_token_hash);

-- ---------------------------------------------------------------------------
-- portfolio_snapshots: periodic rollup for P&L / analytics history
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    total_value       NUMERIC(18, 4) NOT NULL,
    cash_available    NUMERIC(18, 4) NOT NULL,
    margin_used       NUMERIC(18, 4) NOT NULL,
    day_pnl           NUMERIC(18, 4) NOT NULL,
    open_pnl          NUMERIC(18, 4) NOT NULL,
    realized_pnl      NUMERIC(18, 4) NOT NULL,
    snapshot_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_ts ON portfolio_snapshots (snapshot_at DESC);

-- ---------------------------------------------------------------------------
-- api_keys: service-account keys (e.g. Prometheus scraping /metrics)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS api_keys (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    label       TEXT NOT NULL UNIQUE,
    key_hash    TEXT NOT NULL UNIQUE,   -- SHA-256 of the raw key; raw key shown once at creation
    role        TEXT NOT NULL DEFAULT 'viewer' CHECK (role IN ('viewer', 'trader', 'admin')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- audit_logs: append-only log of every auth event and order action
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_logs (
    id            BIGSERIAL PRIMARY KEY,
    actor         TEXT NOT NULL,          -- JWT subject or API key label
    role          TEXT NOT NULL,
    action        TEXT NOT NULL,          -- e.g. 'manual_order', 'modify_order', 'close_position', 'login'
    endpoint      TEXT NOT NULL,
    request_meta  JSONB NOT NULL DEFAULT '{}'::jsonb,   -- secrets/tokens redacted before insert
    result        TEXT NOT NULL,          -- 'success', 'rejected', 'error'
    detail        TEXT,
    source_ip     INET,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_ts ON audit_logs (actor, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);

-- No UPDATE/DELETE grants on audit_logs for the application role — enforced at the
-- application layer (no such routes exist) and can additionally be enforced with a
-- dedicated least-privilege DB role if desired:
--
-- REVOKE UPDATE, DELETE ON audit_logs FROM mt5bridge_app;
