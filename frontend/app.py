
import streamlit as st
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="📅 Booking Assistant")
st.title("📅 AI Appointment Scheduler")

API_BASE = "https://chatbot1-production-8826.up.railway.app"

if "messages" not in st.session_state:
    st.session_state.messages = []
if "proposed_time" not in st.session_state:
    st.session_state.proposed_time = None

user_input = st.text_input("You:", key="input")

if user_input:
    st.session_state.messages.append(f"User: {user_input}")

    try:
        response = requests.post(f"{API_BASE}/chat", json={
            "message": user_input,
            "history": st.session_state.messages
        })
        result = response.json()

        reply = result.get("message", "⚠️ No reply received.")
        st.session_state.messages.append(f"Assistant: {reply}")

        st.write("🤖 " + reply)

        parsed_dt = result.get("datetime")
        if parsed_dt:
            st.session_state.proposed_time = parsed_dt
            readable_time = datetime.fromisoformat(parsed_dt).strftime("%A, %B %d at %I:%M %p")
            st.write(f"🕒 Proposed time: {readable_time}")
            if st.button("✅ Yes, book this meeting"):
                end_time = (datetime.fromisoformat(parsed_dt) + timedelta(hours=1)).isoformat()
                booking = requests.post(f"{API_BASE}/book", json={
                    "start": parsed_dt, "end": end_time
                })
                if booking.status_code == 200:
                    st.success("📅 Meeting booked successfully!")
                    st.session_state.proposed_time = None
                else:
                    st.error("❌ Booking failed.")
    except Exception as e:
        st.error(f"⚠️ Error: {e}")
