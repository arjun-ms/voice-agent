import pytest
from httpx import AsyncClient, ASGITransport
import asyncpg
import json
from backend.main import app, DATABASE_URL
from backend.db import init_db, get_or_create_user, save_conversation_summary

import os



@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_get_summary_endpoint(db, client):
    # Create test user
    user = await get_or_create_user(db, "+1234567890", "Test User")
    # Insert a fake summary
    summary_id = await save_conversation_summary(
        db,
        user_id=user["id"],
        summary_text="The user wanted to book an appointment.",
        appointments_json=json.dumps([{"date": "2026-07-01", "time": "10:00"}]),
        preferences=json.dumps({"language": "English"})
    )
    
    # Fetch via API using phone number
    response = await client.get("/api/summary/%2B1234567890")
    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "The user wanted to book an appointment."
    assert data["appointments"] == [{"date": "2026-07-01", "time": "10:00"}]
    assert "English" in data["preferences"]
    assert "timestamp" in data

@pytest.mark.asyncio
async def test_get_summary_not_found(db, client):
    response = await client.get("/api/summary/+9999999999")
    assert response.status_code == 404
