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
    # note: we will inject "slots" in the response

def is_time_query(text: str) -> bool:
    patterns = [ r"\bwhat(?:'s| is)? the time\b", r"\bcurrent time\b", r"\btime now\b" ]
    return any(re.search(p, text.lower()) for p in patterns)

def is_tomorrow_query(text: str) -> bool:
    patterns = [ r"\btomorrow(?:'s)? date\b", r"\bdate of tomorrow\b" ]
    return any(re.search(p, text.lower()) for p in patterns)

def is_today_query(text: str) -> bool:
    patterns = [ r"\btoday(?:'s)? date\b", r"\bdate of today\b", r"\bwhats the date today\b" ]
    return any(re.search(p, text.lower()) for p in patterns)

def respond(state: AgentState) -> AgentState:
    message = state["message"]
    history = state.get("history", [])

    # 1) Quick date/time handlers
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

    # 2) Calendar‐driven “available slots” block
    lower = message.lower()
    if any(kw in lower for kw in ["available slot", "available time"]):
        # pick date
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
            return {"message": f"Sorry, no free slots on {target.strftime('%B %d, %Y')}.",
                    "history": history, "slots": []}

        # build human list + raw ISO list
        iso_list = [s[0] for s in slots]
        times = [datetime.fromisoformat(s[0])
                 .astimezone(ZoneInfo("Asia/Kolkata"))
                 .strftime("%-I:%M %p") for s in slots]
        text = ", ".join(times)
        return {
            "message": f"Here are your available slots on {target.strftime('%B %d, %Y')}: {text}. Which one would you like to book?",
            "history": history,
            "slots": iso_list
        }

    # 3) Fallback to LLM with conversation history
    convo = "\n".join(
        f"{'User' if i % 2 == 0 else 'Assistant'}: {h}"
        for i, h in enumerate(history)
    )
    prompt = (
        "You are a helpful appointment scheduling assistant.\n"
        "Only respond as the assistant.\n"
        "Continue the dialogue below:\n"
        f"{convo}\nUser: {message}\nAssistant:"
    )
    try:
        r = requests.post(
            "https://api.together.xyz/inference",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "mistralai/Mistral-7B-Instruct-v0.1",
                  "prompt": prompt,
                  "max_tokens": 256,
                  "temperature": 0.7}
        )
        data = r.json()
        choices = (data.get("output", {}) or {}).get("choices", [])
        reply = choices[0].get("text", "").strip() if choices else "⚠️ No reply."
    except Exception as e:
        reply = f"❌ Error: {e}"
    # strip any rogue roleplay
    for tr in ["User:", "Assistant:", "User 1:", "Assistant says"]:
        if tr in reply:
            reply = reply.split(tr)[0].strip()
            break
    return {"message": reply, "history": history}

# compile LangGraph
workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

def run_agent(message: str, history: List[str]) -> dict:
    out = agent.invoke({"message": message, "history": history})
    # pass through any slots
    reply = out.get("message", "")
    slots = out.get("slots", [])
    # detect a parsed date for booking proposal
    parsed = dateparser.parse(
        message,
        settings={'TIMEZONE': 'Asia/Kolkata','TO_TIMEZONE': 'Asia/Kolkata','RETURN_AS_TIMEZONE_AWARE': True}
    )
    dt = parsed.isoformat() if parsed else None
    # check availability when date is explicit
    if parsed:
        start = parsed.isoformat()
        end = (parsed + timedelta(hours=1)).isoformat()
        for ev in get_available_slots():
            st_, en_ = ev['start'].get('dateTime', ev['start'].get('date')), ev['end'].get('dateTime', ev['end'].get('date'))
            if st_ <= start < en_:
                return {"reply": "That time is not available.", "datetime": None, "slots": slots}
        return {"reply": "That time seems available. Would you like me to book it?", "datetime": dt, "slots": slots}

    return {"reply": reply, "datetime": dt, "slots": slots}
