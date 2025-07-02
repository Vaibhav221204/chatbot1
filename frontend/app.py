# frontend/app.py

import streamlit as st
import requests
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="📅 AI Appointment Scheduler", layout="centered")
API_BASE = "https://chatbot1-production-8826.up.railway.app"

# ——— Your CSS/UI styling ———
st.markdown("""
<style>
.chat-bubble {
    padding: 0.75rem 1rem;
    border-radius: 12px;
    margin: 0.5rem 0;
    max-width: 80%;
    word-wrap: break-word;
    font-weight: 500;
}
.user {
    background-color: #E0F7FA;
    align-self: flex-end;
    margin-left: auto;
    color: black;
}
.bot {
    background-color: #F3E5F5;
    align-self: flex-start;
    margin-right: auto;
    color: black;
}
.chat-box {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 1rem;
    background: linear-gradient(to bottom right, #ffffff, #f8f9fa);
    border-radius: 12px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)

st.title("💬 AI Appointment Scheduler")

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_slots" not in st.session_state:
    st.session_state.last_slots = []
if "proposed_time" not in st.session_state:
    st.session_state.proposed_time = None
if "input_key" not in st.session_state:
    st.session_state.input_key = "input_1"

# User input
user_input = st.text_input(
    "You:", key=st.session_state.input_key,
    placeholder="e.g. Book a meeting on Friday at 2pm"
)

if user_input:
    st.session_state.messages.append({"role": "user", "text": user_input})

    # 1) “Yes” intercept: keep booking button alive
    if user_input.strip().lower() in ("yes", "y", "sure", "please") \
       and st.session_state.proposed_time:
        st.session_state.messages.append({
            "role": "bot",
            "text": "Perfect—please click the button below to confirm the booking."
        })
        st.session_state.input_key = f"input_{len(st.session_state.messages)}"
        st.rerun()

    # 2) Direct time-pick intercept: match raw time against last_slots
    elif (m := re.match(r"^\s*(\d{1,2}(?::\d{2})?)\s*(am|pm)\s*$", user_input.strip(), re.IGNORECASE)):
        raw = m.group(1)  # "3:30" or "3"
        suffix = m.group(2).lower()  # "am" or "pm"
        time_str1 = f"{raw.lower()}{suffix}"        # "3:30pm"
        time_str2 = f"{raw.lower()}"               # "3:30"
        for slot_iso in st.session_state.last_slots:
            slot_dt = datetime.fromisoformat(slot_iso).astimezone(ZoneInfo("Asia/Kolkata"))
            s1 = slot_dt.strftime("%-I:%M%p").lower()
            s2 = slot_dt.strftime("%-I:%M").lower()
            if time_str1 == s1 or time_str2 == s2:
                st.session_state.proposed_time = slot_iso
                break
        if st.session_state.proposed_time:
            st.session_state.input_key = f"input_{len(st.session_state.messages)}"
            st.rerun()

    # 3) Ordinal-pick intercept (“first”, “second”, etc.)
    elif (m2 := re.search(r"\b(first|second|third|fourth)\b", user_input.lower())) \
         and st.session_state.last_slots:
        idx = {"first": 0, "second": 1, "third": 2, "fourth": 3}[m2.group(1)]
        if idx < len(st.session_state.last_slots):
            st.session_state.proposed_time = st.session_state.last_slots[idx]
            st.session_state.input_key = f"input_{len(st.session_state.messages)}"
            st.rerun()

    # 4) Fallback to backend
    else:
        history = [m["text"] for m in st.session_state.messages]
        resp = requests.post(
            f"{API_BASE}/chat",
            json={"message": user_input, "history": history}
        )
        try:
            res = resp.json()
        except Exception:
            st.error(f"Server error:\n\n{resp.text}")
            st.session_state.input_key = f"input_{len(st.session_state.messages)}"
            st.rerun()

        # Append assistant reply
        st.session_state.messages.append({"role": "bot", "text": res.get("reply", "⚠️ No reply received.")})

        # Cache returned slots
        slots = res.get("slots", [])
        if isinstance(slots, list) and slots:
            st.session_state.last_slots = slots

        # Capture any datetime for booking
        if res.get("datetime"):
            st.session_state.proposed_time = res["datetime"]

        st.session_state.input_key = f"input_{len(st.session_state.messages)}"
        st.rerun()

# Render chat bubbles
st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
for msg in st.session_state.messages:
    cls = "user" if msg["role"] == "user" else "bot"
    st.markdown(f"<div class='chat-bubble {cls}'>{msg['text']}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Show booking button when proposed_time is set
if st.session_state.proposed_time:
    start_iso = st.session_state.proposed_time
    end_iso = (datetime.fromisoformat(start_iso) + timedelta(hours=1)).isoformat()
    local = datetime.fromisoformat(start_iso).astimezone(ZoneInfo("Asia/Kolkata"))

    st.markdown("🕒 **Proposed time:** " + local.strftime("%A, %B %d at %I:%M %p"))
    if st.button("✅ Yes, book this meeting"):
        booking = requests.post(
            f"{API_BASE}/book",
            json={"start": start_iso, "end": end_iso}
        )
        if booking.status_code == 200:
            st.success("📅 Meeting booked successfully!")
            st.session_state.messages.append({
                "role": "bot",
                "text": f"✅ Your meeting has been booked for {local.strftime('%B %d at %I:%M %p')}"
            })
            st.session_state.proposed_time = None
            st.session_state.last_slots = []
        else:
            st.error("❌ Booking failed.")
