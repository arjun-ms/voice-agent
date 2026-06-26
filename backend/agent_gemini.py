import json
import os
import asyncpg
from backend import tools
from google import genai
from google.genai import types

from datetime import datetime

def get_system_prompt():
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

def get_gemini_tools():
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="identify_user",
                    description="Look up or create a user by their phone number. Call this when the patient provides their phone number.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "phone_number": types.Schema(type="STRING", description="The patient's phone number"),
                            "name": types.Schema(type="STRING", description="The patient's name, if provided"),
                        },
                        required=["phone_number"],
                    )
                ),
                types.FunctionDeclaration(
                    name="fetch_slots",
                    description="Get available appointment time slots for a given date.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "date": types.Schema(type="STRING", description="The date to check slots for, in YYYY-MM-DD format"),
                        },
                        required=["date"],
                    )
                ),
                types.FunctionDeclaration(
                    name="book_appointment",
                    description="Book an appointment for a patient at a specific date and time. The user must be identified first.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "user_id": types.Schema(type="INTEGER", description="The patient's user ID (from identify_user)"),
                            "date": types.Schema(type="STRING", description="Appointment date in YYYY-MM-DD format"),
                            "time": types.Schema(type="STRING", description="Appointment time in HH:MM format"),
                        },
                        required=["user_id", "date", "time"],
                    )
                ),
                types.FunctionDeclaration(
                    name="retrieve_appointments",
                    description="Get all appointments for a patient.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "user_id": types.Schema(type="INTEGER", description="The patient's user ID"),
                        },
                        required=["user_id"],
                    )
                ),
                types.FunctionDeclaration(
                    name="cancel_appointment",
                    description="Cancel an existing appointment.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "appointment_id": types.Schema(type="INTEGER", description="The appointment ID to cancel"),
                            "user_id": types.Schema(type="INTEGER", description="The patient's user ID"),
                        },
                        required=["appointment_id", "user_id"],
                    )
                ),
                types.FunctionDeclaration(
                    name="modify_appointment",
                    description="Modify the date or time of an existing appointment.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "appointment_id": types.Schema(type="INTEGER", description="The appointment ID to modify"),
                            "user_id": types.Schema(type="INTEGER", description="The patient's user ID"),
                            "date": types.Schema(type="STRING", description="New date in YYYY-MM-DD format"),
                            "time": types.Schema(type="STRING", description="New time in HH:MM format"),
                        },
                        required=["appointment_id", "user_id"],
                    )
                ),
                types.FunctionDeclaration(
                    name="end_conversation",
                    description="End the conversation and generate a summary. Call this when the patient says goodbye or is done.",
                    parameters=types.Schema(
                        type="OBJECT",
                        properties={
                            "user_id": types.Schema(type="INTEGER", description="The patient's user ID"),
                        },
                        required=["user_id"],
                    )
                ),
            ]
        )
    ]

async def dispatch_tool_call(conn: asyncpg.Connection, tool_name: str, arguments: dict, conversation_history: list[types.Content] = None) -> str:
    """Execute a tool call and return the result as a JSON string for the LLM."""
    try:
        if tool_name == "identify_user":
            result = await tools.identify_user(conn, arguments["phone_number"], arguments.get("name"))
        elif tool_name == "fetch_slots":
            result = await tools.fetch_slots(conn, arguments["date"])
        elif tool_name == "book_appointment":
            result = await tools.book_appointment(conn, int(arguments["user_id"]), arguments["date"], arguments["time"])
        elif tool_name == "retrieve_appointments":
            result = await tools.retrieve_appointments(conn, int(arguments["user_id"]))
        elif tool_name == "cancel_appointment":
            result = await tools.cancel_appointment(conn, int(arguments["appointment_id"]), int(arguments["user_id"]))
        elif tool_name == "modify_appointment":
            result = await tools.modify_appointment(
                conn, int(arguments["appointment_id"]), int(arguments["user_id"]),
                date=arguments.get("date"), time=arguments.get("time"),
            )
        elif tool_name == "end_conversation":
            # For simplicity, convert the Gemini chat history to dictionaries for the summary tool
            history_dicts = [{"role": m.role, "content": m.parts[0].text if m.parts else ""} for m in (conversation_history or [])]
            result = await tools.end_conversation(conn, int(arguments["user_id"]), history_dicts)
        else:
            result = {"error": f"Unknown tool: {tool_name}"}
        
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": str(e)})


async def run_agent_turn(conn: asyncpg.Connection, chat: genai.chats.AsyncChat, user_message: str) -> str:
    """
    Run one agent turn using the Gemini SDK.
    
    Args:
        conn: Database connection
        chat: Active Gemini AsyncChat session
        user_message: The user's input text
    
    Returns:
        response_text - the agent's text reply
    """
    # Send the user message
    response = await chat.send_message(user_message)
    
    # Process tool calls if any
    while response.function_calls:
        tool_results = []
        for function_call in response.function_calls:
            tool_name = function_call.name
            arguments = function_call.args
            
            # Dispatch the tool
            result_json = await dispatch_tool_call(conn, tool_name, arguments, chat.get_history())
            
            # Prepare result
            tool_results.append(types.Part.from_function_response(
                name=tool_name,
                response={"result": result_json}
            ))
            
        # Send tool results back to Gemini
        response = await chat.send_message(tool_results)
        
    return response.text or ""
