import streamlit as st
import requests
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="📅 AI Appointment Scheduler", layout="centered")
API_BASE = "https://chatbot1-production-8826.up.railway.app"

# your CSS/UI
st.markdown("""
<style>
.chat-bubble { /* ... */ }
.user { /* ... */ }
.bot { /* ... */ }
.chat-box { /* ... */ }
</style>
""", unsafe_allow_html=True)
st.title("💬 AI Appointment Scheduler")

# session init
if "messages" not in st.session_state:
    st.session_state.messages = []
if "proposed_time" not in st.session_state:
    st.session_state.proposed_time = None
if "last_slots" not in st.session_state:
    st.session_state.last_slots = []
if "input_key" not in st.session_state:
    st.session_state.input_key = "input_1"

user_input = st.text_input("You:", key=st.session_state.input_key,
                           placeholder="e.g. Book a meeting on Friday at 2pm")

if user_input:
    st.session_state.messages.append({"role":"user","text":user_input})

    # 1) detect ordinal booking commands
    m = re.search(r"\\b(first|second|third|fourth)\\b", user_input.lower())
    if m and st.session_state.last_slots:
        idx = {"first":0,"second":1,"third":2,"fourth":3}[m.group(1)]
        if idx < len(st.session_state.last_slots):
            st.session_state.proposed_time = st.session_state.last_slots[idx]
            st.session_state.input_key = f"input_{len(st.session_state.messages)}"
            st.rerun()

    # 2) normal /chat request
    history = [m["text"] for m in st.session_state.messages]
    resp = requests.post(f"{API_BASE}/chat", json={
        "message": user_input,
        "history": history
    })
    try:
        result = resp.json()
    except requests.JSONDecodeError:
        st.error(f"Server error:\n\n{resp.text}")
        st.session_state.input_key = f"input_{len(st.session_state.messages)}"
        st.rerun()

    reply = result.get("reply", "⚠️ No reply.")
    st.session_state.messages.append({"role":"bot","text":reply})

    # capture raw slots list if present
    slots = result.get("slots", [])
    if slots:
        st.session_state.last_slots = slots

    # capture datetime if present
    if result.get("datetime"):
        st.session_state.proposed_time = result["datetime"]

    st.session_state.input_key = f"input_{len(st.session_state.messages)}"
    st.rerun()

# render chat
st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
for msg in st.session_state.messages:
    css = "user" if msg["role"]=="user" else "bot"
    st.markdown(f"<div class='chat-bubble {css}'>{msg['text']}</div>",
                unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# booking UI
if st.session_state.proposed_time:
    start = st.session_state.proposed_time
    end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()
    local = datetime.fromisoformat(start).astimezone(ZoneInfo("Asia/Kolkata"))
    st.markdown("🕒 **Proposed time:** "+local.strftime("%A, %B %d at %I:%M %p"))
    if st.button("✅ Yes, book this meeting"):
        book = requests.post(f"{API_BASE}/book", json={"start":start,"end":end})
        if book.status_code==200:
            st.success("📅 Meeting booked successfully!")
            st.session_state.messages.append({
                "role":"bot",
                "text":f"✅ Your meeting has been booked for {local.strftime('%B %d at %I:%M %p')}."
            })
            st.session_state.proposed_time = None
            st.session_state.last_slots = []
        else:
            st.error("❌ Booking failed.")
