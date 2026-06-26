import pytest
from httpx import AsyncClient, ASGITransport
import aiosqlite
import json
from backend.main import app
from backend.db import init_db, get_or_create_user, save_conversation_summary

import os

@pytest.fixture
async def test_db():
    db_path = "test_summary.sqlite"
    if os.path.exists(db_path):
        os.remove(db_path)
    os.environ["DB_PATH"] = db_path
    import backend.main
    backend.main.DB_PATH = db_path
    
    conn = await aiosqlite.connect(db_path)
    await init_db(conn)
    app.state.db_path = db_path
    
    # Create test user
    await get_or_create_user(conn, "+1234567890", "Test User")
    
    yield conn
    await conn.close()
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_get_summary_endpoint(test_db, client):
    # Insert a fake summary
    summary_id = await save_conversation_summary(
        test_db,
        user_id=1,
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
async def test_get_summary_not_found(test_db, client):
    response = await client.get("/api/summary/+9999999999")
    assert response.status_code == 404
