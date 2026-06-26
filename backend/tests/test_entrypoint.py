import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from backend.voice_agent import entrypoint, MykareHealthAgent
import json

@pytest.mark.asyncio
async def test_entrypoint_initialization_does_not_crash():
    ctx = MagicMock()
    ctx.room = MagicMock()
    ctx.room.name = "test-room"
    ctx.proc = MagicMock()
    ctx.proc.userdata = {"vad": MagicMock()}
    
    # We mock connect and wait_for_participant to just return
    ctx.connect = AsyncMock()
    ctx.wait_for_participant = AsyncMock(return_value=MagicMock(identity="test-participant"))
    
    with patch('backend.voice_agent.AgentSession') as mock_session_cls, \
         patch('backend.db.init_global_pool', new_callable=AsyncMock):
         
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session
        mock_session.start = AsyncMock()
        mock_session.say = AsyncMock()
        
        try:
            await entrypoint(ctx)
        except TypeError as e:
            if "missing 1 required positional argument: 'model'" in str(e):
                pytest.fail("entrypoint crashed with missing 'model' argument in LLM.__init__")
            raise
