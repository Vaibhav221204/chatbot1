from backend.calendar_utils import check_availability
from datetime import datetime

def run_conversation(message: str, history: list[str]):
    prompt = (
        "You are an appointment booking assistant. Stay focused only on scheduling meetings. "
        "Do not roleplay both user and assistant. Only respond as the assistant.\n"
        "Ask for date and time if not provided. Before confirming a meeting, check the calendar for conflicts.\n"
        "If the time is already booked, ask the user to choose another slot. Otherwise, confirm and ask if you'd like to book it.\n"
        "If the user asks for available time slots, use calendar data and respond accordingly.\n\n"
        f"User: {message}\nAssistant:"
    )

    dt = parse_datetime_from_text(message)
    if "available" in message.lower() or "slot" in message.lower():
        return {"reply": check_availability(message), "datetime": None}
    if dt:
        available = check_availability(dt)
        if available:
            return {"reply": f"That time seems available. Would you like me to book it?", "datetime": dt.isoformat()}
        else:
            return {"reply": "Sorry, you're not free at that time. Would you like to pick another?", "datetime": None}

    return {"reply": "Sure, what date and time would you like to schedule the appointment for?", "datetime": None}

def parse_datetime_from_text(text: str):
    import dateparser
    dt = dateparser.parse(text)
    if dt and dt > datetime.now():
        return dt
    return None