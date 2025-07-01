import os
import requests
import re
from langgraph.graph import StateGraph
from typing import TypedDict, List
from dotenv import load_dotenv
import dateparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from backend.calendar_utils import get_available_slots, get_free_slots_for_day

load_dotenv()
api_key = os.getenv("TOGETHER_API_KEY")

class AgentState(TypedDict):
    message: str
    history: List[str]
    slots: List[str]  # we’ll inject this

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

    # --- built-ins for time/date ---
    if is_time_query(message):
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {"message": f"The current IST time is {now.strftime('%I:%M %p on %A, %B %d')}.", "history": history}
    if is_tomorrow_query(message):
        tomorrow = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)
        return {"message": f"The date tomorrow is {tomorrow.strftime('%B %d, %Y')}.", "history": history}
    if is_today_query(message):
        today = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {"message": f"Today's date is {today.strftime('%B %d, %Y')}.", "history": history}

    # --- calendar-based available-slots handler ---
    lower = message.lower()
    if "available slot" in lower or "available time" in lower:
        # determine the date the user means
        if "today" in lower:
            target_date = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        elif "tomorrow" in lower:
            target_date = (datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)).date()
        else:
            parsed = dateparser.parse(
                message,
                settings={
                    "TIMEZONE": "Asia/Kolkata",
                    "TO_TIMEZONE": "Asia/Kolkata",
                    "RETURN_AS_TIMEZONE_AWARE": True
                }
            )
            if not parsed:
                return {"message": "Sure—what date are you interested in?", "history": history}
            target_date = parsed.date()

        free = get_free_slots_for_day(target_date)
        if not free:
            return {
                "message": f"Sorry, I don’t see any free slots on {target_date.strftime('%B %d, %Y')}.",
                "history": history,
                "slots": []
            }

        iso_list = [slot[0] for slot in free]
        times = [
            datetime.fromisoformat(slot[0])
            .astimezone(ZoneInfo("Asia/Kolkata"))
            .strftime("%-I:%M %p")
            for slot in free
        ]
        times_str = ", ".join(times)
        return {
            "message": (
                f"Here are your available slots on {target_date.strftime('%B %d, %Y')}: "
                f"{times_str}. Which one would you like to book?"
            ),
            "history": history,
            "slots": iso_list
        }

    # --- your ORIGINAL prompt to the LLM ---
    prompt = (
        "You are a helpful and professional appointment scheduling assistant.\n"
        "Respond only as the assistant, never as the user.\n"
        "If the user says something casual (like 'hi', 'how are you'), reply politely but do not ask for appointments yet.\n"
        "If the user wants to book a meeting, ask for both date and time if missing.\n"
        "Always confirm availability before booking by checking the calendar.\n"
        "If time is already booked, ask the user to pick another slot.\n"
        "do not ask the user which service or purpose you need this appointment for.\n"
        "Only confirm booking if time is available.\n"
        f"\nUser: {message}\nAssistant:"
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
                "max_tokens": 256,
                "temperature": 0.7
            }
        )
        data = response.json()
        choices = data.get("output", {}).get("choices", [])
        reply = choices[0].get("text", "").strip() if choices else "⚠️ No valid response."
    except Exception as e:
        reply = f"❌ Error: {e}"

    # strip any hallucinated roleplay
    for trigger in ["User:", "Assistant:", "User says", "Assistant says"]:
        if trigger in reply:
            reply = reply.split(trigger)[0].strip()
            break

    return {"message": reply, "history": history}

# compile graph
workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

def run_agent(message: str, history: List[str]) -> dict:
    out = agent.invoke({"message": message, "history": history})
    slots = out.get("slots", [])
    reply = out.get("message", "")

    # detect explicit date/time for booking prompt
    parsed = dateparser.parse(
        message,
        settings={
            'TIMEZONE': 'Asia/Kolkata',
            'TO_TIMEZONE': 'Asia/Kolkata',
            'RETURN_AS_TIMEZONE_AWARE': True
        }
    )
    datetime_str = parsed.isoformat() if parsed else None

    if parsed:
        start = datetime_str
        end = (parsed + timedelta(hours=1)).isoformat()
        for ev in get_available_slots():
            ev_start = ev["start"].get("dateTime", ev["start"].get("date"))
            ev_end = ev["end"].get("dateTime", ev["end"].get("date"))
            if ev_start <= start < ev_end:
                return {"reply": "That time is not available.", "datetime": None, "slots": slots}
        return {
            "reply": "That time seems available. Would you like me to book it?",
            "datetime": datetime_str,
            "slots": slots
        }

    return {"reply": reply, "datetime": datetime_str, "slots": slots}
