import os
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary'

def get_calendar_service():
    # Decode credentials from Railway variable
    raw = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    if not raw:
        raise ValueError("Missing GOOGLE_CREDENTIALS_BASE64 variable!")

    # Decode and write to /tmp (safe for Railway)
    decoded = base64.b64decode(raw)
    with open("/tmp/credentials.json", "wb") as f:
        f.write(decoded)

    credentials = service_account.Credentials.from_service_account_file(
        "/tmp/credentials.json", scopes=SCOPES
    )
    return build("calendar", "v3", credentials=credentials)

def get_available_slots():
    service = get_calendar_service()
    now = datetime.utcnow().isoformat() + 'Z'
    future = (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=now,
        timeMax=future,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    return events_result.get('items', [])

def create_event(start_time, end_time, summary='Meeting'):
    service = get_calendar_service()
    event = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': 'UTC'},
        'end': {'dateTime': end_time, 'timeZone': 'UTC'},
    }
    return service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
