import streamlit as st
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="📅 Booking Assistant")
st.title("📅 AI Appointment Scheduler")

API_BASE = "https://chatbot1-production-8826.up.railway.app"

if "messages" not in st.session_state:
    st.session_state.messages = []

user_input = st.text_input("You:", key="input")

if user_input:
    st.session_state.messages.append({"role": "user", "text": user_input})

    try:
        # The backend expects a key called "query"
        response = requests.post(f"{API_BASE}/chat", json={"query": user_input})
        result = response.json()

        # Safely extract chatbot's reply
        reply = result.get("reply")
        bot_message = (
            reply["choices"][0]["text"]
            if isinstance(reply, dict) and "choices" in reply
            else str(reply)
        )

        st.session_state.messages.append({"role": "bot", "text": bot_message})
        st.write("🤖 " + bot_message)

        # If datetime is present, offer to book
        if result.get("datetime"):
            start = result["datetime"]
            end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()

            if st.button("✅ Yes, book this meeting"):
                booking = requests.post(f"{API_BASE}/book", json={"start": start, "end": end})
                if booking.status_code == 200:
                    st.success("📅 Meeting booked successfully!")
                else:
                    st.error("❌ Booking failed.")
    except Exception as e:
        st.error(f"⚠️ Error: {e}")
