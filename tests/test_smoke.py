"""Minimal API tests. Run: pytest (uses the dev SQLite db)."""
import httpx
import pytest

from app.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_headers(client):
    r = await client.post(
        "/api/v1/auth/login",
        data={"username": "owner@studyhub.in", "password": "studyhub123"},
    )
    assert r.status_code == 200, "Seed the DB first: python -m scripts.seed"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_health(client):
    assert (await client.get("/health")).json()["status"] == "ok"


async def test_dashboard_kpis(client, auth_headers):
    kpis = (await client.get("/api/v1/dashboard", headers=auth_headers)).json()["kpis"]
    assert kpis["total_students"] >= 12
    assert 0 <= kpis["occupancy_rate"] <= 1


async def test_students_due_filter(client, auth_headers):
    due = (await client.get("/api/v1/students?status=due", headers=auth_headers)).json()
    assert all(s["status"] == "due" for s in due["items"])


async def test_onboard_triggers_seat_and_welcome(client, auth_headers):
    plans = (await client.get("/api/v1/plans", headers=auth_headers)).json()
    batches = (await client.get("/api/v1/batches", headers=auth_headers)).json()
    halls = (await client.get("/api/v1/halls", headers=auth_headers)).json()
    r = await client.post("/api/v1/students", headers=auth_headers, json={
        "name": "PyTest User", "phone": "+91 90000 11111",
        "plan_id": plans[0]["id"], "batch_id": batches[0]["id"], "hall_id": halls[0]["id"]})
    assert r.status_code == 201
    assert r.json()["seat_id"] is not None
