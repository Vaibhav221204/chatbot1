import os
import requests
from langgraph.graph import StateGraph
from typing import TypedDict
from dotenv import load_dotenv
import dateparser

load_dotenv()
api_key = os.getenv("TOGETHER_API_KEY")

# Define the agent's state type
class AgentState(TypedDict):
    message: str

# The function that handles the AI response
def respond(state: AgentState) -> AgentState:
    message = state["message"]
    model = "mistralai/Mistral-7B-Instruct-v0.1"
    system_instruction = (
        "You are an appointment scheduling assistant. "
        "Your only job is to help users schedule meetings. "
        "Ask for a preferred date and time, confirm it, and offer to book it. "
        "Do not answer questions outside scheduling. Be concise and helpful."
    )

    prompt = (
        f"<|system|>\n{system_instruction}\n"
        f"<|user|>\n{message}\n"
        f"<|assistant|>"
    )

    try:
        print("📨 Sending to Together API...")
        print("📨 Prompt:", prompt)

        response = requests.post(
            "https://api.together.xyz/inference",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "prompt": prompt,
                "max_tokens": 256,
                "temperature": 0.7
            }
        )

        print("📬 Status Code:", response.status_code)
        data = response.json()
        print("📦 Raw response JSON:", data)

        if "output" in data and isinstance(data["output"], dict):
            choices = data["output"].get("choices", [])
            if choices and "text" in choices[0]:
                reply_text = choices[0]["text"].strip()
            else:
                reply_text = "⚠️ No valid response text found."
        else:
            reply_text = str(data.get("output", "⚠️ No output."))

        return {"message": reply_text}

    except Exception as e:
        print("❌ Exception caught:", e)
        return {"message": f"❌ Error: {str(e)}"}

# Build the LangGraph workflow
workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

# External callable function for FastAPI
def run_agent(message: str) -> dict:
    result = agent.invoke({"message": message})
    response_text = result.get("message", "")

    if not isinstance(response_text, str):
        response_text = str(response_text)

    parsed_date = dateparser.parse(message)
    datetime_str = parsed_date.isoformat() if parsed_date else None

    return {
        "reply": response_text,
        "datetime": datetime_str
    }
