import os
import requests
import re
from langgraph.graph import StateGraph
from typing import TypedDict
from dotenv import load_dotenv
import dateparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from backend.calendar_utils import create_event, get_free_slots_for_day

load_dotenv()
api_key = os.getenv("TOGETHER_API_KEY")

class AgentState(TypedDict):
    message: str
    history: list[str]

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

def is_tomorrow_query(text: str) -> bool:
    patterns = [
        r"\bwhat(?:'s| is)? the date tomorrow\b",
        r"\btomorrow(?:'s)? date\b",
        r"\bdate of tomorrow\b"
    ]
    return any(re.search(p, text.lower()) for p in patterns)

def is_today_query(text: str) -> bool:
    patterns = [
        r"\bwhat(?:'s| is|s)? the date today\b",
        r"\btoday(?:'s)? date\b",
        r"\bdate of today\b",
        r"\bwhats the date today\b"
    ]
    return any(re.search(p, text.lower()) for p in patterns)

def respond(state: AgentState) -> AgentState:
    message = state["message"]
    history = state.get("history", [])

    if is_time_query(message):
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {"message": f"The current IST time is {now.strftime('%I:%M %p on %A, %B %d')}.", "history": history}

    if is_tomorrow_query(message):
        tomorrow = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)
        return {"message": f"The date tomorrow is {tomorrow.strftime('%B %d, %Y')}.", "history": history}

    if is_today_query(message):
        today = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {"message": f"Today's date is {today.strftime('%B %d, %Y')}.", "history": history}

    convo = "\n".join([f"User: {h}" if i % 2 == 0 else f"Assistant: {h}" for i, h in enumerate(history)])
    model = "mistralai/Mistral-7B-Instruct-v0.1"
    prompt = (
        "You are a helpful and professional appointment scheduling assistant.\n"
        "Respond only as the assistant, never as the user.\n"
        "If the user says something casual (like 'hi', 'how are you'), reply politely but do not ask for appointments yet.\n"
        "If the user wants to book a meeting, ask for both date and time if missing.\n"
        "Always confirm availability before booking by checking the calendar.\n"
        "If time is already booked, ask the user to pick another slot.\n"
        "Only confirm booking if time is available.\n\n"
        + convo + f"\nUser: {message}\nAssistant:"
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
                reply_text = "I'm sorry, I didn’t understand that. Could you rephrase your request?"
        else:
            reply_text = "I'm sorry, I didn’t understand that. Could you rephrase your request?"

    except Exception as e:
        return {"message": f"❌ Error: {str(e)}", "history": history}

    parsed_date = dateparser.parse(
        message,
        settings={
            'TIMEZONE': 'Asia/Kolkata',
            'TO_TIMEZONE': 'Asia/Kolkata',
            'RETURN_AS_TIMEZONE_AWARE': True
        }
    )
    datetime_str = parsed_date.isoformat() if parsed_date else None

    if parsed_date:
        requested_start = parsed_date
        requested_end = requested_start + timedelta(hours=1)

        free_slots = get_free_slots_for_day(requested_start.date())

        for slot_start, slot_end in free_slots:
            if slot_start <= requested_start.isoformat() < slot_end:
                return {
                    "message": "That time seems available. Would you like me to book it?",
                    "datetime": datetime_str,
                    "history": history
                }

        return {
            "message": "That time is not available. Would you like to choose another slot?",
            "datetime": None,
            "history": history
        }

    return {
        "message": reply_text,
        "datetime": datetime_str,
        "history": history
    }

workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

def run_agent(message: str, history: list[str]) -> dict:
    result = agent.invoke({"message": message, "history": history})
    return {"reply": result.get("message", ""), "datetime": result.get("datetime")}