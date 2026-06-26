"""
Manual test script for the Gemini LLM agent. Text-in/text-out, no voice.

Usage:
    Set GEMINI_API_KEY in your environment.
    Then run:
        python -m backend.test_agent_gemini
"""
import asyncio
import os
import aiosqlite
from google import genai
from backend.db import init_db
from backend.agent_gemini import get_system_prompt, get_gemini_tools, run_agent_turn

DB_PATH = os.getenv("DB_PATH", "database.sqlite")

async def main():
    # Load .env file if it exists
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key, val = parts
                        os.environ[key.strip()] = val.strip().strip('"').strip("'")

    # Set up Gemini client
    client = genai.Client()
    
    # Initialize the chat session
    # We use gemini-2.5-flash as the default model
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    config = dict(
        system_instruction=get_system_prompt(),
        tools=get_gemini_tools(),
    )

    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("PRAGMA foreign_keys = ON;")
        await init_db(conn)
        
        # We need an AsyncChat instance
        chat = client.aio.chats.create(model=model, config=config)
        
        print(f"=== Mykare Voice AI Agent (Gemini Mode: {model}) ===")
        print("Type your messages. Type 'quit' to exit.\n")
        
        while True:
            user_input = input("You: ").strip()
            if not user_input or user_input.lower() == "quit":
                break
            
            prev_len = len(chat.get_history()) if chat.get_history() else 0
            
            response_text = await run_agent_turn(conn, chat, user_input)
            
            # Print any tool calls that happened during this turn
            history = chat.get_history()
            if history:
                for msg in history[prev_len:]:
                    if msg.role == "model":
                        for part in msg.parts:
                            if part.function_call:
                                print(f"  [Tool Call] {part.function_call.name}({part.function_call.args})")
                    elif msg.role == "user" and any(p.function_response for p in msg.parts):
                        for part in msg.parts:
                            if part.function_response:
                                print(f"  [Tool Result] {part.function_response.name} -> {part.function_response.response}")
                                
            print(f"\nAgent: {response_text}\n")

if __name__ == "__main__":
    asyncio.run(main())
