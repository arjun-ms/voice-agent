import pytest
import aiosqlite
from backend.db import init_db
from backend.tools import identify_user, fetch_slots, book_appointment, retrieve_appointments, cancel_appointment, modify_appointment

@pytest.fixture
async def db():
    async with aiosqlite.connect(":memory:") as conn:
        await conn.execute("PRAGMA foreign_keys = ON;")
        await init_db(conn)
        yield conn

async def test_identify_user_creates_new_user(db):
    result = await identify_user(db, "+1234567890", "John Doe")
    
    assert result["phone_number"] == "+1234567890"
    assert result["name"] == "John Doe"
    assert "id" in result

async def test_identify_user_returns_existing_user(db):
    first = await identify_user(db, "+1234567890", "John Doe")
    second = await identify_user(db, "+1234567890", "Different Name")
    
    assert second["id"] == first["id"]
    assert second["phone_number"] == "+1234567890"

async def test_fetch_slots_returns_all_slots_when_none_booked(db):
    result = await fetch_slots(db, "2024-10-15")
    
    assert result["date"] == "2024-10-15"
    slots = result["available_slots"]
    # 9:00 to 16:30 in 30-min blocks = 16 slots
    assert len(slots) == 16
    assert "09:00" in slots
    assert "16:30" in slots
    assert "17:00" not in slots

async def test_fetch_slots_excludes_booked_slots(db):
    user = await identify_user(db, "+1234567890", "John Doe")
    # Book two slots via the DB directly
    from backend.db import create_appointment
    await create_appointment(db, user["id"], "2024-10-15", "10:00")
    await create_appointment(db, user["id"], "2024-10-15", "14:30")
    
    result = await fetch_slots(db, "2024-10-15")
    slots = result["available_slots"]
    
    assert "10:00" not in slots
    assert "14:30" not in slots
    assert len(slots) == 14  # 16 - 2 booked

async def test_book_appointment_returns_confirmation(db):
    user = await identify_user(db, "+1234567890", "John Doe")
    
    result = await book_appointment(db, user["id"], "2024-10-15", "10:00")
    
    assert result["date"] == "2024-10-15"
    assert result["time"] == "10:00"
    assert result["status"] == "booked"
    assert "id" in result

async def test_book_appointment_rejects_double_booking(db):
    user1 = await identify_user(db, "+1234567890", "John Doe")
    user2 = await identify_user(db, "+0987654321", "Jane Doe")
    
    await book_appointment(db, user1["id"], "2024-10-15", "11:00")
    
    with pytest.raises(ValueError, match="Slot already booked"):
        await book_appointment(db, user2["id"], "2024-10-15", "11:00")

async def test_retrieve_appointments_returns_user_bookings(db):
    user = await identify_user(db, "+1234567890", "John Doe")
    await book_appointment(db, user["id"], "2024-10-15", "10:00")
    await book_appointment(db, user["id"], "2024-10-16", "14:00")
    
    result = await retrieve_appointments(db, user["id"])
    
    assert len(result) == 2
    assert result[0]["date"] == "2024-10-15"
    assert result[1]["date"] == "2024-10-16"

async def test_cancel_appointment_frees_slot(db):
    user = await identify_user(db, "+1234567890", "John Doe")
    appt = await book_appointment(db, user["id"], "2024-10-15", "10:00")
    
    result = await cancel_appointment(db, appt["id"], user["id"])
    assert result is True
    
    # Verify status changed
    appts = await retrieve_appointments(db, user["id"])
    assert appts[0]["status"] == "cancelled"
    
    # Verify slot is available again
    slots = await fetch_slots(db, "2024-10-15")
    assert "10:00" in slots["available_slots"]

async def test_modify_appointment_updates_time(db):
    user = await identify_user(db, "+1234567890", "John Doe")
    appt = await book_appointment(db, user["id"], "2024-10-15", "10:00")
    
    result = await modify_appointment(db, appt["id"], user["id"], time="11:00")
    assert result is True
    
    appts = await retrieve_appointments(db, user["id"])
    assert appts[0]["time"] == "11:00"
    
    # Old slot should be free, new slot should be taken
    slots = await fetch_slots(db, "2024-10-15")
    assert "10:00" in slots["available_slots"]
    assert "11:00" not in slots["available_slots"]

async def test_modify_appointment_rejects_double_booking(db):
    user = await identify_user(db, "+1234567890", "John Doe")
    await book_appointment(db, user["id"], "2024-10-15", "10:00")
    appt2 = await book_appointment(db, user["id"], "2024-10-15", "11:00")
    
    with pytest.raises(ValueError, match="Slot already booked"):
        await modify_appointment(db, appt2["id"], user["id"], time="10:00")
