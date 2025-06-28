# backend/main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend import calendar_utils
from backend.agent import run_agent  # ✅ Updated to point to correct agent
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Booking API working ✅"}

# Pydantic input model
class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
async def chat(request: ChatRequest):
    response = run_agent(request.message)
    return {"reply": response}

@app.get("/slots")
def slots():
    return {"events": calendar_utils.get_available_slots()}

class BookRequest(BaseModel):
    start: str
    end: str

@app.post("/book")
async def book(request: BookRequest):
    result = calendar_utils.create_event(request.start, request.end)
    return {"status": "Booked ✅", "event": result}

