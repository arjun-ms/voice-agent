import os
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
import json

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_db_initialized_on_startup(db):
    # db fixture already initialized the db, verify the tables exist
    tables = [r["table_name"] for r in await db.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")]
    
    assert "users" in tables
    assert "appointments" in tables
    assert "conversation_summaries" in tables

@pytest.mark.asyncio
async def test_get_summary_returns_404_when_no_summary(client):
    response = await client.get("/api/summary/+9999999999")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_summary_returns_persisted_summary(db, client):
    from backend.db import get_or_create_user, save_conversation_summary
    
    user = await get_or_create_user(db, "+1112223333", "Test User")
    await save_conversation_summary(
        db, user["id"],
        "Patient requested a checkup.",
        '[{"date": "2030-10-15", "time": "10:00", "status": "booked"}]',
        "Prefers morning"
    )
    
    response = await client.get("/api/summary/+1112223333")
    
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Patient requested a checkup."
    assert len(data["appointments"]) == 1
    assert data["preferences"] == "Prefers morning"
    assert "timestamp" in data

@pytest.mark.asyncio
async def test_post_token_returns_valid_jwt(client):
    response = await client.post("/token", json={"participant_name": "Test User"})
        
    assert response.status_code == 200
    data = response.json()
    
    assert "token" in data
    assert "room_name" in data
    assert data["token"].startswith("eyJ") # Valid JWT prefix
