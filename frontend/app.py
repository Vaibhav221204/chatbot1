import streamlit as st
import requests
from datetime import datetime, timedelta

st.set_page_config(page_title="📅 Booking Assistant")
st.title("📅 AI Appointment Scheduler")

if "messages" not in st.session_state:
    st.session_state.messages = []

user_input = st.text_input("You:", key="input")

if user_input:
    st.session_state.messages.append({"role": "user", "text": user_input})

    response = requests.post("http://localhost:8000/chat", json={"message": user_input}).json()
    st.session_state.messages.append({"role": "bot", "text": response["reply"]})

    st.write("🤖 " + response["reply"])

    if response["datetime"]:
        start = response["datetime"]
        end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()
        if st.button("✅ Yes, book this meeting"):
            booked = requests.post("http://localhost:8000/book", json={"start": start, "end": end})
            if booked.status_code == 200:
                st.success("📅 Meeting booked successfully!")
