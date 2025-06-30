
import os
import requests
import json
import re
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

    prompt = (f"""
You are a friendly and intelligent appointment scheduling assistant. Respond to the user in a natural and helpful tone.

Your job is to:
1. **Understand intent**: Detect whether the user is trying to:
   - check available slots (`check_slots`)
   - book a specific time (`book_meeting`)
   - or just casually greet or talk (`unknown`)
   
2. **Extract datetime**: If the user mentions a day or time (like “next Friday at 3pm” or “tomorrow morning”), capture it exactly as said under `time_text`.

3. **Handle greetings & casual messages**: 
   If the user is just being friendly or greeting (e.g., "hi", "hello", "how are you", "good evening", "what’s up", "how do you do", "yo", "hey there", etc.), respond warmly but do **not** try to book or check anything. 
   In such cases:
   - intent = "unknown"
   - time_text = null

4. **Avoid assuming time** unless the user clearly specifies it. Don’t guess or make up a time if it’s vague.

5. **Always respond in a friendly tone**, and use JSON format as shown below.

Return your response strictly in this JSON format (and nothing else):

{{
  "reply": "Your assistant's full response here.",
  "intent": "check_slots", "book_meeting", or "unknown",
  "time_text": "natural language time description like 'next Tuesday at 3pm', or null"
}}

User: {message}
JSON:
"""
)


    try:
        response = requests.post(
            "https://api.together.xyz/inference",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/Mixtral-8x7B-Instruct-v0.1",
                "prompt": prompt,
                "max_tokens": 256,
                "temperature": 0.4
            }
        )

        data = response.json()
        raw_text = data.get("choices", [{}])[0].get("text", "")
        if not raw_text:
            return {"message": "⚠️ The model returned an empty response."}

        matches = re.findall(r"{.*?}", raw_text, re.DOTALL)
        if not matches:
            return {"message": f"⚠️ Could not find valid JSON in output:\n\n{raw_text}"}

        try:
            parsed = json.loads(matches[-1])
        except Exception:
            return {"message": f"⚠️ Failed to parse extracted JSON:\n\n{matches[-1]}"}

        reply = parsed.get("reply", "I'm here to help you schedule meetings.")
        intent = parsed.get("intent", "unknown")
        time_text = parsed.get("time_text")

        # If it's not a scheduling intent, just return reply
        if intent == "unknown":
            return {"message": reply}

        # Try parsing datetime from the natural time string
        parsed_date = None
        if time_text:
            parsed_date = dateparser.parse(
                time_text,
                settings={
                    'TIMEZONE': 'Asia/Kolkata',
                    'TO_TIMEZONE': 'UTC',
                    'RETURN_AS_TIMEZONE_AWARE': True
                }
            )

        if intent == "check_slots" and parsed_date:
            local_day = parsed_date.astimezone(ZoneInfo("Asia/Kolkata")).strftime('%A, %B %d')
            free_slots = get_free_slots_for_day(parsed_date.date())

            if not free_slots:
                return {"message": f"{reply}\n\nI'm fully booked on {local_day}."}

            formatted = "\n".join([
                f"• {datetime.fromisoformat(start).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p')} – {datetime.fromisoformat(end).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%I:%M %p')}"
                for start, end in free_slots
            ])
            return {
                "message": f"{reply}\n\nHere are my available slots on {local_day}:\n{formatted}\nWould you like to book one?"
            }

        elif intent == "book_meeting" and parsed_date:
            requested_start = parsed_date
            requested_end = requested_start + timedelta(hours=1)

            events = get_available_slots()
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                if start <= requested_start.isoformat() < end:
                    return {"message": f"{reply}\nBut that time is not available. Would you like to choose another slot?"}

            ist_time = requested_start.astimezone(ZoneInfo("Asia/Kolkata"))
            return {
                "message": f"{reply}\nThat time seems available ({ist_time.strftime('%B %d at %I:%M %p')}). Should I go ahead and book it?",
                "datetime": requested_start.isoformat()
            }

        return {"message": reply}

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
