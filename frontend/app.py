import streamlit as st
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="📅 AI Appointment Scheduler", layout="centered")

API_BASE = "https://chatbot1-production-8826.up.railway.app"

st.markdown("""
<style>
.chat-container {
    background-color: #ffffff;
    border-radius: 16px;
    padding: 1.5rem;
    max-width: 700px;
    margin: auto;
    box-shadow: 0 10px 25px rgba(0,0,0,0.05);
    display: flex;
    flex-direction: column;
    gap: 1rem;
}
.chat-box {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    height: 400px;
    overflow-y: auto;
    border: 1px solid #ddd;
    border-radius: 16px;
    padding: 1rem;
    background: linear-gradient(to bottom right, #ffffff, #f8f9fa);
}
.user-msg, .bot-msg {
    padding: 0.75rem 1rem;
    border-radius: 12px;
    margin-bottom: 0.5rem;
    max-width: 80%;
    word-wrap: break-word;
}
.user-msg {
    background-color: #E0F7FA;
    align-self: flex-end;
    margin-left: auto;
}
.bot-msg {
    background-color: #F3E5F5;
    align-self: flex-start;
    margin-right: auto;
}
.input-area input {
    width: 100%;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    border: 1px solid #ccc;
}
</style>
""", unsafe_allow_html=True)

st.title("💬 AI Appointment Scheduler")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "proposed_time" not in st.session_state:
    st.session_state.proposed_time = None

with st.container():
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)

    # CHAT BOX
    st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
    for msg in st.session_state.messages:
        role = msg["role"]
        text = msg["text"]
        class_name = "user-msg" if role == "user" else "bot-msg"
        st.markdown(f"<div class='{class_name}'>{text}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # TEXT INPUT INSIDE CHAT CONTAINER
    user_input = st.text_input("Type your message", label_visibility="collapsed",
                               placeholder="e.g. Book a meeting on Friday at 2pm", key="input_box")

    if user_input:
        st.session_state.messages.append({"role": "user", "text": user_input})
        st.session_state["input_box"] = ""  # Clear input after submission

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
        except Exception as e:
            st.session_state.messages.append({"role": "bot", "text": f"⚠️ Error: {e}"})

    # PROPOSED TIME + BUTTON
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

    st.markdown("</div>", unsafe_allow_html=True)  # close chat-container
