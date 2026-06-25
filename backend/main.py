from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import aiosqlite
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
