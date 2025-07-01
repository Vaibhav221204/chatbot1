import os
import requests
import re
from langgraph.graph import StateGraph
from typing import TypedDict
from dotenv import load_dotenv
import dateparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from backend.calendar_utils import get_free_slots_for_day

load_dotenv()
api_key = os.getenv("TOGETHER_API_KEY")

class AgentState(TypedDict):
    message: str
    history: list[str]

def respond(state: AgentState) -> AgentState:
    message = state["message"]
    history = state.get("history", [])

    convo = "\n".join([f"User: {h}" if i % 2 == 0 else f"Assistant: {h}" for i, h in enumerate(history)])

    prompt = (
        "You are a helpful and professional appointment scheduling assistant.\n"
        "Respond only as the assistant, never as the user.\n"
        "If the user says something casual (like 'hi', 'how are you'), reply politely but do not ask for appointments yet.\n"
        "If the user wants to book a meeting, ask for both date and time if missing.\n"
        "Always confirm availability before booking by checking the calendar.\n"
        "If time is already booked, ask the user to pick another slot.\n"
        "do not ask the user which service or purpose you need this appointment for.\n"
        "Only confirm booking if time is available.\n"
        "⚠️ NEVER include the words 'User:' or 'Assistant:' in your reply.\n"
        "⚠️ NEVER say 'I have booked the meeting' unless the user explicitly says 'yes'.\n"
        "✅ If the time is available, always ask: 'Would you like me to book it?' and wait.\n"
        "Use polite, clear responses and avoid repeating the same introduction multiple times.\n"
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
        reply_text = data.get("output", {}).get("choices", [{}])[0].get("text", "").strip()
        reply_text = reply_text.replace("User:", "").replace("Assistant:", "").strip()

        # Prevent fake booking replies
        if "I have booked" in reply_text and ("[date]" in reply_text or "[time]" in reply_text):
            reply_text = "✅ That time seems good. Would you like me to book it?"

        if not reply_text:
            reply_text = "I'm sorry, I didn’t understand that. Could you rephrase your request?"
    except Exception as e:
        return {"message": f"❌ Error: {str(e)}", "datetime": None, "history": history}

    parsed_date = dateparser.parse(
        message,
        settings={
            'TIMEZONE': 'Asia/Kolkata',
            'TO_TIMEZONE': 'Asia/Kolkata',
            'RETURN_AS_TIMEZONE_AWARE': True
        }
    )
    datetime_str = parsed_date.isoformat() if parsed_date else None
    print("⏰ Parsed datetime:", datetime_str)

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