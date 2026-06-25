import pytest
import aiosqlite
from backend.db import init_db, get_or_create_user, create_appointment, get_user_appointments, update_appointment, save_conversation_summary

@pytest.fixture
async def memory_db():
    async with aiosqlite.connect(":memory:") as db:
        # Enable foreign keys for sqlite
        await db.execute("PRAGMA foreign_keys = ON;")
        yield db

async def test_init_db_creates_tables(memory_db):
    await init_db(memory_db)
    
    # Check if tables were created
    async with memory_db.execute("SELECT name FROM sqlite_master WHERE type='table';") as cursor:
        tables = [row[0] async for row in cursor]
        
    assert "users" in tables
    assert "appointments" in tables
    assert "conversation_summaries" in tables

async def test_get_or_create_user(memory_db):
    await init_db(memory_db)
    
    # First call should create the user
    user1 = await get_or_create_user(memory_db, "+1234567890", "John Doe")
    assert user1["phone_number"] == "+1234567890"
    assert user1["name"] == "John Doe"
    assert "id" in user1
    
    # Second call with same phone should return existing user
    user2 = await get_or_create_user(memory_db, "+1234567890", "Jane Doe")
    assert user2["id"] == user1["id"]
    # The name shouldn't change if it's returning the existing user (assuming we don't update name)
    assert user2["name"] == "John Doe"

async def test_create_appointment(memory_db):
    await init_db(memory_db)
    user = await get_or_create_user(memory_db, "+1234567890", "John Doe")
    
    appt = await create_appointment(memory_db, user["id"], "2024-10-15", "10:00")
    assert appt["user_id"] == user["id"]
    assert appt["date"] == "2024-10-15"
    assert appt["time"] == "10:00"
    assert appt["status"] == "booked"
    assert "id" in appt

async def test_create_appointment_prevents_double_booking(memory_db):
    await init_db(memory_db)
    user1 = await get_or_create_user(memory_db, "+1234567890", "John Doe")
    user2 = await get_or_create_user(memory_db, "+0987654321", "Jane Doe")
    
    # First booking succeeds
    await create_appointment(memory_db, user1["id"], "2024-10-15", "11:00")
    
    # Second booking for the same date and time should fail
    with pytest.raises(ValueError, match="Slot already booked"):
        await create_appointment(memory_db, user2["id"], "2024-10-15", "11:00")

async def test_get_and_update_appointment(memory_db):
    await init_db(memory_db)
    user = await get_or_create_user(memory_db, "+1234567890", "John Doe")
    
    appt1 = await create_appointment(memory_db, user["id"], "2024-10-15", "10:00")
    appt2 = await create_appointment(memory_db, user["id"], "2024-10-16", "14:00")
    
    appts = await get_user_appointments(memory_db, user["id"])
    assert len(appts) == 2
    
    # Update status to cancelled
    success = await update_appointment(memory_db, appt1["id"], user["id"], status="cancelled")
    assert success is True
    
    appts_after = await get_user_appointments(memory_db, user["id"])
    cancelled_appt = next(a for a in appts_after if a["id"] == appt1["id"])
    assert cancelled_appt["status"] == "cancelled"
    
    # Update time of appt2
    success = await update_appointment(memory_db, appt2["id"], user["id"], time="15:00")
    assert success is True
    appts_after_time = await get_user_appointments(memory_db, user["id"])
    updated_appt = next(a for a in appts_after_time if a["id"] == appt2["id"])
    assert updated_appt["time"] == "15:00"

async def test_update_appointment_prevents_double_booking(memory_db):
    await init_db(memory_db)
    user = await get_or_create_user(memory_db, "+1234567890", "John Doe")
    user2 = await get_or_create_user(memory_db, "+0987654321", "Jane Doe")
    
    await create_appointment(memory_db, user["id"], "2024-10-15", "10:00")
    appt2 = await create_appointment(memory_db, user2["id"], "2024-10-15", "11:00")
    
    # Try to change appt2 to user1's slot
    with pytest.raises(ValueError, match="Slot already booked"):
        await update_appointment(memory_db, appt2["id"], user2["id"], time="10:00")

async def test_save_conversation_summary(memory_db):
    await init_db(memory_db)
    user = await get_or_create_user(memory_db, "+1234567890", "John Doe")
    
    summary_id = await save_conversation_summary(
        memory_db, 
        user["id"], 
        "User wanted to book an appointment.", 
        '[{"id": 1, "date": "2024-10-15", "time": "10:00"}]',
        "Prefers morning appointments"
    )
    
    assert summary_id is not None
    
    # Verify it was saved
    memory_db.row_factory = aiosqlite.Row
    async with memory_db.execute("SELECT * FROM conversation_summaries WHERE id = ?", (summary_id,)) as cursor:
        summary = await cursor.fetchone()
        
    assert summary is not None
    assert summary["user_id"] == user["id"]
    assert summary["summary_text"] == "User wanted to book an appointment."
    assert summary["appointments_json"] == '[{"id": 1, "date": "2024-10-15", "time": "10:00"}]'
    assert summary["preferences"] == "Prefers morning appointments"
