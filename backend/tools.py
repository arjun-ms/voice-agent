
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

async def identify_user(conn, phone_number: str, name: str | None = None) -> dict:
    """Look up or create a user by phone number. Returns user info dict."""
    validate_phone(phone_number)
    return await get_or_create_user(conn, phone_number, name)

# All possible 30-minute slots from 9:00 to 16:30
ALL_SLOTS = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in (0, 30) if not (h == 17 and m == 0)]

def check_date_and_time(date: str, time: str | None = None):
    validate_date(date)
    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    
    # 3. Weekend check
    if date_obj.weekday() >= 5:
        raise ValueError("The clinic is closed on weekends. Please choose a weekday.")
        
    now = datetime.now()
    today = now.date()
    
    if date_obj < today:
        raise ValueError(f"Cannot book an appointment in the past: {date}")
        
    # 1. Past time on current date check
    if date_obj == today and time:
        time_obj = datetime.strptime(time, "%H:%M").time()
        if time_obj <= now.time():
            raise ValueError(f"The time {time} has already passed today. Please choose a future time.")
            
    # 2. Strict ALL_SLOTS check
    if time and time not in ALL_SLOTS:
        raise ValueError(f"Invalid time {time}. Please book only from available slots.")

async def fetch_slots(conn, date: str) -> dict:
    """Return available time slots for a given date, excluding booked ones."""
    check_date_and_time(date)
    
    rows = await conn.fetch(
        "SELECT time FROM appointments WHERE date = $1 AND status = 'booked'",
        date
    )
    booked = {row["time"] for row in rows}
    
    # Filter out past times if the date is today
    now = datetime.now()
    is_today = (datetime.strptime(date, "%Y-%m-%d").date() == now.date())
    
    available = []
    for s in ALL_SLOTS:
        if s in booked:
            continue
        if is_today:
            s_time = datetime.strptime(s, "%H:%M").time()
            if s_time <= now.time():
                continue
        available.append(s)
        
    return {"date": date, "available_slots": available}

async def book_appointment(conn, user_id: int, date: str, time: str) -> dict:
    """Book an appointment. Raises ValueError if slot is taken."""
    validate_time(time)
    check_date_and_time(date, time)
    return await create_appointment(conn, user_id, date, time)

async def retrieve_appointments(conn, user_id: int) -> list[dict]:
    """Return all appointments for the user."""
    return await get_user_appointments(conn, user_id)

async def cancel_appointment(conn, appointment_id: int, user_id: int) -> bool:
    """Cancel an appointment. Verifies user ownership."""
    return await update_appointment(conn, appointment_id, user_id, status="cancelled")

async def modify_appointment(conn, appointment_id: int, user_id: int, date: str | None = None, time: str | None = None) -> bool:
    """Modify an appointment's date/time. Verifies ownership and prevents double booking."""
    if date or time:
        # If modifying, we need to check the combined new date/time.
        # But we don't have existing date/time here unless we query it. 
        # For simple check, just validate whatever is provided.
        if date and not time:
            check_date_and_time(date)
        elif date and time:
            validate_time(time)
            check_date_and_time(date, time)
        elif time:
            validate_time(time)
            # Cannot fully check time against 'today' without knowing the date.
            if time not in ALL_SLOTS:
                raise ValueError(f"Invalid time {time}. Please book only from available slots.")
                
    return await update_appointment(conn, appointment_id, user_id, date=date, time=time)

async def end_conversation(conn, user_id: int | None, conversation_history: list[dict], summarize_fn=None, cost_breakdown: str | None = None, room_name: str | None = None) -> dict:
    """End the conversation: generate summary, persist it, return structured result."""
    # Get the user's appointments if they were identified
    appointments = await get_user_appointments(conn, user_id) if user_id else []
    
    # Generate summary via the injected summarize function
    if summarize_fn:
        llm_result = await summarize_fn(conversation_history)
    else:
        llm_result = {"summary": "Conversation ended.", "preferences": ""}
    
    summary_text = llm_result.get("summary", "")
    preferences = llm_result.get("preferences", "")
    appointments_dict = [dict(a) for a in appointments] # for frontend to display
    appointments_json = json.dumps(appointments_dict, default=str) # for saving to db (objects are not serializable by default)
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Persist to DB
    await save_conversation_summary(conn, user_id, summary_text, appointments_json, preferences, cost_breakdown, room_name)
    
    return {
        "summary": summary_text,
        "appointments": appointments,
        "preferences": preferences,
        "timestamp": timestamp,
        "cost_breakdown": json.loads(cost_breakdown) if cost_breakdown else None
    }
