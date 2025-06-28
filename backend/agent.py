import os
import requests
from langgraph.graph import StateGraph, END
from typing import TypedDict
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("TOGETHER_API_KEY")

# Define state structure
class AgentState(TypedDict):
    message: str

def respond(state: AgentState):
    message = state["message"]

    model = "mistralai/Mistral-7B-Instruct-v0.1"
    prompt = f"### Human: {message}\n### Assistant:"

    try:
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
        data = response.json()
        output = data.get("output") or "⚠️ No output received from Together API."
    except Exception as e:
        output = f"❌ Error: {str(e)}"

    return {"message": output}

workflow = StateGraph(AgentState)
workflow.add_node("chat", respond)
workflow.set_entry_point("chat")
workflow.set_finish_point("chat")
agent = workflow.compile()

def run_agent(message: str) -> str:
    result = agent.invoke({"message": message})
    return result["message"]
