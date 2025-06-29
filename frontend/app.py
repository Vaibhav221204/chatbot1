import streamlit as st
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="📅 AI Appointment Scheduler", layout="centered")

API_BASE = "https://chatbot1-production-8826.up.railway.app"

# Inject custom CSS for clean chat UI
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

# Session state setup
if "messages" not in st.session_state:
    st.session_state.messages = []
if "proposed_time" not in st.session_state:
    st.session_state.proposed_time = None

# Text input
user_input = st.text_input("You:", key="input_text", placeholder="e.g. Book a meeting on Friday at 2pm")

# Handle user input and chatbot reply
if user_input:
    st.session_state.messages.append({"role": "user", "text": user_input})
    try:
        response = requests.post(f"{API_BASE}/chat", json={
            "message": user_input,
            "history": [m["text"] for m in st.session_state.messages if m["role"] in ["user", "bot"]]
        })
        result = response.json()
        reply = result.get("reply", "⚠️ No reply received.")

        # Only show bot message if not a booking confirmation
        if "I have scheduled" not in reply and "meeting booked" not in reply.lower():
            st.session_state.messages.append({"role": "bot", "text": reply})

        # Store datetime for booking button
        if result.get("datetime"):
            st.session_state.proposed_time = result["datetime"]

    except Exception as e:
        st.session_state.messages.append({"role": "bot", "text": f"⚠️ Error: {e}"})

    # Clear the input box after submission
    del st.session_state["input_text"]
    st.rerun()

# Display messages
st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
for msg in st.session_state.messages:
    role = msg["role"]
    css_class = "user" if role == "user" else "bot"
    st.markdown(f"<div class='chat-bubble {css_class}'>{msg['text']}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Show booking confirmation button
if st.session_state.proposed_time:
    start = st.session_state.proposed_time
    end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()

    st.markdown("🕒 **Proposed time:** " + datetime.fromisoformat(start).strftime("%A, %B %d at %I:%M %p"))

    if st.button("✅ Yes, book this meeting"):
        booking = requests.post(f"{API_BASE}/book", json={"start": start, "end": end})
        if booking.status_code == 200:
            st.success("📅 Meeting booked successfully!")
            st.session_state.messages.append({
                "role": "bot",
                "text": f"✅ Your meeting has been booked for {datetime.fromisoformat(start).strftime('%B %d at %I:%M %p')}."
            })
            st.session_state.proposed_time = None
        else:
            st.error("❌ Booking failed.")
