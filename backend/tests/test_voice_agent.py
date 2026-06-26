from backend.voice_agent import MykareHealthAgent
import json
import os
import pytest
import aiosqlite
from unittest.mock import MagicMock

EXPECTED_TOOLS = [
    "identify_user",
    "fetch_slots",
    "book_appointment",
    "retrieve_appointments",
    "cancel_appointment",
    "modify_appointment",
    "end_conversation",
]

def test_agent_has_all_tools():
    agent = MykareHealthAgent()
    tool_names = [t.info.name for t in agent.tools]
    for expected in EXPECTED_TOOLS:
        assert expected in tool_names, f"Missing tool: {expected}"

@pytest.mark.asyncio
async def test_identify_user_tool_calls_through_to_db():
    db_path = "test_voice_agent.sqlite"
    try:
        agent = MykareHealthAgent(db_path=db_path)
        
        # Find the identify_user tool and call it directly
        tool = next(t for t in agent.tools if t.info.name == "identify_user")
        result_json = await tool(context=MagicMock(), phone_number="+919876543210")
        result = json.loads(result_json)
        
        assert result["phone_number"] == "+919876543210"
        assert "id" in result
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

def test_agent_instructions_contain_today_date():
    from datetime import datetime
    agent = MykareHealthAgent()
    today = datetime.now().strftime("%Y-%m-%d")
    assert today in agent.instructions, f"Expected '{today}' in instructions, but got: {agent.instructions}"

@pytest.mark.asyncio
async def test_book_appointment_error_handling():
    db_path = "test_error_handling.sqlite"
    try:
        agent = MykareHealthAgent(db_path=db_path)
        
        # 1. Identify user
        identify_tool = next(t for t in agent.tools if t.info.name == "identify_user")
        user_result = json.loads(await identify_tool(context=MagicMock(), phone_number="+918888888888"))
        user_id = user_result["id"]
        
        # 2. Book an appointment
        book_tool = next(t for t in agent.tools if t.info.name == "book_appointment")
        book_res_1 = json.loads(await book_tool(context=MagicMock(), user_id=user_id, date="2030-01-01", time="10:00"))
        assert "id" in book_res_1, "First booking should succeed"
        
        # 3. Book the SAME appointment (should trigger ValueError and be caught gracefully)
        book_res_2 = json.loads(await book_tool(context=MagicMock(), user_id=user_id, date="2030-01-01", time="10:00"))
        
        assert "error" in book_res_2, "Should return a JSON object with 'error' key instead of raising an exception"
        assert book_res_2["error"] == "Slot already booked"
        assert "suggestion" in book_res_2
        assert "offer another time" in book_res_2["suggestion"]
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

@pytest.mark.asyncio
async def test_tool_sends_data_messages():
    db_path = "test_tool_messages.sqlite"
    try:
        agent = MykareHealthAgent(db_path=db_path)
        
        # Mock room and local_participant
        agent.room = MagicMock()
        agent.room.local_participant = MagicMock()
        import asyncio
        
        # publish_data is an async method
        async def mock_publish_data(data, reliable=True):
            agent.room.local_participant.published_messages.append(data)
            
        agent.room.local_participant.publish_data = mock_publish_data
        agent.room.local_participant.published_messages = []
        
        tool = next(t for t in agent.tools if t.info.name == "identify_user")
        await tool(context=MagicMock(), phone_number="+918888888888")
        
        messages = agent.room.local_participant.published_messages
        assert len(messages) >= 2, "Should publish at least 'running' and 'success/error' messages"
        
        # Decode and verify first message
        first_msg = json.loads(messages[0].decode('utf-8'))
        assert first_msg["tool"] == "identify_user"
        assert first_msg["status"] == "running"
        
        # Decode and verify second message
        last_msg = json.loads(messages[-1].decode('utf-8'))
        assert last_msg["tool"] == "identify_user"
        assert last_msg["status"] in ["success", "error"]
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
