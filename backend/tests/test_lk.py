import asyncio
import os
from livekit import api
from livekit import rtc
from dotenv import load_dotenv

load_dotenv()

async def main():
    room_name = "test-room"
    
    token = api.AccessToken(
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET")
    )
    token.with_identity("test-client")
    token.with_grants(api.VideoGrants(room_join=True, room=room_name))
    jwt = token.to_jwt()
    
    print(f"Connecting to {os.getenv('LIVEKIT_URL')}")
    room = rtc.Room()
    try:
        await room.connect(os.getenv("LIVEKIT_URL"), jwt)
        print("Connected successfully!")
        await room.disconnect()
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(main())
