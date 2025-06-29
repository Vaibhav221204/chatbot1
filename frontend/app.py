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
        response = requests.post(f"{API_BASE}/chat", json={"message": user_input})
        result = response.json()

        # Ensure response is a plain string
        bot_reply = result.get("reply", "")
        if isinstance(bot_reply, dict):
            bot_reply = str(bot_reply)

        st.session_state.messages.append({"role": "bot", "text": bot_reply})
        st.write("🤖 " + bot_reply)

        # Optional booking if datetime was extracted
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
