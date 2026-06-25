import aiosqlite
import json
from datetime import datetime, timezone
import re
from backend.db import get_or_create_user, create_appointment, get_user_appointments, update_appointment, save_conversation_summary

def validate_phone(phone: str):
    if not re.match(r"^\+?[1-9]\d{6,14}$", phone):
        raise ValueError("Invalid phone number format. Must be E.164 format (e.g. +1234567890)")

def validate_date(date: str):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        raise ValueError("Invalid date format. Must be YYYY-MM-DD")

def validate_time(time: str):
    if not re.match(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$", time):
        raise ValueError("Invalid time format. Must be HH:MM in 24-hour format")

async def identify_user(conn: aiosqlite.Connection, phone_number: str, name: str = None) -> dict:
    """Look up or create a user by phone number. Returns user info dict."""
    validate_phone(phone_number)
    return await get_or_create_user(conn, phone_number, name)

# All possible 30-minute slots from 9:00 to 16:30
ALL_SLOTS = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in (0, 30) if not (h == 17 and m == 0)]

async def fetch_slots(conn: aiosqlite.Connection, date: str) -> dict:
    """Return available time slots for a given date, excluding booked ones."""
    validate_date(date)
    today = datetime.now().strftime("%Y-%m-%d")
    if date < today:
        raise ValueError(f"Cannot fetch slots for a past date: {date}")
    conn.row_factory = aiosqlite.Row
    async with conn.execute(
        "SELECT time FROM appointments WHERE date = ? AND status = 'booked'",
        (date,)
    ) as cursor:
        booked = {row["time"] for row in await cursor.fetchall()}
    
    available = [s for s in ALL_SLOTS if s not in booked]
    return {"date": date, "available_slots": available}

async def book_appointment(conn: aiosqlite.Connection, user_id: int, date: str, time: str) -> dict:
    """Book an appointment. Raises ValueError if slot is taken."""
    validate_date(date)
    validate_time(time)
    today = datetime.now().strftime("%Y-%m-%d")
    if date < today:
        raise ValueError(f"Cannot book an appointment in the past: {date}")
    return await create_appointment(conn, user_id, date, time)

async def retrieve_appointments(conn: aiosqlite.Connection, user_id: int) -> list[dict]:
    """Return all appointments for the user."""
    return await get_user_appointments(conn, user_id)

async def cancel_appointment(conn: aiosqlite.Connection, appointment_id: int, user_id: int) -> bool:
    """Cancel an appointment. Verifies user ownership."""
    return await update_appointment(conn, appointment_id, user_id, status="cancelled")

async def modify_appointment(conn: aiosqlite.Connection, appointment_id: int, user_id: int, date: str = None, time: str = None) -> bool:
    """Modify an appointment's date/time. Verifies ownership and prevents double booking."""
    if date:
        validate_date(date)
        today = datetime.now().strftime("%Y-%m-%d")
        if date < today:
            raise ValueError(f"Cannot book an appointment in the past: {date}")
    if time:
        validate_time(time)
    return await update_appointment(conn, appointment_id, user_id, date=date, time=time)

async def end_conversation(conn: aiosqlite.Connection, user_id: int, conversation_history: list[dict], summarize_fn=None) -> dict:
    """End the conversation: generate summary, persist it, return structured result."""
    # Get the user's appointments
    appointments = await get_user_appointments(conn, user_id)
    
    # Generate summary via the injected summarize function
    if summarize_fn:
        llm_result = await summarize_fn(conversation_history)
    else:
        llm_result = {"summary": "Conversation ended.", "preferences": ""}
    
    summary_text = llm_result.get("summary", "")
    preferences = llm_result.get("preferences", "")
    appointments_json = json.dumps(appointments)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Persist to DB
    await save_conversation_summary(conn, user_id, summary_text, appointments_json, preferences)
    
    return {
        "summary": summary_text,
        "appointments": appointments,
        "preferences": preferences,
        "timestamp": timestamp,
    }
