import os
import requests
from langgraph.graph import StateGraph
from typing import TypedDict
from dotenv import load_dotenv
import dateparser
import re

load_dotenv()
api_key = os.getenv("TOGETHER_API_KEY")

# Define the agent's state type
class AgentState(TypedDict):
    message: str

# The function that handles the AI response
def respond(state: AgentState) -> AgentState:
    message = state["message"]
    model = "mistralai/Mistral-7B-Instruct-v0.1"
    prompt = f"### Human: {message}\n### Assistant:"

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

        if response.status_code != 200:
            return {"message": f"⚠️ Together API error: {response.status_code} - {response.text}"}

        data = response.json()
        print("📦 Raw response JSON:", data)

        # Safe extraction
        output = ""
        if "choices" in data and isinstance(data["choices"], list):
            output = data["choices"][0].get("text", "")
        elif "output" in data:
            output = data["output"]

        if not isinstance(output, str):
            output = str(output)

        cleaned = re.split(r"###\s*Assistant:", output)[-1].strip()
        return {"message": cleaned}

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
