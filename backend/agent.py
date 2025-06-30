import os
import requests
import re
from langgraph.graph import StateGraph
from typing import TypedDict
from dotenv import load_dotenv
import dateparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from backend.calendar_utils import create_event, get_available_slots 

load_dotenv()
api_key = os.getenv("TOGETHER_API_KEY")

class AgentState(TypedDict):
    message: str

def is_time_query(text: str) -> bool:
    patterns = [
        r"\bwhat(?:'s| is)? the time\b",
        r"\bcurrent time\b",
        r"\btell me the time\b",
        r"\btime now\b",
        r"\bwhat time is it\b",
        r"\bdo you know the time\b"
    ]
    return any(re.search(p, text.lower()) for p in patterns)

def respond(state: AgentState) -> AgentState:
    message = state["message"]

    if is_time_query(message):
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {
            "message": f"The current IST time is {now.strftime('%I:%M %p on %A, %B %d')}."
        }

    model = "mistralai/Mistral-7B-Instruct-v0.1"
    prompt = (
        "You are an appointment booking assistant. Stay focused only on scheduling meetings. "
        "Do not roleplay both user and assistant. Only respond as the assistant.\n"
        "Ask for date and time if not provided. Before confirming a meeting, check the calendar for conflicts.\n"
        "If the time is already booked, ask the user to choose another slot. Otherwise, confirm and ask if you'd like to book it.\n"
        "If the user asks for available time slots, use calendar data and respond accordingly.\n\n"
        f"User: {message}\nAssistant:"
    )

    try:
        response = requests.post(
            "https://api.together.xyz/inference",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "prompt": prompt,
                "max_tokens": 256,
                "temperature": 0.7
            }
        )

        data = response.json()
        if "output" in data and isinstance(data["output"], dict):
            choices = data["output"].get("choices", [])
            if choices and "text" in choices[0]:
                reply_text = choices[0]["text"].strip()
            else:
                reply_text = "⚠️ No valid response text found."
        else:
            reply_text = str(data.get("output", "⚠️ No output."))

        return {"message": reply_text}

    except Exception as e:
        return {"message": f"❌ Error: {str(e)}"}

workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

def run_agent(message: str) -> dict:
    result = agent.invoke({"message": message})
    response_text = result.get("message", "")
    parsed_date = dateparser.parse(
        message,
        settings={
            'TIMEZONE': 'Asia/Kolkata',
            'TO_TIMEZONE': 'UTC',
            'RETURN_AS_TIMEZONE_AWARE': True
        }
    )
    datetime_str = parsed_date.isoformat() if parsed_date else None

    if parsed_date:
        requested_start = parsed_date.isoformat()
        requested_end = (parsed_date + timedelta(hours=1)).isoformat()

        try:
            events = get_available_slots()
            for event in events:
                event_start = event['start'].get('dateTime', event['start'].get('date'))
                event_end = event['end'].get('dateTime', event['end'].get('date'))

                if event_start <= requested_start < event_end:
                    return {
                        "reply": "That time is not available. Would you like me to book it?",
                        "datetime": None
                    }

            return {
                "reply": "That time seems available (based on IST). Would you like me to book it?",
                "datetime": datetime_str
            }

        except Exception as e:
            return {
                "reply": f"⚠️ Failed to check calendar availability: {str(e)}",
                "datetime": None
            }

    return {
        "reply": response_text,
        "datetime": datetime_str
    }