# Integration tests

These tests exercise the FastAPI app against a **real Postgres** (schema applied from
`db/schema.sql`) with the **Kotak Neo REST API mocked** via `respx` — they never make a
real network call to Kotak Neo.

## Running

```bash
docker run --rm -d --name mt5bridge-test-pg -p 5433:5432 \
  -e POSTGRES_USER=mt5bridge -e POSTGRES_PASSWORD=mt5bridge -e POSTGRES_DB=mt5bridge_test \
  postgres:16

export TEST_DATABASE_URL="postgresql+asyncpg://mt5bridge:mt5bridge@localhost:5433/mt5bridge_test"
cd backend
pip install -r requirements-dev.txt
pytest tests/integration -v

docker stop mt5bridge-test-pg
```

`conftest.py` applies `db/schema.sql` against `TEST_DATABASE_URL` once per session and
truncates data tables between tests, so tests are independent and re-runnable.
