import streamlit as st
import requests
import re
import dateparser
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="📅 AI Appointment Scheduler", layout="centered")
API_BASE = "https://chatbot1-production-8826.up.railway.app"

# ——— Your original styling/UI code ———
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
# —————————————————————————————

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "proposed_time" not in st.session_state:
    st.session_state.proposed_time = None
if "last_slots" not in st.session_state:
    st.session_state.last_slots = []
if "input_key" not in st.session_state:
    st.session_state.input_key = "input_1"

# User input
user_input = st.text_input(
    "You:", key=st.session_state.input_key,
    placeholder="e.g. Book a meeting on Friday at 2pm"
)

if user_input:
    # Store user message
    st.session_state.messages.append({"role": "user", "text": user_input})

    # 1) Auto-yes intercept: preserve booking button
    if user_input.strip().lower() in ("yes", "y", "sure", "please") \
       and st.session_state.proposed_time:
        st.session_state.messages.append({
            "role": "bot",
            "text": "Great! Please click the button below to confirm the booking."
        })
        st.session_state.input_key = f"input_{len(st.session_state.messages)}"
        st.rerun()

    # 2) Direct time pick from last_slots
    parsed = dateparser.parse(
        user_input,
        settings={
            "TIMEZONE": "Asia/Kolkata",
            "TO_TIMEZONE": "Asia/Kolkata",
            "RETURN_AS_TIMEZONE_AWARE": True
        }
    )
    if parsed:
        iso = parsed.isoformat()
        if iso in st.session_state.last_slots:
            st.session_state.proposed_time = iso
            st.session_state.input_key = f"input_{len(st.session_state.messages)}"
            st.rerun()

    # 3) Ordinal pick (first/second/third)
    m = re.search(r"\b(first|second|third|fourth)\b", user_input.lower())
    if m and st.session_state.last_slots:
        idx = {"first":0, "second":1, "third":2, "fourth":3}[m.group(1)]
        if idx < len(st.session_state.last_slots):
            st.session_state.proposed_time = st.session_state.last_slots[idx]
            st.session_state.input_key = f"input_{len(st.session_state.messages)}"
            st.rerun()

    # 4) Normal /chat call with history
    history_texts = [m["text"] for m in st.session_state.messages]
    resp = requests.post(
        f"{API_BASE}/chat",
        json={"message": user_input, "history": history_texts}
    )
    try:
        result = resp.json()
    except requests.JSONDecodeError:
        st.error(f"Server returned invalid JSON:\n\n{resp.text}")
        st.session_state.input_key = f"input_{len(st.session_state.messages)}"
        st.rerun()

    # Append assistant reply
    reply = result.get("reply", "⚠️ No reply received.")
    st.session_state.messages.append({"role": "bot", "text": reply})

    # Cache raw slots list if present
    slots = result.get("slots", [])
    if isinstance(slots, list) and slots:
        st.session_state.last_slots = slots

    # Capture datetime for booking button
    if result.get("datetime"):
        st.session_state.proposed_time = result["datetime"]

    # Advance input and rerun
    st.session_state.input_key = f"input_{len(st.session_state.messages)}"
    st.rerun()

# Render chat bubbles
st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
for msg in st.session_state.messages:
    css_class = "user" if msg["role"] == "user" else "bot"
    st.markdown(
        f"<div class='chat-bubble {css_class}'>{msg['text']}</div>",
        unsafe_allow_html=True
    )
st.markdown("</div>", unsafe_allow_html=True)

# Booking UI
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
            st.session_state.messages.app_
