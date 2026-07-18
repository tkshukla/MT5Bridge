import pytest


@pytest.mark.asyncio
async def test_health_requires_no_auth_and_reports_db_ok(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["db"] == "ok"
    assert body["kotak_feed"] == "disconnected"  # no feed wired up in this test client
