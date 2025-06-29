import streamlit as st
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="📅 AI Appointment Scheduler", layout="centered")

API_BASE = "https://chatbot1-production-8826.up.railway.app"

# Light theme styling
st.markdown("""
<style>
body {
    background-color: #f5f5f5;
}
html, body, [class*="css"] {
    font-family: 'Segoe UI', sans-serif;
}

.chat-container {
    background-color: #ffffff;
    border-radius: 16px;
    padding: 1rem;
    max-width: 700px;
    margin: auto;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.chat-bubble {
    padding: 0.8rem 1rem;
    border-radius: 16px;
    margin-bottom: 0.5rem;
    max-width: 80%;
    word-wrap: break-word;
    color: #000000;
    font-size: 1rem;
}

.user-msg {
    background-color: #e3f2fd;
    align-self: flex-end;
    margin-left: auto;
}

.bot-msg {
    background-color: #f3e5f5;
    align-self: flex-start;
    margin-right: auto;
}

.chat-box {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 1rem;
    border-radius: 12px;
    background-color: #ffffff;
    min-height: 300px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='chat-container'>", unsafe_allow_html=True)

st.title("💬 AI Appointment Scheduler")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "proposed_time" not in st.session_state:
    st.session_state.proposed_time = None

# User input
user_input = st.text_input("You:", key="input", placeholder="e.g. Book a meeting on Friday at 2pm")

if user_input:
    st.session_state.messages.append({"role": "user", "text": user_input})
    try:
        response = requests.post(f"{API_BASE}/chat", json={
            "message": user_input,
            "history": [m["text"] for m in st.session_state.messages if m["role"] in ["user", "bot"]]
        })
        result = response.json()
        reply = result.get("reply", "⚠️ No reply received.")
        st.session_state.messages.append({"role": "bot", "text": reply})
        parsed_dt = result.get("datetime")
        if parsed_dt:
            st.session_state.proposed_time = parsed_dt
        # Clear input
        st.experimental_rerun()
    except Exception as e:
        st.session_state.messages.append({"role": "bot", "text": f"⚠️ Error: {e}"})

# Chat history
st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
for msg in st.session_state.messages:
    class_name = "user-msg" if msg["role"] == "user" else "bot-msg"
    st.markdown(f"<div class='chat-bubble {class_name}'>{msg['text']}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Proposed time and booking
if st.session_state.proposed_time:
    start = st.session_state.proposed_time
    end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()
    st.markdown("🕒 **Proposed time:** " + datetime.fromisoformat(start).strftime("%A, %B %d at %I:%M %p"))
    if st.button("✅ Yes, book this meeting"):
        booking = requests.post(f"{API_BASE}/book", json={"start": start, "end": end})
        if booking.status_code == 200:
            st.success("📅 Meeting booked successfully!")
            st.session_state.proposed_time = None
        else:
            st.error("❌ Booking failed.")

st.markdown("</div>", unsafe_allow_html=True)
