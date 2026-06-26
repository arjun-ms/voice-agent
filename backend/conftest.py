import pytest
import os
import asyncio
from backend.db import init_global_pool, close_global_pool, get_pool, init_db

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://localhost:5432/postgres")

@pytest.fixture(scope="session", autouse=True)
async def global_test_db():
    await init_global_pool(TEST_DATABASE_URL)
    pool = get_pool()
    async with pool.acquire() as conn:
        await init_db(conn)
    yield
    # We do not close the pool since it's shared across async loops during tests
    
@pytest.fixture
async def db():
    pool = get_pool()
    await pool.execute("DELETE FROM conversation_summaries; DELETE FROM appointments; DELETE FROM users;")
    async with pool.acquire() as conn:
        yield conn
