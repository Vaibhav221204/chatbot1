import os
import requests
import re
from langgraph.graph import StateGraph
from typing import TypedDict, List
from dotenv import load_dotenv
import dateparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from backend.calendar_utils import (
    create_event,
    get_available_slots,
    get_free_slots_for_day
)

load_dotenv()
api_key = os.getenv("TOGETHER_API_KEY")

class AgentState(TypedDict):
    message: str
    history: List[str]

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

    # 1) built-in date/time queries
    if is_time_query(message):
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {"message": f"The current IST time is {now.strftime('%I:%M %p on %A, %B %d')}.", "history": history}

    if is_tomorrow_query(message):
        tomorrow = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)
        return {"message": f"The date tomorrow is {tomorrow.strftime('%B %d, %Y')}.", "history": history}

    if is_today_query(message):
        today = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {"message": f"Today's date is {today.strftime('%B %d, %Y')}.", "history": history}

    # 2) calendar-driven “available slots” handler
    lower = message.lower()
    if any(kw in lower for kw in ["available slot", "available slots", "available time", "available times"]):
        # determine target date
        if "today" in lower:
            target = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        elif "tomorrow" in lower:
            target = (datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)).date()
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
            target = parsed.date()

        slots = get_free_slots_for_day(target)
        if not slots:
            return {
                "message": f"Sorry, I don’t see any free slots on {target.strftime('%B %d, %Y')}.",
                "history": history
            }

        times = [ datetime.fromisoformat(s[0]).strftime("%-I:%M %p") for s in slots ]
        slot_list = ", ".join(times)
        return {
            "message": (
                f"Here are your available slots on {target.strftime('%B %d, %Y')}: "
                f"{slot_list}. Which one would you like to book?"
            ),
            "history": history
        }

    # 3) fallback to history-aware LLM prompt
    convo = "\n".join(
        f"User: {h}" if i % 2 == 0 else f"Assistant: {h}"
        for i, h in enumerate(history)
    )
    model = "mistralai/Mistral-7B-Instruct-v0.1"
    prompt = (
       "You are a helpful and professional appointment scheduling assistant.\n"
       "Respond only as the assistant, never as the user.\n"
       "Continue the conversation based on the history below.\n"
       f"{convo}\n"
       f"User: {message}\nAssistant:"
    )

    try:
        response = requests.post(
            "https://api.together.xyz/inference",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={"model": model, "prompt": prompt, "max_tokens": 256, "temperature": 0.7}
        )
        data = response.json()

        # extract and filter reply_text
        if "output" in data and isinstance(data["output"], dict):
            choices = data["output"].get("choices", [])
            if choices and "text" in choices[0]:
                reply_text = choices[0]["text"].strip()
            else:
                reply_text = "⚠️ No valid response text found."
        else:
            reply_text = str(data.get("output", "⚠️ No output."))
    except Exception as e:
        return {"message": f"❌ Error: {str(e)}", "history": history}

    # strip hallucinations
    roleplay_triggers = ["User:", "Assistant:", "User 1:", "User 2:", "User says", "Assistant says"]
    for tr in roleplay_triggers:
        if tr in reply_text:
            reply_text = reply_text.split(tr)[0].strip()
            reply_text += " Could you please pick a time you'd like to book?"
            break

    # block fake bookings
    if re.search(r"\b(i can book|i have (?:scheduled|booked))\b", reply_text.lower()):
        reply_text = "That time seems available. Would you like me to book it?"

    return {"message": reply_text, "history": history}

# compile LangGraph
workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

def run_agent(message: str, history: List[str]) -> dict:
    result = agent.invoke({"message": message, "history": history})
    response_text = result.get("message", "")
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
        requested_start = parsed_date.isoformat()
        requested_end = (parsed_date + timedelta(hours=1)).isoformat()
        try:
            events = get_available_slots()
            for event in events:
                start_ = event['start'].get('dateTime', event['start'].get('date'))
                end_   = event['end'].get('dateTime',   event['end'].get('date'))
                if start_ <= requested_start < end_:
                    return {"reply": "That time is not available.", "datetime": None}
            return {"reply": "That time seems available. Would you like me to book it?", "datetime": datetime_str}
        except Exception as e:
            return {"reply": f"⚠️ Failed to check calendar availability: {str(e)}", "datetime": None}

    return {"reply": response_text, "datetime": datetime_str}
