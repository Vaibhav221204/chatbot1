# backend/calendar_utils.py

import os
import base64
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from dateutil.parser import isoparse

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

# UPDATED get_free_slots_for_day with proper tz-aware comparisons
LOCAL_TZ = ZoneInfo("Asia/Kolkata")

def get_free_slots_for_day(target_date):
    service = get_calendar_service()

    # Build the IST‐localized day bounds (9:00–17:00)
    start_of_day = datetime.combine(target_date, time(9, 0), tzinfo=LOCAL_TZ)
    end_of_day   = datetime.combine(target_date, time(17, 0), tzinfo=LOCAL_TZ)

    # Ask Google for events in UTC
    utc_start = start_of_day.astimezone(ZoneInfo("UTC")).isoformat()
    utc_end   = end_of_day.astimezone(ZoneInfo("UTC")).isoformat()

    events = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=utc_start,
        timeMax=utc_end,
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items', [])

    # Parse busy intervals into IST tz‐aware datetimes
    busy = []
    for e in events:
        raw_s = e['start'].get('dateTime')
        raw_e = e['end'].get('dateTime')
        if raw_s and raw_e:
            s = isoparse(raw_s).astimezone(LOCAL_TZ)
            t = isoparse(raw_e).astimezone(LOCAL_TZ)
            busy.append((s, t))

    # Build half‐hour slots from 9:00 to 17:00 in IST
    slots = []
    slot_start = start_of_day
    while slot_start + timedelta(minutes=30) <= end_of_day:
        slot_end = slot_start + timedelta(minutes=30)
        # include slot only if it does not overlap any busy block
        if all(not (slot_start < b_end and slot_end > b_start) for b_start, b_end in busy):
            slots.append((slot_start.isoformat(), slot_end.isoformat()))
        slot_start = slot_end

    return slots

def create_event(start_time, end_time, summary='Meeting'):
    service = get_calendar_service()
    event = {
        'summary': summary,
        'start': {'dateTime': start_time, 'timeZone': 'UTC'},
        'end':   {'dateTime': end_time,   'timeZone': 'UTC'},
    }
    return service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
