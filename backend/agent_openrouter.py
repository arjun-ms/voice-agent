import json
import asyncpg
from backend import tools

SYSTEM_PROMPT = """You are a friendly and professional healthcare front-desk AI assistant for Mykare Health.

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

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "identify_user",
            "description": "Look up or create a user by their phone number. Call this when the patient provides their phone number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone_number": {"type": "string", "description": "The patient's phone number"},
                    "name": {"type": "string", "description": "The patient's name, if provided"},
                },
                "required": ["phone_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_slots",
            "description": "Get available appointment time slots for a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "The date to check slots for, in YYYY-MM-DD format"},
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment for a patient at a specific date and time. The user must be identified first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "The patient's user ID (from identify_user)"},
                    "date": {"type": "string", "description": "Appointment date in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "Appointment time in HH:MM format"},
                },
                "required": ["user_id", "date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_appointments",
            "description": "Get all appointments for a patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "The patient's user ID"},
                },
                "required": ["user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer", "description": "The appointment ID to cancel"},
                    "user_id": {"type": "integer", "description": "The patient's user ID"},
                },
                "required": ["appointment_id", "user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_appointment",
            "description": "Modify the date or time of an existing appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "integer", "description": "The appointment ID to modify"},
                    "user_id": {"type": "integer", "description": "The patient's user ID"},
                    "date": {"type": "string", "description": "New date in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "New time in HH:MM format"},
                },
                "required": ["appointment_id", "user_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_conversation",
            "description": "End the conversation and generate a summary. Call this when the patient says goodbye or is done.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "The patient's user ID"},
                },
                "required": ["user_id"],
            },
        },
    },
]


async def dispatch_tool_call(conn: asyncpg.Connection, tool_name: str, arguments: dict, conversation_history: list[dict] = None) -> str:
    """Execute a tool call and return the result as a JSON string for the LLM."""
    try:
        if tool_name == "identify_user":
            result = await tools.identify_user(conn, arguments["phone_number"], arguments.get("name"))
        elif tool_name == "fetch_slots":
            result = await tools.fetch_slots(conn, arguments["date"])
        elif tool_name == "book_appointment":
            result = await tools.book_appointment(conn, arguments["user_id"], arguments["date"], arguments["time"])
        elif tool_name == "retrieve_appointments":
            result = await tools.retrieve_appointments(conn, arguments["user_id"])
        elif tool_name == "cancel_appointment":
            result = await tools.cancel_appointment(conn, arguments["appointment_id"], arguments["user_id"])
        elif tool_name == "modify_appointment":
            result = await tools.modify_appointment(
                conn, arguments["appointment_id"], arguments["user_id"],
                date=arguments.get("date"), time=arguments.get("time"),
            )
        elif tool_name == "end_conversation":
            result = await tools.end_conversation(conn, arguments["user_id"], conversation_history or [])
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
        
        return json.dumps(result, default=str)
    except ValueError as e:
        return json.dumps({"error": str(e)})


async def run_agent_turn(conn: asyncpg.Connection, messages: list[dict], llm_client) -> tuple[str, list[dict]]:
    """
    Run one agent turn: send messages to LLM, handle any tool calls, return final response.
    
    Args:
        conn: Database connection
        messages: Full conversation history (including system prompt)
        llm_client: An OpenAI-compatible async client
    
    Returns:
        (response_text, updated_messages) - the agent's text reply and the updated message list
    """
    import os
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    
    while True:
        response = await llm_client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
        )
        
        assistant_message = response.choices[0].message
        messages.append(assistant_message.model_dump(exclude_none=True))
        
        # If no tool calls, we're done - return the text response
        if not assistant_message.tool_calls:
            return assistant_message.content or "", messages
        
        # Process each tool call
        for tool_call in assistant_message.tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            result_json = await dispatch_tool_call(conn, tool_name, arguments, messages)
            
            # Append tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_json,
            })
