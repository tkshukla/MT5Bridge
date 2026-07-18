"""
Background workers: tick ingestion (write-through cache + candle folding) and the
portfolio poller. Both are read-path only — see docs/SECURITY.md for why nothing here
ever calls into order placement.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.db import async_session_factory
from app.kotak.client import KotakClient
from app.kotak.exceptions import KotakApiError
from app.redis_client import get_redis

logger = logging.getLogger("mt5bridge.workers")

CANDLE_TIMEFRAMES_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}


def _floor_to_bucket(ts: datetime, bucket_seconds: int) -> datetime:
    epoch = int(ts.timestamp())
    floored = epoch - (epoch % bucket_seconds)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


async def handle_tick(tick: dict) -> None:
    symbol = tick["symbol"]
    ltp = tick["ltp"]
    ts = tick.get("ts")
    ts_dt = datetime.fromisoformat(ts) if isinstance(ts, str) else datetime.now(timezone.utc)

    redis = get_redis()
    await redis.set(f"tick:{symbol}", json.dumps(tick), ex=300)
    await redis.publish(f"ticks:{symbol}", json.dumps(tick))

    async with async_session_factory() as db:
        await db.execute(
            text(
                "INSERT INTO ticks (symbol, ltp, volume, bid, ask, ts) "
                "VALUES (:symbol, :ltp, :volume, :bid, :ask, :ts)"
            ),
            {
                "symbol": symbol,
                "ltp": ltp,
                "volume": tick.get("volume"),
                "bid": tick.get("bid"),
                "ask": tick.get("ask"),
                "ts": ts_dt,
            },
        )
        for timeframe, bucket_seconds in CANDLE_TIMEFRAMES_SECONDS.items():
            bucket_open = _floor_to_bucket(ts_dt, bucket_seconds)
            await db.execute(
                text(
                    """
                    INSERT INTO candles (symbol, timeframe, ts_open, open, high, low, close, volume, updated_at)
                    VALUES (:symbol, :timeframe, :ts_open, :ltp, :ltp, :ltp, :ltp, 0, now())
                    ON CONFLICT (symbol, timeframe, ts_open) DO UPDATE SET
                        high = GREATEST(candles.high, EXCLUDED.close),
                        low = LEAST(candles.low, EXCLUDED.close),
                        close = EXCLUDED.close,
                        updated_at = now()
                    """
                ),
                {"symbol": symbol, "timeframe": timeframe, "ts_open": bucket_open, "ltp": ltp},
            )
        await db.commit()


async def poll_portfolio_once(kotak_client: KotakClient) -> None:
    redis = get_redis()
    async with async_session_factory() as db:
        try:
            positions = await kotak_client.get_positions()
            holdings = await kotak_client.get_holdings()
            margins = await kotak_client.get_margins()
        except KotakApiError:
            logger.exception("portfolio poll failed against Kotak Neo API")
            return

        for p in positions:
            await db.execute(
                text(
                    """
                    INSERT INTO positions (symbol, product, quantity, avg_price, ltp, unrealized_pnl, realized_pnl)
                    VALUES (:symbol, :product, :quantity, :avg_price, :ltp, :unrealized_pnl, :realized_pnl)
                    ON CONFLICT (symbol, product) DO UPDATE SET
                        quantity = EXCLUDED.quantity, avg_price = EXCLUDED.avg_price, ltp = EXCLUDED.ltp,
                        unrealized_pnl = EXCLUDED.unrealized_pnl, realized_pnl = EXCLUDED.realized_pnl,
                        snapshot_at = now()
                    """
                ),
                {
                    "symbol": p.get("tradingSymbol") or p.get("symbol"),
                    "product": p.get("product"),
                    "quantity": p.get("quantity", 0),
                    "avg_price": p.get("avgPrice", 0),
                    "ltp": p.get("ltp"),
                    "unrealized_pnl": p.get("unrealizedPnl"),
                    "realized_pnl": p.get("realizedPnl"),
                },
            )

        for h in holdings:
            await db.execute(
                text(
                    """
                    INSERT INTO holdings (symbol, quantity, avg_price, ltp, current_value, pnl)
                    VALUES (:symbol, :quantity, :avg_price, :ltp, :current_value, :pnl)
                    ON CONFLICT (symbol) DO UPDATE SET
                        quantity = EXCLUDED.quantity, avg_price = EXCLUDED.avg_price, ltp = EXCLUDED.ltp,
                        current_value = EXCLUDED.current_value, pnl = EXCLUDED.pnl, snapshot_at = now()
                    """
                ),
                {
                    "symbol": h.get("tradingSymbol") or h.get("symbol"),
                    "quantity": h.get("quantity", 0),
                    "avg_price": h.get("avgPrice", 0),
                    "ltp": h.get("ltp"),
                    "current_value": h.get("currentValue"),
                    "pnl": h.get("pnl"),
                },
            )

        total_value = margins.get("totalValue", 0)
        cash_available = margins.get("cashAvailable", margins.get("availableMargin", 0))
        margin_used = margins.get("marginUsed", margins.get("usedMargin", 0))
        day_pnl = sum((p.get("unrealizedPnl") or 0) + (p.get("realizedPnl") or 0) for p in positions)
        open_pnl = sum((p.get("unrealizedPnl") or 0) for p in positions)
        realized_pnl = sum((p.get("realizedPnl") or 0) for p in positions)

        await db.execute(
            text(
                """
                INSERT INTO portfolio_snapshots
                    (total_value, cash_available, margin_used, day_pnl, open_pnl, realized_pnl)
                VALUES (:total_value, :cash_available, :margin_used, :day_pnl, :open_pnl, :realized_pnl)
                """
            ),
            {
                "total_value": total_value,
                "cash_available": cash_available,
                "margin_used": margin_used,
                "day_pnl": day_pnl,
                "open_pnl": open_pnl,
                "realized_pnl": realized_pnl,
            },
        )
        await db.commit()

    await redis.publish(
        "portfolio:updates",
        json.dumps({"type": "portfolio_snapshot", "day_pnl": day_pnl, "open_pnl": open_pnl}),
    )
