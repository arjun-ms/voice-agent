import aiosqlite
import os
import re

_global_pool = None

class SQLiteAdapter:
    def __init__(self, conn):
        self.conn = conn

    def _convert_query(self, query):
        # Convert Postgres $1, $2, etc. to SQLite ?
        return re.sub(r'\$\d+', '?', query)

    async def execute(self, query, *args):
        await self.conn.execute(self._convert_query(query), args)
        await self.conn.commit()

    async def fetchrow(self, query, *args):
        async with self.conn.execute(self._convert_query(query), args) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def fetch(self, query, *args):
        async with self.conn.execute(self._convert_query(query), args) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

class DummyPool:
    def __init__(self, adapter):
        self.adapter = adapter

    def acquire(self):
        class ContextManager:
            def __init__(self, adapter):
                self.adapter = adapter
            async def __aenter__(self):
                return self.adapter
            async def __aexit__(self, exc_type, exc, tb):
                pass
        return ContextManager(self.adapter)

    async def close(self):
        await self.adapter.conn.close()

async def init_global_pool(dsn: str = None):
    global _global_pool
    if _global_pool is None:
        db_path = "database.sqlite"
        if os.path.exists("backend/database.sqlite"):
            db_path = "backend/database.sqlite"
        elif os.path.exists("../database.sqlite"):
            db_path = "../database.sqlite"
            
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.commit()
        _global_pool = DummyPool(SQLiteAdapter(conn))
    return _global_pool

def get_pool():
    global _global_pool
    if _global_pool is None:
        raise RuntimeError("Global pool is not initialized")
    return _global_pool

async def close_global_pool():
    global _global_pool
    if _global_pool is not None:
        await _global_pool.close()
        _global_pool = None

async def init_db(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            summary_text TEXT NOT NULL,
            appointments_json TEXT,
            preferences TEXT,
            cost_breakdown TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

async def get_or_create_user(conn, phone_number: str, name: str = None) -> dict:
    user = await conn.fetchrow("SELECT * FROM users WHERE phone_number = $1", phone_number)
        
    if user:
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
    return rows

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

async def save_conversation_summary(conn, user_id: int, summary_text: str, appointments_json: str, preferences: str, cost_breakdown: str = None) -> int:
    row = await conn.fetchrow(
        "INSERT INTO conversation_summaries (user_id, summary_text, appointments_json, preferences, cost_breakdown) VALUES ($1, $2, $3, $4, $5) RETURNING id",
        user_id, summary_text, appointments_json, preferences, cost_breakdown
    )
    return row['id']
