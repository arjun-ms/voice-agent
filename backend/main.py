from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import os

from backend.db import init_db, init_global_pool, close_global_pool, get_pool
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/postgres")

from pydantic import BaseModel
import uuid

class TokenRequest(BaseModel):
    participant_name: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the database
    await init_global_pool(DATABASE_URL)
    pool = get_pool()
    async with pool.acquire() as conn:
        await init_db(conn)
    yield
    # Shutdown logic
    await close_global_pool()

app = FastAPI(title="Mykare Voice AI Agent", lifespan=lifespan)

# Configure CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
@app.get("/ping")
async def ping_check():
    return {"status": "ok"}

@app.get("/api/summary/room/{room_name}")
async def get_summary(room_name: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        # Get the summary for this room
        summary = await conn.fetchrow(
            "SELECT * FROM conversation_summaries WHERE room_name = $1",
            room_name
        )
        
        if not summary:
            raise HTTPException(status_code=404, detail="No summary found")
            
        # Try to get user details if user_id exists
        user = {"name": "Guest", "phone_number": "Unknown"}
        if summary["user_id"]:
            db_user = await conn.fetchrow("SELECT id, name, phone_number FROM users WHERE id = $1", summary["user_id"])
            if db_user:
                user = {"name": db_user["name"], "phone_number": db_user["phone_number"]}
        
        cost_breakdown = None
        if "cost_breakdown" in summary.keys() and summary["cost_breakdown"]:
            cost_breakdown = json.loads(summary["cost_breakdown"])
            
        return {
            "user": user,
            "summary": summary["summary_text"],
            "appointments": json.loads(summary["appointments_json"]) if summary["appointments_json"] else [],
            "preferences": summary["preferences"],
            "timestamp": summary["timestamp"],
            "cost_breakdown": cost_breakdown
        }


# @app.get("/api/summary/latest")
# async def get_latest_summary():
#     pool = get_pool()
#     async with pool.acquire() as conn:
#         # Get the globally most recent summary
#         summary = await conn.fetchrow(
#             "SELECT * FROM conversation_summaries ORDER BY timestamp DESC LIMIT 1"
#         )
        
#         if not summary:
#             raise HTTPException(status_code=404, detail="No summary found")
            
#         cost_breakdown = None
#         if "cost_breakdown" in summary.keys() and summary["cost_breakdown"]:
#             cost_breakdown = json.loads(summary["cost_breakdown"])
        
#         return {
#             "summary": summary["summary_text"],
#             "appointments": json.loads(summary["appointments_json"]) if summary["appointments_json"] else [],
#             "preferences": summary["preferences"],
#             "timestamp": summary["timestamp"],
#             "cost_breakdown": cost_breakdown
#         }



@app.post("/token")
async def get_token(req: TokenRequest):
    # Lazy import to avoid blocking server startup on aiohttp C-extension load
    from livekit.api import AccessToken, VideoGrants

    room_name = "voice-agent-room-" + str(uuid.uuid4())[:8]
    
    grant = VideoGrants(room_join=True, room=room_name)
    
    # We allow fallbacks for local testing without valid env vars
    token = AccessToken(
        os.getenv("LIVEKIT_API_KEY", "devkey"),
        os.getenv("LIVEKIT_API_SECRET", "secret")
    )
    token.with_identity(req.participant_name)
    token.with_name(req.participant_name)
    token.with_grants(grant)
    
    jwt = token.to_jwt()
    
    from livekit import api
    lkapi = api.LiveKitAPI(
        os.getenv("LIVEKIT_URL", "ws://localhost:7880"),
        os.getenv("LIVEKIT_API_KEY", "devkey"),
        os.getenv("LIVEKIT_API_SECRET", "secret")
    )
    try:
        await lkapi.room.create_room(api.CreateRoomRequest(name=room_name, empty_timeout=10 * 60))
        await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name="mykare-voice-agent",
                room=room_name
            )
        )
    except Exception as e:
        print(f"Failed to explicitly dispatch agent: {e}")
    finally:
        await lkapi.aclose()

    
    return {
        "token": jwt,
        "room_name": room_name,
        "server_url": os.getenv("LIVEKIT_URL", "ws://localhost:7880")
    }
