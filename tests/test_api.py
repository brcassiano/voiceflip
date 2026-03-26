# E2E API tests
import asyncio

import httpx
import pytest

from app.main import app
from app.store import InMemoryStore


@pytest.fixture(autouse=True)
def _reset_store():
    """Reset the global store before each test."""
    import app.main as main_mod
    main_mod._store = InMemoryStore()
    yield


@pytest.fixture
def client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_post_returns_pending(client):
    resp = await client.post("/requests", json={"payload": {"scenario": "ok"}})
    assert resp.status_code == 200
    data = resp.json()
    assert "request_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_not_found(client):
    resp = await client.get("/requests/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_ok_flow(client):
    resp = await client.post("/requests", json={"payload": {"scenario": "ok"}})
    request_id = resp.json()["request_id"]

    await asyncio.sleep(0.5)

    resp = await client.get(f"/requests/{request_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["degraded"] is False


@pytest.mark.asyncio
async def test_hard_fail_flow(client):
    resp = await client.post("/requests", json={"payload": {"scenario": "hard_fail"}})
    request_id = resp.json()["request_id"]

    await asyncio.sleep(0.5)

    resp = await client.get(f"/requests/{request_id}")
    data = resp.json()
    assert data["status"] == "failed"


@pytest.mark.asyncio
async def test_health_counters(client):
    # Submit two requests
    await client.post("/requests", json={"payload": {"scenario": "ok"}})
    await client.post("/requests", json={"payload": {"scenario": "ok"}})

    await asyncio.sleep(1.0)

    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_processed"] == 2
    assert data["primary"]["success"] == 2
    assert data["optional"]["success"] == 2
