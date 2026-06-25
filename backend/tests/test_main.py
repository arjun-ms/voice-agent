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
