
import os
import requests
import json
from langgraph.graph import StateGraph
from typing import TypedDict
from dotenv import load_dotenv
import dateparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from backend.calendar_utils import create_event, get_available_slots, get_free_slots_for_day

load_dotenv()
api_key = os.getenv("TOGETHER_API_KEY")

class AgentState(TypedDict):
    message: str

def respond(state: AgentState) -> AgentState:
    message = state["message"]

    # Step 1: Use LLM to extract intent and datetime (in ISO format)
    prompt = (
        "You are a scheduling assistant. Analyze the user's message and extract their intent."
        "Return JSON with two fields:"
        "1. intent: one of 'check_slots', 'book_meeting', or 'unknown'"
        "2. datetime: the requested time in ISO 8601 format if mentioned, else null"
        f"User: {message}"
        "JSON:"
    )

    try:
        response = requests.post(
            "https://api.together.xyz/inference",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/Mistral-7B-Instruct-v0.1",
                "prompt": prompt,
                "max_tokens": 200,
                "temperature": 0.3
            }
        )

        data = response.json()
        parsed = json.loads(data.get("output", "{}"))
        intent = parsed.get("intent", "unknown")
        datetime_str = parsed.get("datetime")

        # Step 2: Route based on intent
        if intent == "check_slots":
            if not datetime_str:
                return {"message": "Sure, for which day should I check availability?"}

            target = datetime.fromisoformat(datetime_str).astimezone(ZoneInfo("Asia/Kolkata"))
            local_day = target.strftime('%A, %B %d')
            free_slots = get_free_slots_for_day(target.date())

            if not free_slots:
                return {"message": f"I'm fully booked on {local_day}."}

            formatted = "\n".join([f"• {datetime.fromisoformat(start).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p')} – {datetime.fromisoformat(end).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p')}" for start, end in free_slots])
            return {
                "message": f"Here are my available slots on {local_day}:\n{formatted}\nWould you like to book one?"
            }

        elif intent == "book_meeting":
            if not datetime_str:
                return {"message": "What time would you like to book the meeting?"}

            requested_start = datetime.fromisoformat(datetime_str)
            requested_end = requested_start + timedelta(hours=1)

            events = get_available_slots()
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                if start <= requested_start.isoformat() < end:
                    return {"message": "That time is not available. Would you like to choose another slot?"}

            ist_time = requested_start.astimezone(ZoneInfo("Asia/Kolkata"))
            return {
                "message": f"That time seems available ({ist_time.strftime('%B %d at %I:%M %p')}). Should I go ahead and book it?",
                "datetime": requested_start.isoformat()
            }

        return {"message": "I'm not sure what you're asking. Can you clarify?"}

    except Exception as e:
     return {"message": f"❌ Error: {str(e)}"}

workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

def run_agent(message: str) -> dict:
    result = agent.invoke({"message": message})
    return {
        "reply": result.get("message", ""),
        "datetime": result.get("datetime", None)
    }
