
import os
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta, time

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'vaibhav22gandhi@gmail.com'

def get_calendar_service():
    raw = os.getenv("GOOGLE_CREDENTIALS_BASE64")
    if not raw:
        raise ValueError("Missing GOOGLE_CREDENTIALS_BASE64 variable!")

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

def get_free_slots_for_day(target_date):
    service = get_calendar_service()
    start_of_day = datetime.combine(target_date, time(9, 0))
    end_of_day = datetime.combine(target_date, time(17, 0))
    utc_start = start_of_day.isoformat() + 'Z'
    utc_end = end_of_day.isoformat() + 'Z'

    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=utc_start,
        timeMax=utc_end,
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items', [])

    # Build list of free slots (1-hour blocks from 9 AM to 5 PM)
    all_slots = [(start_of_day + timedelta(hours=i), start_of_day + timedelta(hours=i+1)) for i in range(8)]
    busy_times = [(datetime.fromisoformat(e['start']['dateTime'].replace('Z', '')),
                   datetime.fromisoformat(e['end']['dateTime'].replace('Z', '')))
                  for e in events]

    free_slots = []
    for slot_start, slot_end in all_slots:
        if all(not (slot_start < b_end and slot_end > b_start) for b_start, b_end in busy_times):
            free_slots.append((slot_start.isoformat(), slot_end.isoformat()))

    return free_slots
