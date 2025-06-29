import os
import requests
from langgraph.graph import StateGraph
from typing import TypedDict
from dotenv import load_dotenv
import dateparser
from datetime import datetime, timedelta
from backend.calendar_utils import create_event, get_available_slots 

load_dotenv()
api_key = os.getenv("TOGETHER_API_KEY")


class AgentState(TypedDict):
    message: str


def respond(state: AgentState) -> AgentState:
    message = state["message"]
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

# LangGraph setup
workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

# Final callable function
def run_agent(message: str) -> dict:
    result = agent.invoke({"message": message})
    response_text = result.get("message", "")
    parsed_date = dateparser.parse(message)
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
                        "reply": f"You're not available at that time. Would you like to choose another slot?",
                        "datetime": None
                    }

            
            return {
                "reply": f"You're available at that time. Should I go ahead and book it?",
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
