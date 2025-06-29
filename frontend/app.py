import streamlit as st
import requests

st.set_page_config(page_title="AI Appointment Scheduler", page_icon="📅", layout="wide")

st.markdown("<h1 style='text-align: center;'>📅 AI Appointment Scheduler</h1>", unsafe_allow_html=True)

API_URL = "https://chatbot1-production-8826.up.railway.app/chat"  # Your Railway FastAPI URL

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input from user
prompt = st.chat_input("How can I help you?")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = requests.post(API_URL, json={"prompt": prompt})
                response.raise_for_status()
                data = response.json()

                # 🔥 FIX: Safely extract only the assistant reply text
                raw_text = data.get("output", {}).get("choices", [{}])[0].get("text", "").strip()

                if raw_text:
                    # Show response
                    st.markdown(raw_text)
                    st.session_state.messages.append({"role": "assistant", "content": raw_text})
                else:
                    st.warning("⚠️ No meaningful reply received from the assistant.")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
