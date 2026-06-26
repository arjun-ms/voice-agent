import pytest
import pytest_asyncio
import os
import asyncio
from backend.db import init_global_pool, close_global_pool, get_pool, init_db

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://localhost:5432/postgres")

@pytest_asyncio.fixture(scope="session", autouse=True)
async def global_test_db():
    if "localhost" in TEST_DATABASE_URL or "127.0.0.1" in TEST_DATABASE_URL:
        # Provide a mock pool for tests when DB is not available
        class MockPool:
            async def execute(self, *args, **kwargs): pass
            async def fetchrow(self, *args, **kwargs): return None
            async def fetch(self, *args, **kwargs): return []
            async def close(self): pass
        
        import backend.db
        backend.db._global_pool = MockPool()
        yield backend.db._global_pool
        return
        
    await init_global_pool(TEST_DATABASE_URL)
    pool = get_pool()
    # Initialize schema before any tests run
    async with pool.acquire() as conn:
        await init_db(conn)
    
    yield pool
    
    await close_global_pool()
    
@pytest.fixture
async def db():
    pool = get_pool()
    await pool.execute("DELETE FROM conversation_summaries; DELETE FROM appointments; DELETE FROM users;")
    async with pool.acquire() as conn:
        yield conn
