import streamlit as st
import requests
import os

API_BASE = "https://chatbot1-production-8826.up.railway.app"  # your deployed FastAPI base

st.set_page_config(page_title="AI Appointment Scheduler", page_icon="📅")
st.title("📅 AI Appointment Scheduler")

if "messages" not in st.session_state:
    st.session_state.messages = []

user_input = st.chat_input("How can I help you?")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        try:
            # Send POST request with key 'query' as expected by FastAPI
            response = requests.post(f"{API_BASE}/chat", json={"query": user_input})
            response.raise_for_status()
            result = response.json()
            message = result["message"]
            st.markdown("😊 " + message)
        except Exception as e:
            st.error(f"⚠️ No reply received.\n\nError: {str(e)}")

    st.session_state.messages.append({"role": "assistant", "content": message})
