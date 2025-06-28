
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta

SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary'

def get_calendar_service():
    credentials = service_account.Credentials.from_service_account_file(
        'backend/credentials.json', scopes=SCOPES)
    return build('calendar', 'v3', credentials=credentials)

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
