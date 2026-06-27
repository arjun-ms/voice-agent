import pytest
import pytest_asyncio
import os
import asyncio
from backend.db import init_global_pool, close_global_pool, get_pool, init_db

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://localhost:5432/postgres")

@pytest_asyncio.fixture(scope="session", autouse=True)
async def global_test_db():
    if "localhost" in TEST_DATABASE_URL or "127.0.0.1" in TEST_DATABASE_URL:
        # Provide a mock pool for tests when DB is not available
        db_store = {
            "users": {},
            "appointments": {},
            "conversation_summaries": {}
        }

        class MockConnection:
            def __init__(self, db_store):
                self.db_store = db_store

            async def execute(self, query, *args):
                q = query.lower()
                if "delete from" in q:
                    self.db_store["users"].clear()
                    self.db_store["appointments"].clear()
                    self.db_store["conversation_summaries"].clear()
                elif "update appointments" in q:
                    # UPDATE appointments SET date = $1, time = $2, status = $3, updated_at = CURRENT_TIMESTAMP WHERE id = $4
                    date, time, status, appt_id = args
                    appt_id = int(appt_id)
                    if appt_id in self.db_store["appointments"]:
                        self.db_store["appointments"][appt_id].update({
                            "date": date,
                            "time": time,
                            "status": status
                        })
                return "UPDATE 1"

            async def fetchrow(self, query, *args):
                q = query.lower()
                if "from users where phone_number" in q:
                    phone = args[0]
                    for u in self.db_store["users"].values():
                        if u["phone_number"] == phone:
                            return u
                    return None
                elif "insert into users" in q:
                    phone, name = args
                    uid = len(self.db_store["users"]) + 1
                    user = {"id": uid, "phone_number": phone, "name": name}
                    self.db_store["users"][uid] = user
                    return user
                elif "from appointments where date = $1 and time = $2" in q:
                    date, time = args[:2]
                    exclude_id = args[2] if len(args) > 2 else None
                    for appt in self.db_store["appointments"].values():
                        if appt["date"] == date and appt["time"] == time and appt["status"] == "booked":
                            if exclude_id is None or appt["id"] != int(exclude_id):
                                return {"id": appt["id"]}
                    return None
                elif "insert into appointments" in q:
                    user_id, date, time = args
                    aid = len(self.db_store["appointments"]) + 1
                    appt = {"id": aid, "user_id": int(user_id), "date": date, "time": time, "status": "booked"}
                    self.db_store["appointments"][aid] = appt
                    return appt
                elif "from appointments where id" in q:
                    aid = int(args[0])
                    return self.db_store["appointments"].get(aid)
                elif "insert into conversation_summaries" in q:
                    user_id, summary_text, appointments_json, preferences = args[:4]
                    if int(user_id) not in self.db_store["users"]:
                        import asyncpg
                        raise asyncpg.exceptions.ForeignKeyViolationError("violates foreign key constraint")
                        
                    cost_breakdown = args[4] if len(args) > 4 else None
                    cid = len(self.db_store["conversation_summaries"]) + 1
                    summary = {
                        "id": cid,
                        "user_id": int(user_id),
                        "summary_text": summary_text,
                        "appointments_json": appointments_json,
                        "preferences": preferences,
                        "cost_breakdown": cost_breakdown,
                        "timestamp": "2026-06-27 12:00:00"
                    }
                    self.db_store["conversation_summaries"][cid] = summary
                    return {"id": cid}
                elif "from conversation_summaries where id" in q:
                    cid = int(args[0])
                    return self.db_store["conversation_summaries"].get(cid)
                elif "from conversation_summaries where user_id" in q:
                    user_id = int(args[0])
                    user_sums = [s for s in self.db_store["conversation_summaries"].values() if s["user_id"] == user_id]
                    if user_sums:
                        return user_sums[-1]
                    return None
                elif "from conversation_summaries order by timestamp" in q:
                    all_sums = list(self.db_store["conversation_summaries"].values())
                    if all_sums:
                        return all_sums[-1]
                    return None
                return None

            async def fetch(self, query, *args):
                q = query.lower()
                if "information_schema.tables" in q:
                    return [{"table_name": "users"}, {"table_name": "appointments"}, {"table_name": "conversation_summaries"}]
                elif "from appointments where date = $1" in q:
                    date = args[0]
                    res = []
                    for appt in self.db_store["appointments"].values():
                        if appt["date"] == date and appt["status"] == "booked":
                            res.append(appt)
                    return res
                elif "from appointments where user_id" in q:
                    user_id = int(args[0])
                    return [a for a in self.db_store["appointments"].values() if a["user_id"] == user_id]
                return []

        class MockPool:
            def acquire(self):
                class ContextManager:
                    async def __aenter__(self):
                        return MockConnection(db_store)
                    async def __aexit__(self, exc_type, exc, tb):
                        pass
                return ContextManager()

            async def execute(self, query, *args):
                conn = MockConnection(db_store)
                await conn.execute(query, *args)

            async def fetchrow(self, query, *args):
                conn = MockConnection(db_store)
                return await conn.fetchrow(query, *args)

            async def fetch(self, query, *args):
                conn = MockConnection(db_store)
                return await conn.fetch(query, *args)

            async def close(self):
                pass
        
        import backend.db
        backend.db._global_pool = MockPool()
        yield backend.db._global_pool
        return
        
    await init_global_pool(TEST_DATABASE_URL)
    pool = get_pool()
    # Initialize schema before any tests run
    async with pool.acquire() as conn:
        await init_db(conn)
    
    yield pool
    
    await close_global_pool()
    
@pytest_asyncio.fixture
async def db():
    pool = get_pool()
    await pool.execute("DELETE FROM conversation_summaries; DELETE FROM appointments; DELETE FROM users;")
    async with pool.acquire() as conn:
        yield conn
