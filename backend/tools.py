import aiosqlite
from backend.db import get_or_create_user, create_appointment, get_user_appointments, update_appointment

async def identify_user(conn: aiosqlite.Connection, phone_number: str, name: str = None) -> dict:
    """Look up or create a user by phone number. Returns user info dict."""
    return await get_or_create_user(conn, phone_number, name)

# All possible 30-minute slots from 9:00 to 16:30
ALL_SLOTS = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in (0, 30) if not (h == 17 and m == 0)]

async def fetch_slots(conn: aiosqlite.Connection, date: str) -> dict:
    """Return available time slots for a given date, excluding booked ones."""
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
    return await create_appointment(conn, user_id, date, time)

async def retrieve_appointments(conn: aiosqlite.Connection, user_id: int) -> list[dict]:
    """Return all appointments for the user."""
    return await get_user_appointments(conn, user_id)

async def cancel_appointment(conn: aiosqlite.Connection, appointment_id: int, user_id: int) -> bool:
    """Cancel an appointment. Verifies user ownership."""
    return await update_appointment(conn, appointment_id, user_id, status="cancelled")

async def modify_appointment(conn: aiosqlite.Connection, appointment_id: int, user_id: int, date: str = None, time: str = None) -> bool:
    """Modify an appointment's date/time. Verifies ownership and prevents double booking."""
    return await update_appointment(conn, appointment_id, user_id, date=date, time=time)
