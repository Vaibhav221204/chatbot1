import streamlit as st
import requests

st.set_page_config(page_title="AI Appointment Scheduler", page_icon="📅")

st.title("📅 AI Appointment Scheduler")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("How can I help you?"):
    st.chat_message("user").write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    try:
        res = requests.post(
            "https://chatbot1-production-8826.up.railway.app/chat",
            json={"message": prompt},
            timeout=30
        )
        res.raise_for_status()
        data = res.json()
        
        # ✅ Extract only assistant's reply text
        reply = data.get("choices", [{}])[0].get("text", "").strip()

        if not reply:
            reply = "⚠️ No meaningful reply received from the assistant."

    except Exception as e:
        reply = f"⚠️ No reply received.\n\nError: {str(e)}"

    st.chat_message("assistant").write(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
