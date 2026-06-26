"""
Manual test script for the LLM agent. Text-in/text-out, no voice.

Usage:
    Set OPENAI_API_KEY (or OPENROUTER_API_KEY + OPENAI_BASE_URL) in your environment.
    Then run:
        python -m backend.test_agent_manual
"""
import asyncio
import os
import asyncpg
from openai import AsyncOpenAI
from backend.db import init_db
from backend.agent_openrouter import SYSTEM_PROMPT, run_agent_turn

DATABASE_URL = os.getenv("DATABASE_URL")

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

    # Set up OpenAI client (works with OpenRouter too via base_url)
    client = AsyncOpenAI(
        api_key=os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    
    if not DATABASE_URL:
        print("Error: DATABASE_URL environment variable is required.")
        return

    pool = await asyncpg.create_pool(DATABASE_URL)
    
    async with pool.acquire() as conn:
        await init_db(conn)
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        print("=== Mykare Voice AI Agent (Text Mode) ===")
        print("Type your messages. Type 'quit' to exit.\n")
        
        while True:
            user_input = input("You: ").strip()
            if not user_input or user_input.lower() == "quit":
                break
            
            messages.append({"role": "user", "content": user_input})
            
            response_text, messages = await run_agent_turn(conn, messages, client)
            print(f"Agent: {response_text}\n")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
