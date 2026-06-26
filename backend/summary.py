import os
import json
from google import genai
from pydantic import BaseModel, Field

class SummaryResult(BaseModel):
    summary: str = Field(description="A concise summary of the conversation.")
    preferences: str = Field(description="Any user preferences mentioned during the call (e.g., likes mornings). Leave empty if none.")

async def generate_summary_from_history(history: list[dict]) -> dict:
    if not history:
        return {"summary": "No conversation occurred.", "preferences": ""}
    
    # Format the transcript
    transcript = "\n".join([f"{msg.get('role', 'unknown')}: {msg.get('text', '')}" for msg in history])
    
    prompt = f"""
    Please summarize the following healthcare front-desk conversation.
    Extract the main points discussed.
    Also identify any user preferences (e.g. prefers morning appointments).
    
    Transcript:
    {transcript}
    """
    
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': SummaryResult,
            },
        )
        
        result = json.loads(response.text)
        return result
    except Exception as e:
        return {"summary": f"Failed to generate summary: {str(e)}", "preferences": ""}
