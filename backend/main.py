from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from backend import calendar_utils
from backend.agent import run_agent
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Booking API working ✅"}

class ChatRequest(BaseModel):
    message: str
    history: List[str] = []

@app.post("/chat")
async def chat(request: ChatRequest):
    result = run_agent(request.message, request.history)
    return {"reply": result["reply"], "datetime": result["datetime"]}

@app.get("/slots")
def slots():
    return {"events": calendar_utils.get_available_slots()}

class BookRequest(BaseModel):
    start: str
    end: str

@app.post("/book")
async def book(request: BookRequest):
    print("📥 Received booking request:", request.start, "to", request.end)
    try:
        result = calendar_utils.create_event(request.start, request.end)
        print("✅ Event created:", result)
        return {"status": "Booked ✅", "event": result}
    except Exception as e:
        print("❌ Booking failed:", e)
        return {"status": "Failed ❌", "error": str(e)}
