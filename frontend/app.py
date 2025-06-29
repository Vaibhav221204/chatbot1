import streamlit as st
import requests
import datetime

st.set_page_config(page_title="AI Appointment Scheduler", page_icon="📅")
st.markdown("<h1 style='text-align: center;'>📅 AI Appointment Scheduler</h1>", unsafe_allow_html=True)

API_BASE = "https://chatbot1-production-8826.up.railway.app"

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.container():
    for msg in st.session_state.messages:
        role = "assistant" if msg["role"] == "assistant" else "user"
        with st.chat_message(role):
            st.markdown(msg["content"])

prompt = st.chat_input("How can I help you?")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            response = requests.post(f"{API_BASE}/chat", json={"message": prompt})
            result = response.json()
            reply = result.get("reply", "No reply received.")
            dt = result.get("datetime")

            st.session_state.datetime = dt
            st.session_state.last_prompt = prompt
            st.session_state.messages.append({"role": "assistant", "content": reply})
            st.markdown(reply)

            if dt:
                if st.button("✅ Yes, book this meeting"):
                    payload = {"datetime": dt, "user_input": st.session_state.last_prompt}
                    book_response = requests.post(f"{API_BASE}/book", json=payload)
                    if book_response.status_code == 200:
                        st.success("✅ Meeting successfully booked!")
                    else:
                        st.error("❌ Booking failed.")

        except Exception as e:
            st.error(f"⚠️ No reply received.\n\n{e}")
