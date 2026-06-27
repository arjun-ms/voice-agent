import os
import json
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from typing import Any

# Find and load the nearest .env file
load_dotenv(find_dotenv())


from livekit.agents import (
    Agent,
    AgentSession,
    AgentServer,
    JobContext,
    JobProcess,
    RunContext,
    function_tool,
    inference,
    cli,
    WorkerOptions,
)

from livekit.plugins import silero
from backend import tools
from backend.db import init_db, get_pool

# Configure file logging (resolve relative to project root)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log_dir = os.path.join(_project_root, "logs")
os.makedirs(log_dir, exist_ok=True)
log_filename = os.path.join(log_dir, f"voice_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# Setup logger
logger = logging.getLogger("mykare-voice-agent")
logger.setLevel(logging.INFO)

# File handler
fh = logging.FileHandler(log_filename)
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

# Also capture LiveKit logs to the file
logging.getLogger("livekit").addHandler(fh)
logging.getLogger("livekit").setLevel(logging.DEBUG)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/postgres")

# Replaced with get_pool from backend.db

def get_agent_instructions():
    today = datetime.now().strftime("%Y-%m-%d")
    return f"""You are a friendly and professional healthcare front-desk AI assistant for Mykare Health.

Today's date is: {today}. Do not allow booking appointments in the past.

Your responsibilities:
- Greet patients warmly and help them with appointment scheduling
- Identify patients by asking for their phone number (use it as unique ID)
- Extract the following from conversation: name, phone number, date, time, and intent
- Book, retrieve, modify, or cancel appointments as requested
- Confirm appointment details clearly (date, time) before and after booking
- Summarize the conversation when the patient is done

Guidelines:
- Keep responses concise and natural (1-2 sentences)
- Always confirm details before taking action
- If a slot is unavailable, suggest checking other times
- Maintain context across the full conversation
- When the conversation is complete, call end_conversation to generate a summary
"""


class MykareHealthAgent(Agent):
    room: Any
    _agent_session: Any
    session_start_time: datetime | None

    def __init__(self, db_url: str | None = None):
        super().__init__(instructions=get_agent_instructions())
        self._db_url = db_url or DATABASE_URL
        self.current_user_id: int | None = None
        self.room = None
        self._agent_session = None
        self.session_start_time = None
        self._publish_lock = asyncio.Lock()

    async def on_enter(self):
        # The system instructions already tell the agent to greet patients.
        # generate_reply() is called from the participant_connected event
        # in the entrypoint, so no chat context manipulation needed here.
        self.session_start_time = datetime.now()
        logger.info("Agent entered session")

    async def send_tool_message(self, status: str, tool_name: str, result: str | None = None):
        """Helper to send tool execution status to frontend via data channel."""
        if hasattr(self, 'room') and self.room and hasattr(self.room.local_participant, 'publish_data'):
            payload = {"status": status, "tool": tool_name}
            if result:
                payload["result"] = result
            try:
                # Use lock to prevent "another operation is in progress" from concurrent publishes
                async with self._publish_lock:
                    await self.room.local_participant.publish_data(
                        json.dumps(payload).encode('utf-8'), 
                        reliable=True
                    )
            except Exception as e:
                logger.warning(f"Could not send tool message ({tool_name} - {status}): {e}")

    @function_tool
    async def identify_user(
        self, context: RunContext, phone_number: str, name: str | None = None
    ):
        """Identify an existing user by phone number (with country code, e.g. +91) and optionally their name. Create a new one if not found."""
        logger.info(f"===> LLM calling identify_user with phone_number: '{phone_number}', name: '{name}'")
        await self.send_tool_message("running", "identify_user")
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                result = await tools.identify_user(conn, phone_number, name)
                self.current_user_id = result.get("id")
                await self.send_tool_message("success", "identify_user", "User identified successfully")
                return json.dumps(result, default=str)
        except ValueError as e:
            await self.send_tool_message("error", "identify_user", str(e))
            return json.dumps({"error": str(e), "suggestion": "Please inform the user and ask for the correct information."})
        except Exception as e:
            logger.exception("Error in identify_user:")
            await self.send_tool_message("error", "identify_user", "Internal error")
            return json.dumps({"error": "Internal error occurred while identifying user."})

    @function_tool
    async def fetch_slots(self, context: RunContext, date: str):
        """Get available appointment time slots for a given date in YYYY-MM-DD format."""
        await self.send_tool_message("running", "fetch_slots")
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                result = await tools.fetch_slots(conn, date)
                await self.send_tool_message("success", "fetch_slots", f"Found {len(result.get('slots', []))} slots")
                return json.dumps(result, default=str)
        except ValueError as e:
            await self.send_tool_message("error", "fetch_slots", str(e))
            return json.dumps({"error": str(e), "suggestion": "Please ask the user for a valid future date."})
        except Exception as e:
            logger.error(f"Error in fetch_slots: {e}")
            await self.send_tool_message("error", "fetch_slots", "Internal error")
            return json.dumps({"error": "Internal error occurred while fetching slots."})

    @function_tool
    async def book_appointment(
        self, context: RunContext, user_id: int, date: str, time: str
    ):
        """Book an appointment for a patient at a specific date (YYYY-MM-DD) and time (HH:MM 24h). The user must be identified first."""
        await self.send_tool_message("running", "book_appointment")
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                result = await tools.book_appointment(conn, user_id, date, time)
                await self.send_tool_message("success", "book_appointment", "Appointment booked")
                return json.dumps(result, default=str)
        except ValueError as e:
            await self.send_tool_message("error", "book_appointment", str(e))
            return json.dumps({"error": str(e), "suggestion": "Please inform the user that the slot is already booked or invalid, and offer another time."})
        except Exception as e:
            logger.error(f"Error in book_appointment: {e}")
            await self.send_tool_message("error", "book_appointment", "Internal error")
            return json.dumps({"error": "Internal error occurred while booking the appointment."})

    @function_tool
    async def retrieve_appointments(self, context: RunContext, user_id: int):
        """Get all appointments for a patient by their user ID."""
        await self.send_tool_message("running", "retrieve_appointments")
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                result = await tools.retrieve_appointments(conn, user_id)
                await self.send_tool_message("success", "retrieve_appointments", f"Found {len(result)} appointments")
                return json.dumps(result, default=str)
        except Exception as e:
            logger.error(f"Error in retrieve_appointments: {e}")
            await self.send_tool_message("error", "retrieve_appointments", "Internal error")
            return json.dumps({"error": "Internal error occurred while retrieving appointments."})

    @function_tool
    async def cancel_appointment(
        self, context: RunContext, appointment_id: int, user_id: int
    ):
        """Cancel an existing appointment. Requires appointment ID and user ID."""
        await self.send_tool_message("running", "cancel_appointment")
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                result = await tools.cancel_appointment(conn, appointment_id, user_id)
                await self.send_tool_message("success", "cancel_appointment", "Appointment cancelled")
                return json.dumps(result, default=str)
        except ValueError as e:
            await self.send_tool_message("error", "cancel_appointment", str(e))
            return json.dumps({"error": str(e), "suggestion": "Please inform the user."})
        except Exception as e:
            logger.error(f"Error in cancel_appointment: {e}")
            await self.send_tool_message("error", "cancel_appointment", "Internal error")
            return json.dumps({"error": "Internal error occurred while cancelling the appointment."})

    @function_tool
    async def modify_appointment(
        self,
        context: RunContext,
        appointment_id: int,
        user_id: int,
        date: str | None = None,
        time: str | None = None,
    ):
        """Modify the date or time of an existing appointment. Requires appointment ID and user ID."""
        await self.send_tool_message("running", "modify_appointment")
        try:
            pool = get_pool()
            async with pool.acquire() as conn:
                result = await tools.modify_appointment(
                    conn, appointment_id, user_id, date=date, time=time
                )
                await self.send_tool_message("success", "modify_appointment", "Appointment modified")
                return json.dumps(result, default=str)
        except ValueError as e:
            await self.send_tool_message("error", "modify_appointment", str(e))
            return json.dumps({"error": str(e), "suggestion": "Please inform the user that the modification failed because the slot is taken or invalid."})
        except Exception as e:
            logger.error(f"Error in modify_appointment: {e}")
            await self.send_tool_message("error", "modify_appointment", "Internal error")
            return json.dumps({"error": "Internal error occurred while modifying the appointment."})

    @function_tool
    async def end_conversation(self, context: RunContext, user_id: int):
        """End the conversation and generate a summary. Call this when the patient says goodbye or is done."""
        await self.send_tool_message("running", "end_conversation")
        from backend.summary import generate_summary_from_history
        import asyncio
        
        # Robustly extract chat history from the session
        history = []
        try:
            ctx = getattr(self.session, "chat_ctx", getattr(self.session, "history", None))
                
            if ctx is not None:
                messages: Any = getattr(ctx, "messages", ctx)
                if callable(messages):
                    messages = messages()
                for msg in messages:
                    role = getattr(msg, 'role', 'unknown')
                    content = getattr(msg, 'content', getattr(msg, 'text', str(msg)))
                    if isinstance(content, list):
                        content = " ".join([str(getattr(p, 'text', p)) for p in content])
                    history.append({"role": role, "text": str(content)})
        except Exception as e:
            logger.error(f"Could not extract history: {e}")
            
        cost_breakdown_json = None
        if hasattr(self, "session_start_time"):
            end_time = datetime.now()
            duration_minutes = (end_time - self.session_start_time).total_seconds() / 60.0
            stt_cost = duration_minutes * 0.0043 # deepgram cost
            tts_cost = duration_minutes * 0.015 # cartesia cost 
            llm_cost = duration_minutes * 0.001 # gemini cost
            cost_breakdown = {
                "duration_minutes": round(duration_minutes, 2),
                "stt_deepgram": f"${stt_cost:.4f}",
                "tts_cartesia": f"${tts_cost:.4f}",
                "llm_gemini": f"${llm_cost:.4f}",
                "total_cost": f"${(stt_cost + tts_cost + llm_cost):.4f}"
            }
            cost_breakdown_json = json.dumps(cost_breakdown)
                
        pool = get_pool()
        async with pool.acquire() as conn:
            room_name = getattr(self.room, "name", None) if hasattr(self, "room") else None
            result = await tools.end_conversation(
                conn, 
                user_id, 
                history, 
                summarize_fn=generate_summary_from_history,
                cost_breakdown=cost_breakdown_json,
                room_name=room_name
            )
            await self.send_tool_message("success", "end_conversation", "Conversation ended")
            
            # Schedule a disconnect after the agent finishes speaking its final goodbye
            async def delayed_disconnect():
                # Wait a moment for the LLM to process the tool return and start speaking
                await asyncio.sleep(2)
                
                try:
                    # Dynamically wait for the agent to finish speaking (become idle)
                    agent_session = getattr(self, '_agent_session', None)
                    if agent_session and hasattr(agent_session, 'wait_for_idle'):
                        await agent_session.wait_for_idle()
                    else:
                        await asyncio.sleep(8)
                except Exception as e:
                    logger.warning(f"wait_for_idle failed, falling back to sleep: {e}")
                    await asyncio.sleep(8)
                    
                if hasattr(self, 'room') and self.room:
                    logger.info("Automatically disconnecting the call as conversation ended.")
                    await self.room.disconnect()
            asyncio.create_task(delayed_disconnect())

            return json.dumps(result, default=str)


# --- LiveKit Agent Server ---
# Only set up the server when this module is run directly.

async def entrypoint(ctx: JobContext):
    try:
        from backend.db import init_global_pool
        await init_global_pool(DATABASE_URL)
        
        ctx.log_context_fields = {"room": ctx.room.name}

        session = AgentSession(
            stt=inference.STT(model="deepgram/nova-3-general"),
            llm=inference.LLM(model="google/gemini-2.5-flash"),
            tts=inference.TTS(
                model="cartesia/sonic-2",
                voice="79a125e8-cd45-4c13-8a67-188112f4dd22",
            ),
            vad=silero.VAD.load(),
        )
        logger.info("AgentSession created successfully")
        
        @session.on("user_speech_committed")
        def on_user_speech_committed(msg):
            # Check what type of message it is, usually it has a text property or it's just a string.
            text = getattr(msg, 'text', str(msg))
            logger.info(f"\n===> STT HEARD: {text}\n")

        agent = MykareHealthAgent()
        agent.room = ctx.room
        agent._agent_session = session
    except Exception as e:
        logger.error(f"Fatal error during agent initialization: {e}", exc_info=True)
        raise

    @ctx.room.on("disconnected")
    def on_disconnected(*args, **kwargs):
        import asyncio
        user_id = agent.current_user_id or 1
        logger.info(f"Room disconnected. Triggering fallback summary for user {user_id}")
        
        # Calculate cost
        cost_breakdown_json = None
        if getattr(agent, "session_start_time", None) is not None:
            end_time = datetime.now()
            duration_minutes = (end_time - agent.session_start_time).total_seconds() / 60.0
            stt_cost = duration_minutes * 0.0043
            tts_cost = duration_minutes * 0.015
            llm_cost = duration_minutes * 0.001
            cost_breakdown = {
                "duration_minutes": round(duration_minutes, 2),
                "stt_deepgram": f"${stt_cost:.4f}",
                "tts_cartesia": f"${tts_cost:.4f}",
                "llm_gemini": f"${llm_cost:.4f}",
                "total_cost": f"${(stt_cost + tts_cost + llm_cost):.4f}"
            }
            cost_breakdown_json = json.dumps(cost_breakdown)
        
        # Extract history directly from the local `session` object to avoid Agent context lookup errors
        history = []
        try:
            ctx_obj = getattr(session, "chat_ctx", getattr(session, "history", None))
            if ctx_obj is not None:
                messages: Any = getattr(ctx_obj, "messages", ctx_obj)
                if callable(messages):
                    messages = messages()
                for msg in messages:
                    role = getattr(msg, 'role', 'unknown')
                    content = getattr(msg, 'content', getattr(msg, 'text', str(msg)))
                    if isinstance(content, list):
                        content = " ".join([str(getattr(p, 'text', p)) for p in content])
                    history.append({"role": role, "text": str(content)})
        except Exception as e:
            logger.error(f"Fallback summary history extraction failed: {e}")
        
        async def run_fallback():
            from backend.summary import generate_summary_from_history
            pool = get_pool()
            async with pool.acquire() as conn:
                room_name = getattr(ctx.room, "name", None) if hasattr(ctx, "room") else None
                await tools.end_conversation(
                    conn, user_id, history, generate_summary_from_history, cost_breakdown=cost_breakdown_json, room_name=room_name
                )
        asyncio.create_task(run_fallback())

    await ctx.connect()
    
    # Wait for the user to join before starting the session
    try:
        participant = await ctx.wait_for_participant()
        logger.info(f"Participant joined: {participant.identity}")
    except RuntimeError:
        logger.warning("Room disconnected before participant could join.")
        return
    
    agent.session_start_time = datetime.now()
        
    await session.start(agent=agent, room=ctx.room)
    logger.info("Session started, generating initial greeting...")
    # Trigger the greeting - use say() for an immediate, reliable greeting
    await session.say(
        "Hello! Welcome to Mykare Health. To get started, could you please tell me your name and your phone number with the country code?",
        allow_interruptions=False
    )



if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        agent_name="mykare-voice-agent",
        entrypoint_fnc=entrypoint,
        port=int(os.getenv("PORT", 8080))
    ))
