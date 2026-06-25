import json
import pytest
import aiosqlite
from backend.db import init_db
from backend.agent import TOOL_SCHEMAS, SYSTEM_PROMPT, dispatch_tool_call

@pytest.fixture
async def db():
    async with aiosqlite.connect(":memory:") as conn:
        await conn.execute("PRAGMA foreign_keys = ON;")
        await init_db(conn)
        yield conn

def test_tool_schemas_cover_all_seven_tools():
    tool_names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    
    expected = {
        "identify_user",
        "fetch_slots",
        "book_appointment",
        "retrieve_appointments",
        "cancel_appointment",
        "modify_appointment",
        "end_conversation",
    }
    assert tool_names == expected

def test_system_prompt_contains_key_instructions():
    prompt_lower = SYSTEM_PROMPT.lower()
    # Must mention healthcare context
    assert "healthcare" in prompt_lower or "health" in prompt_lower
    # Must mention extraction of key fields
    assert "phone" in prompt_lower
    assert "name" in prompt_lower
    assert "date" in prompt_lower
    assert "time" in prompt_lower

async def test_dispatch_routes_to_correct_tools(db):
    # identify_user
    result_json = await dispatch_tool_call(db, "identify_user", {"phone_number": "+1234567890", "name": "John Doe"})
    result = json.loads(result_json)
    assert result["phone_number"] == "+1234567890"
    user_id = result["id"]
    
    # fetch_slots
    result_json = await dispatch_tool_call(db, "fetch_slots", {"date": "2024-10-15"})
    result = json.loads(result_json)
    assert "available_slots" in result
    assert "10:00" in result["available_slots"]
    
    # book_appointment
    result_json = await dispatch_tool_call(db, "book_appointment", {"user_id": user_id, "date": "2024-10-15", "time": "10:00"})
    result = json.loads(result_json)
    assert result["status"] == "booked"
    assert result["time"] == "10:00"
    
    # retrieve_appointments
    result_json = await dispatch_tool_call(db, "retrieve_appointments", {"user_id": user_id})
    result = json.loads(result_json)
    assert len(result) == 1
    
    # fetch_slots again - booked slot should be gone
    result_json = await dispatch_tool_call(db, "fetch_slots", {"date": "2024-10-15"})
    result = json.loads(result_json)
    assert "10:00" not in result["available_slots"]

async def test_dispatch_unknown_tool_returns_error(db):
    result_json = await dispatch_tool_call(db, "nonexistent_tool", {})
    result = json.loads(result_json)
    assert "error" in result
    assert "Unknown tool" in result["error"]

async def test_dispatch_returns_error_on_double_booking(db):
    # Set up a user and book a slot
    r = await dispatch_tool_call(db, "identify_user", {"phone_number": "+5555555555"})
    user_id = json.loads(r)["id"]
    await dispatch_tool_call(db, "book_appointment", {"user_id": user_id, "date": "2024-12-01", "time": "09:00"})
    
    # Try to double-book the same slot
    result_json = await dispatch_tool_call(db, "book_appointment", {"user_id": user_id, "date": "2024-12-01", "time": "09:00"})
    result = json.loads(result_json)
    assert "error" in result
    assert "already booked" in result["error"].lower()
