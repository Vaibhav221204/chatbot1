import os, requests, re
from langgraph.graph import StateGraph
from typing import TypedDict, List, Optional
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

    # 1) built-ins
    if is_time_query(message):
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {"message": f"The current IST time is {now.strftime('%I:%M %p on %A, %B %d')}.",
                "history": history}

    if is_tomorrow_query(message):
        d = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)
        return {"message": f"The date tomorrow is {d.strftime('%B %d, %Y')}.",
                "history": history}

    if is_today_query(message):
        d = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {"message": f"Today's date is {d.strftime('%B %d, %Y')}.",
                "history": history}

    # 2) “Book an appointment” intent → ask for date/time only
    if re.search(r"\b(book|schedule)\b.*\b(appointment|meeting)\b", message.lower()):
        return {
            "message": "Sure—what date and time would you like to schedule?",
            "history": history
        }

    # 3) available‐slots handler → return list of iso timestamps
    lower = message.lower()
    if any(kw in lower for kw in ["available slot", "available slots", "available time", "available times"]):
        # choose date
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
                "message": f"Sorry, no free slots on {target.strftime('%B %d, %Y')}.",
                "history": history,
                "slots": []
            }

        # build iso list + human list
        iso_list = [ s[0] for s in slots ]
        times = [
            datetime.fromisoformat(s[0]).astimezone(ZoneInfo("Asia/Kolkata")).strftime("%-I:%M %p")
            for s in slots
        ]
        text = ", ".join(times)
        return {
            "message": (
                f"Here are your available slots on {target.strftime('%B %d, %Y')}: "
                f"{text}. Which one would you like to book?"
            ),
            "history": history,
            "slots": iso_list
        }

    # 4) fallback to LLM with full history
    convo = "\n".join(
        f"User: {h}" if i % 2 == 0 else f"Assistant: {h}"
        for i, h in enumerate(history)
    )
    prompt = (
       "You are a helpful appointment scheduling assistant.\n"
       "Respond only as the assistant, never as the user.\n"
       "Continue the conversation based on the history below.\n"
       f"{convo}\nUser: {message}\nAssistant:"
    )

    try:
        r = requests.post(
            "https://api.together.xyz/inference",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "mistralai/Mistral-7B-Instruct-v0.1",
                  "prompt": prompt,
                  "max_tokens": 256,
                  "temperature": 0.7}
        )
        data = r.json()
        choices = (data.get("output", {}) or {}).get("choices", [])
        reply_text = choices[0].get("text","").strip() if choices else "⚠️ No reply."
    except Exception as e:
        reply_text = f"❌ Error: {e}"

    # strip out any LLM roleplay
    for tr in ["User:", "Assistant:", "User 1:","User 2:","User says","Assistant says"]:
        if tr in reply_text:
            reply_text = reply_text.split(tr)[0].strip() + " Could you pick a time?"
            break
    # block fake bookings
    if re.search(r"\b(i can book|i have (?:scheduled|booked))\b", reply_text.lower()):
        reply_text = "That time seems available. Would you like me to book it?"

    return {"message": reply_text, "history": history}

# compile graph
workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

def run_agent(message: str, history: List[str]) -> dict:
    result = agent.invoke({"message": message, "history": history})
    return {
        "reply": result.get("message",""),
        "datetime": result.get("datetime"),
        "slots": result.get("slots", [])
    }
