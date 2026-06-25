import aiosqlite

async def init_db(conn: aiosqlite.Connection):
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
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    await conn.commit()

async def get_or_create_user(conn: aiosqlite.Connection, phone_number: str, name: str = None) -> dict:
    conn.row_factory = aiosqlite.Row
    async with conn.execute("SELECT * FROM users WHERE phone_number = ?", (phone_number,)) as cursor:
        user = await cursor.fetchone()
        
    if user:
        return dict(user)
        
    async with conn.execute(
        "INSERT INTO users (phone_number, name) VALUES (?, ?) RETURNING *", 
        (phone_number, name)
    ) as cursor:
        new_user = await cursor.fetchone()
        await conn.commit()
        return dict(new_user)

async def create_appointment(conn: aiosqlite.Connection, user_id: int, date: str, time: str) -> dict:
    conn.row_factory = aiosqlite.Row
    
    # Check for double booking
    async with conn.execute(
        "SELECT id FROM appointments WHERE date = ? AND time = ? AND status = 'booked'",
        (date, time)
    ) as cursor:
        existing = await cursor.fetchone()
        if existing:
            raise ValueError("Slot already booked")
            
    # Insert new appointment
    async with conn.execute(
        "INSERT INTO appointments (user_id, date, time) VALUES (?, ?, ?) RETURNING *",
        (user_id, date, time)
    ) as cursor:
        new_appt = await cursor.fetchone()
        await conn.commit()
        return dict(new_appt)

async def get_user_appointments(conn: aiosqlite.Connection, user_id: int) -> list[dict]:
    conn.row_factory = aiosqlite.Row
    async with conn.execute(
        "SELECT * FROM appointments WHERE user_id = ? ORDER BY date, time",
        (user_id,)
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

async def update_appointment(conn: aiosqlite.Connection, appointment_id: int, user_id: int, date: str = None, time: str = None, status: str = None) -> bool:
    conn.row_factory = aiosqlite.Row
    
    # First get existing to know what's changing
    async with conn.execute("SELECT * FROM appointments WHERE id = ? AND user_id = ?", (appointment_id, user_id)) as cursor:
        existing_appt = await cursor.fetchone()
        if not existing_appt:
            return False
            
    new_date = date if date is not None else existing_appt["date"]
    new_time = time if time is not None else existing_appt["time"]
    new_status = status if status is not None else existing_appt["status"]
    
    if (new_date != existing_appt["date"] or new_time != existing_appt["time"] or new_status != existing_appt["status"]):
        if new_status == 'booked':
            # Check for double booking
            async with conn.execute(
                "SELECT id FROM appointments WHERE date = ? AND time = ? AND status = 'booked' AND id != ?",
                (new_date, new_time, appointment_id)
            ) as cursor:
                existing = await cursor.fetchone()
                if existing:
                    raise ValueError("Slot already booked")
        
        await conn.execute(
            "UPDATE appointments SET date = ?, time = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_date, new_time, new_status, appointment_id)
        )
        await conn.commit()
    
    return True

async def save_conversation_summary(conn: aiosqlite.Connection, user_id: int, summary_text: str, appointments_json: str, preferences: str) -> int:
    async with conn.execute(
        "INSERT INTO conversation_summaries (user_id, summary_text, appointments_json, preferences) VALUES (?, ?, ?, ?) RETURNING id",
        (user_id, summary_text, appointments_json, preferences)
    ) as cursor:
        row = await cursor.fetchone()
        await conn.commit()
        return row[0]

