import asyncpg
import os

import asyncio

_pools = {}

async def init_global_pool(dsn: str):
    loop = asyncio.get_running_loop()
    if loop not in _pools:
        if os.environ.get("RENDER") == "true" and ("localhost" in dsn or "127.0.0.1" in dsn):
            raise RuntimeError("DATABASE_URL environment variable is not set. Please configure it in your Render dashboard.")
            
        import urllib.parse
        parsed = urllib.parse.urlparse(dsn)
        if parsed.password and "@" in parsed.password:
            auth = f"{parsed.username}:{urllib.parse.quote(parsed.password)}@" if parsed.password else ""
            port_part = f":{parsed.port}" if parsed.port else ""
            netloc = f"{auth}{parsed.hostname}{port_part}"
            dsn = urllib.parse.urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
            
        _pools[loop] = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
    return _pools[loop]

def get_pool():
    loop = asyncio.get_running_loop()
    if loop not in _pools:
        raise RuntimeError("Pool is not initialized for this event loop")
    return _pools[loop]

async def close_global_pool():
    loop = asyncio.get_running_loop()
    if loop in _pools:
        await _pools[loop].close()
        del _pools[loop]

async def init_db(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            phone_number TEXT UNIQUE NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'booked',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_summaries (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            summary_text TEXT NOT NULL,
            appointments_json TEXT,
            preferences TEXT,
            room_name TEXT UNIQUE,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    
    # Simple migration for cost_breakdown
    try:
        await conn.execute("ALTER TABLE conversation_summaries ADD COLUMN cost_breakdown TEXT")
    except asyncpg.exceptions.DuplicateColumnError:
        pass
        
    # Simple migration for room_name
    try:
        await conn.execute("ALTER TABLE conversation_summaries ADD COLUMN room_name TEXT UNIQUE")
    except asyncpg.exceptions.DuplicateColumnError:
        pass
        
    # Allow user_id to be null for anonymous callers
    try:
        await conn.execute("ALTER TABLE conversation_summaries ALTER COLUMN user_id DROP NOT NULL")
    except asyncpg.exceptions.PostgresError:
        pass

async def get_or_create_user(conn, phone_number: str, name: str = None) -> dict:
    user = await conn.fetchrow("SELECT * FROM users WHERE phone_number = $1", phone_number)
        
    if user:
        # If a name is provided and the existing user's name is missing or "Guest", update it.
        if name and (not user["name"] or user["name"] == "Guest"):
            await conn.execute("UPDATE users SET name = $1 WHERE id = $2", name, user["id"])
            user = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user["id"])
        return dict(user)
        
    new_user = await conn.fetchrow(
        "INSERT INTO users (phone_number, name) VALUES ($1, $2) RETURNING *", 
        phone_number, name
    )
    return dict(new_user)

async def create_appointment(conn, user_id: int, date: str, time: str) -> dict:
    # Check for double booking
    existing = await conn.fetchrow(
        "SELECT id FROM appointments WHERE date = $1 AND time = $2 AND status = 'booked'",
        date, time
    )
    if existing:
        raise ValueError("This slot was just taken, please choose another available slot.")
            
    # Insert new appointment
    new_appt = await conn.fetchrow(
        "INSERT INTO appointments (user_id, date, time) VALUES ($1, $2, $3) RETURNING *",
        user_id, date, time
    )
    return dict(new_appt)

async def get_user_appointments(conn, user_id: int) -> list[dict]:
    rows = await conn.fetch(
        "SELECT * FROM appointments WHERE user_id = $1 ORDER BY date, time",
        user_id
    )
    return [dict(r) for r in rows]

async def update_appointment(conn, appointment_id: int, user_id: int, date: str = None, time: str = None, status: str = None) -> bool:
    # First get existing to know what's changing
    existing_appt = await conn.fetchrow("SELECT * FROM appointments WHERE id = $1", appointment_id)
    if not existing_appt:
        raise ValueError("I cant find an appointment with the provided details")
    if existing_appt["user_id"] != user_id:
        raise ValueError("Appointment not found or not owned by you")
            
    new_date = date if date is not None else existing_appt["date"]
    new_time = time if time is not None else existing_appt["time"]
    new_status = status if status is not None else existing_appt["status"]
    
    if (new_date != existing_appt["date"] or new_time != existing_appt["time"] or new_status != existing_appt["status"]):
        if new_status == 'booked':
            # Check for double booking
            existing = await conn.fetchrow(
                "SELECT id FROM appointments WHERE date = $1 AND time = $2 AND status = 'booked' AND id != $3",
                new_date, new_time, appointment_id
            )
            if existing:
                raise ValueError("This slot was just taken, please choose another available slot.")
        
        await conn.execute(
            "UPDATE appointments SET date = $1, time = $2, status = $3, updated_at = CURRENT_TIMESTAMP WHERE id = $4",
            new_date, new_time, new_status, appointment_id
        )
    
    return True

import asyncpg

async def save_conversation_summary(conn, user_id: int | None, summary_text: str, appointments_json: str, preferences: str, cost_breakdown: str = None, room_name: str = None) -> int:
    try:
        row = await conn.fetchrow(
            "INSERT INTO conversation_summaries (user_id, summary_text, appointments_json, preferences, cost_breakdown, room_name) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            user_id, summary_text, appointments_json, preferences, cost_breakdown, room_name
        )
        return row['id']
    except asyncpg.exceptions.ForeignKeyViolationError:
        # Fallback if somehow a user_id is provided that doesn't exist
        row = await conn.fetchrow(
            "INSERT INTO conversation_summaries (summary_text, appointments_json, preferences, cost_breakdown, room_name) VALUES ($1, $2, $3, $4, $5) RETURNING id",
            summary_text, appointments_json, preferences, cost_breakdown, room_name
        )
        return row['id']
