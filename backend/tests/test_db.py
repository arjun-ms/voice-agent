import pytest
import asyncpg
import os
from backend.db import init_db, get_or_create_user, create_appointment, get_user_appointments, update_appointment, save_conversation_summary



@pytest.mark.asyncio
async def test_init_db_creates_tables(db):
    # Pass the pool to our init_db function
    # Note: db already initialized tables, just verifying
    
    # Verify tables were created
    tables = await db.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public';
    """)
        
    table_names = [t['table_name'] for t in tables]
    assert "users" in table_names
    assert "appointments" in table_names
    assert "conversation_summaries" in table_names

@pytest.mark.asyncio
async def test_get_or_create_user(db):
    # First call should create the user
    user1 = await get_or_create_user(db, "+1234567890", "John Doe")
    assert user1["phone_number"] == "+1234567890"
    assert user1["name"] == "John Doe"
    assert "id" in user1
    
    # Second call with same phone should return existing user
    user2 = await get_or_create_user(db, "+1234567890", "Jane Doe")
    assert user2["id"] == user1["id"]
    # The name shouldn't change if it's returning the existing user (assuming we don't update name)
    assert user2["name"] == "John Doe"

@pytest.mark.asyncio
async def test_create_appointment(db):
    user = await get_or_create_user(db, "+1234567890", "John Doe")
    
    appt = await create_appointment(db, user["id"], "2030-10-15", "10:00")
    assert appt["user_id"] == user["id"]
    assert appt["date"] == "2030-10-15"
    assert appt["time"] == "10:00"
    assert appt["status"] == "booked"
    assert "id" in appt

@pytest.mark.asyncio
async def test_create_appointment_prevents_double_booking(db):
    user1 = await get_or_create_user(db, "+1234567890", "John Doe")
    user2 = await get_or_create_user(db, "+0987654321", "Jane Doe")
    
    # First booking succeeds
    await create_appointment(db, user1["id"], "2030-10-15", "11:00")
    
    # Second booking for the same date and time should fail
    with pytest.raises(ValueError, match="This slot was just taken"):
        await create_appointment(db, user2["id"], "2030-10-15", "11:00")

@pytest.mark.asyncio
async def test_get_and_update_appointment(db):
    user = await get_or_create_user(db, "+1234567890", "John Doe")
    
    appt1 = await create_appointment(db, user["id"], "2030-10-15", "10:00")
    appt2 = await create_appointment(db, user["id"], "2030-10-16", "14:00")
    
    appts = await get_user_appointments(db, user["id"])
    assert len(appts) == 2
    
    # Update status to cancelled
    success = await update_appointment(db, appt1["id"], user["id"], status="cancelled")
    assert success is True
    
    appts_after = await get_user_appointments(db, user["id"])
    cancelled_appt = next(a for a in appts_after if a["id"] == appt1["id"])
    assert cancelled_appt["status"] == "cancelled"
    
    # Update time of appt2
    success = await update_appointment(db, appt2["id"], user["id"], time="15:00")
    assert success is True
    appts_after_time = await get_user_appointments(db, user["id"])
    updated_appt = next(a for a in appts_after_time if a["id"] == appt2["id"])
    assert updated_appt["time"] == "15:00"

@pytest.mark.asyncio
async def test_update_appointment_prevents_double_booking(db):
    user = await get_or_create_user(db, "+1234567890", "John Doe")
    user2 = await get_or_create_user(db, "+0987654321", "Jane Doe")
    
    await create_appointment(db, user["id"], "2030-10-15", "10:00")
    appt2 = await create_appointment(db, user2["id"], "2030-10-15", "11:00")
    
    # Try to change appt2 to user1's slot
    with pytest.raises(ValueError, match="This slot was just taken"):
        await update_appointment(db, appt2["id"], user2["id"], time="10:00")

@pytest.mark.asyncio
async def test_save_conversation_summary(db):
    user = await get_or_create_user(db, "+1234567890", "John Doe")
    
    summary_id = await save_conversation_summary(
        db, 
        user["id"], 
        "User wanted to book an appointment.", 
        '[{"id": 1, "date": "2030-10-15", "time": "10:00"}]',
        "Prefers morning appointments"
    )
    
    assert summary_id is not None
    
    # Verify it was saved
    summary = await db.fetchrow("SELECT * FROM conversation_summaries WHERE id = $1", summary_id)
        
    assert summary is not None
    assert summary["user_id"] == user["id"]
    assert summary["summary_text"] == "User wanted to book an appointment."
    assert summary["appointments_json"] == '[{"id": 1, "date": "2030-10-15", "time": "10:00"}]'
    assert summary["preferences"] == "Prefers morning appointments"

@pytest.mark.asyncio
async def test_init_global_pool_fails_on_render_with_localhost():
    import os
    import backend.db
    # Reset the global pool for the test, but preserve it to restore later
    original_pool = backend.db._global_pool
    backend.db._global_pool = None
    # Temporarily set RENDER env var
    original_render = os.environ.get("RENDER")
    os.environ["RENDER"] = "true"
    
    try:
        with pytest.raises(RuntimeError, match="DATABASE_URL environment variable is not set"):
            await backend.db.init_global_pool("postgresql://localhost:5432/postgres")
    finally:
        backend.db._global_pool = original_pool
        if original_render is not None:
            os.environ["RENDER"] = original_render
        else:
            del os.environ["RENDER"]


@pytest.mark.asyncio
async def test_dsn_password_encoding(monkeypatch):
    import backend.db
    
    passed_dsn = None
    
    # Mock create_pool to just capture the DSN
    async def mock_create_pool(dsn, **kwargs):
        nonlocal passed_dsn
        passed_dsn = dsn
        return "mock_pool"
        
    monkeypatch.setattr(backend.db.asyncpg, "create_pool", mock_create_pool)
    
    # Reset the global pool for the test, but preserve it to restore later
    original_pool = backend.db._global_pool
    backend.db._global_pool = None
    
    try:
        # Test with an unencoded @ in the password
        test_dsn = "postgresql://user:pass@word@host:5432/db"
        await backend.db.init_global_pool(test_dsn)
        
        assert passed_dsn == "postgresql://user:pass%40word@host:5432/db"
    finally:
        # Reset it back
        backend.db._global_pool = original_pool

