from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncpg
import json
import os

from backend.db import init_db, init_global_pool, close_global_pool, get_pool
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/postgres")

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

@app.get("/api/summary/{phone_number}")
async def get_summary(phone_number: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        # Get user
        user = await conn.fetchrow("SELECT id FROM users WHERE phone_number = $1", phone_number)
            
        if not user:
            raise HTTPException(status_code=404, detail="No summary found")
            
        # Get the most recent summary for this user
        summary = await conn.fetchrow(
            "SELECT * FROM conversation_summaries WHERE user_id = $1 ORDER BY timestamp DESC LIMIT 1",
            user["id"]
        )
        
        if not summary:
            raise HTTPException(status_code=404, detail="No summary found")
        
        cost_breakdown = None
        if "cost_breakdown" in summary.keys() and summary["cost_breakdown"]:
            cost_breakdown = json.loads(summary["cost_breakdown"])
            
        return {
            "summary": summary["summary_text"],
            "appointments": json.loads(summary["appointments_json"]) if summary["appointments_json"] else [],
            "preferences": summary["preferences"],
            "timestamp": summary["timestamp"],
            "cost_breakdown": cost_breakdown
        }

@app.get("/api/summary/latest")
async def get_latest_summary():
    pool = get_pool()
    async with pool.acquire() as conn:
        # Get the globally most recent summary
        summary = await conn.fetchrow(
            "SELECT * FROM conversation_summaries ORDER BY timestamp DESC LIMIT 1"
        )
        
        if not summary:
            raise HTTPException(status_code=404, detail="No summary found")
            
        cost_breakdown = None
        if "cost_breakdown" in summary.keys() and summary["cost_breakdown"]:
            cost_breakdown = json.loads(summary["cost_breakdown"])
        
        return {
            "summary": summary["summary_text"],
            "appointments": json.loads(summary["appointments_json"]) if summary["appointments_json"] else [],
            "preferences": summary["preferences"],
            "timestamp": summary["timestamp"],
            "cost_breakdown": cost_breakdown
        }

from pydantic import BaseModel
import uuid
from livekit.api import AccessToken, VideoGrants

class TokenRequest(BaseModel):
    participant_name: str

@app.post("/token")
async def get_token(req: TokenRequest):
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
        await lkapi.room.create_room(api.CreateRoomRequest(name=room_name))
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
