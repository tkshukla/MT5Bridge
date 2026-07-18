import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://mt5bridge:mt5bridge@localhost:5433/mt5bridge_test",
)
SCHEMA_SQL_PATH = Path(__file__).resolve().parents[3] / "db" / "schema.sql"

DATA_TABLES = [
    "audit_logs",
    "orders",
    "portfolio_snapshots",
    "holdings",
    "positions",
    "candles",
    "ticks",
    "api_keys",
    "symbols",
]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _apply_schema():
    engine = create_async_engine(TEST_DATABASE_URL)
    schema_sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    async with engine.begin() as conn:
        await conn.exec_driver_sql(schema_sql)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(DATA_TABLES)} RESTART IDENTITY CASCADE"))
    await engine.dispose()
    yield


@pytest_asyncio.fixture
async def seed_symbol():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO symbols (symbol, exchange, segment, kotak_exchange_segment, lot_size, tick_size, mt5_symbol_name)
                VALUES ('NIFTY24JULFUT', 'NFO', 'FUT', 'NSEFO', 50, 0.05, 'NIFTY_FUT_JUL24')
                """
            )
        )
    await engine.dispose()


@pytest_asyncio.fixture
async def client(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "unused-see-database-url-override")
    from app import db as db_module
    from app.config import get_settings

    get_settings.cache_clear()
    engine = create_async_engine(TEST_DATABASE_URL)
    from sqlalchemy.ext.asyncio import async_sessionmaker

    test_session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_module, "async_session_factory", test_session_factory)

    from app.main import app

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[db_module.get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()
