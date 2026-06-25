import os
import pytest
import aiosqlite
from fastapi.testclient import TestClient
from backend.main import app, DB_PATH

def test_health_check():
    with TestClient(app) as client:
        response = client.get("/health")
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_db_initialized_on_startup():
    # TestClient context manager guarantees lifespan startup/shutdown
    with TestClient(app):
        pass
    
    # Check if the DB file exists and tables are created
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table';") as cursor:
            tables = [row[0] async for row in cursor]
            
    assert "users" in tables
    assert "appointments" in tables
    assert "conversation_summaries" in tables

def test_get_summary_returns_404_when_no_summary():
    with TestClient(app) as client:
        response = client.get("/api/summary/+9999999999")
    
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_get_summary_returns_persisted_summary():
    # Seed data directly into the DB, then hit the endpoint
    async with aiosqlite.connect(DB_PATH) as db:
        from backend.db import init_db, get_or_create_user, save_conversation_summary
        await init_db(db)
        user = await get_or_create_user(db, "+1112223333", "Test User")
        await save_conversation_summary(
            db, user["id"],
            "Patient requested a checkup.",
            '[{"date": "2030-10-15", "time": "10:00", "status": "booked"}]',
            "Prefers morning"
        )
    
    with TestClient(app) as client:
        response = client.get("/api/summary/+1112223333")
    
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Patient requested a checkup."
    assert len(data["appointments"]) == 1
    assert data["preferences"] == "Prefers morning"
    assert "timestamp" in data
