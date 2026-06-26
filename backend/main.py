from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import aiosqlite
import json
import os

from backend.db import init_db

DB_PATH = os.getenv("DB_PATH", "database.sqlite")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize the database
    async with aiosqlite.connect(DB_PATH) as db:
        await init_db(db)
    yield
    # Shutdown logic (if any)

app = FastAPI(title="Mykare Voice AI Agent", lifespan=lifespan)

# Configure CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/summary/{user_phone}")
async def get_summary(user_phone: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Look up user by phone
        async with db.execute("SELECT id FROM users WHERE phone_number = ?", (user_phone,)) as cursor:
            user = await cursor.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get most recent summary for this user
        async with db.execute(
            "SELECT * FROM conversation_summaries WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
            (user["id"],)
        ) as cursor:
            summary = await cursor.fetchone()
        
        if not summary:
            raise HTTPException(status_code=404, detail="No summary found")
        
        return {
            "summary": summary["summary_text"],
            "appointments": json.loads(summary["appointments_json"]) if summary["appointments_json"] else [],
            "preferences": summary["preferences"],
            "timestamp": summary["timestamp"],
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
    
    return {
        "token": jwt,
        "room_name": room_name
    }
