import os, requests, re
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

def is_time_query(text: str) -> bool:
    return bool(re.search(r"\bwhat(?:'s| is)? the time\b|\bcurrent time\b", text.lower()))

def is_tomorrow_query(text: str) -> bool:
    return bool(re.search(r"\btomorrow(?:'s)? date\b", text.lower()))

def is_today_query(text: str) -> bool:
    return bool(re.search(r"\btoday(?:'s)? date\b|\bdate of today\b", text.lower()))

def respond(state: AgentState) -> AgentState:
    msg = state["message"]
    hist = state.get("history", [])

    # 1) Time/date queries
    if is_time_query(msg):
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {"message": f"The current IST time is {now.strftime('%I:%M %p on %A, %B %d')}.", "history": hist}
    if is_tomorrow_query(msg):
        d = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)
        return {"message": f"The date tomorrow is {d.strftime('%B %d, %Y')}.", "history": hist}
    if is_today_query(msg):
        d = datetime.now(ZoneInfo("Asia/Kolkata"))
        return {"message": f"Today's date is {d.strftime('%B %d, %Y')}.", "history": hist}

    # 2) Available-slots handler
    lower = msg.lower()
    if "available slot" in lower or "available time" in lower:
        if "today" in lower:
            target = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        elif "tomorrow" in lower:
            target = (datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(days=1)).date()
        else:
            parsed = dateparser.parse(msg, settings={
                "TIMEZONE": "Asia/Kolkata", "TO_TIMEZONE": "Asia/Kolkata", "RETURN_AS_TIMEZONE_AWARE": True
            })
            if not parsed:
                return {"message": "Sure—what date are you interested in?", "history": hist}
            target = parsed.date()

        free = get_free_slots_for_day(target)
        if not free:
            return {"message": f"Sorry, no free slots on {target.strftime('%B %d, %Y')}.", "history": hist, "slots": []}

        iso_list = [s[0] for s in free]
        times = [datetime.fromisoformat(s[0]).astimezone(ZoneInfo("Asia/Kolkata")).strftime("%-I:%M %p") for s in free]
        text = ", ".join(times)
        return {
            "message": f"Here are your available slots on {target.strftime('%B %d, %Y')}: {text}. Which one would you like to book?",
            "history": hist,
            "slots": iso_list
        }

    # 3) Fallback to LLM
    convo = "\n".join(f"User: {h}" if i%2==0 else f"Assistant: {h}" for i,h in enumerate(hist))
    prompt = (
        "You are a helpful appointment scheduling assistant.\n"
        f"{convo}\nUser: {msg}\nAssistant:"
    )
    try:
        r = requests.post(
            "https://api.together.xyz/inference",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "mistralai/Mistral-7B-Instruct-v0.1", "prompt": prompt, "max_tokens": 256}
        )
        data = r.json()
        choices = data.get("output", {}).get("choices", [])
        reply = choices[0].get("text","").strip() if choices else "⚠️ No reply."
    except Exception as e:
        reply = f"❌ Error: {e}"
    for tr in ["User:", "Assistant:"]:
        if tr in reply:
            reply = reply.split(tr)[0].strip()
    return {"message": reply, "history": hist}

workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

def run_agent(message: str, history: List[str]) -> dict:
    out = agent.invoke({"message": message, "history": history})
    slots = out.get("slots", [])
    reply = out.get("message","")
    # detect explicit datetime for booking proposal
    parsed = dateparser.parse(message, settings={
        "TIMEZONE": "Asia/Kolkata","TO_TIMEZONE": "Asia/Kolkata","RETURN_AS_TIMEZONE_AWARE": True
    })
    dt = parsed.isoformat() if parsed else None

    if parsed:
        start = parsed.isoformat()
        end = (parsed + timedelta(hours=1)).isoformat()
        busy = get_available_slots()
        for ev in busy:
            s = ev["start"].get("dateTime","")
            e = ev["end"].get("dateTime","")
            if s <= start < e:
                return {"reply":"That time is not available.","datetime":None,"slots":slots}
        return {"reply":"That time seems available. Would you like me to book it?","datetime":dt,"slots":slots}

    return {"reply":reply,"datetime":dt,"slots":slots}
