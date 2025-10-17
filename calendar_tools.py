# calendar_tools.py

import os.path
from datetime import datetime, timedelta
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import Optional

# --- Configuration & Setup ---
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly", # To read/search emails
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/tasks"  # To manage tasks
]
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Reusable Authentication Function ---
def get_credentials():
    """Handles Google API authentication and token management."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials.")
            creds.refresh(Request())
        else:
            logger.info("No valid credentials found, starting OAuth flow.")
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

# --- Tool Definitions ---

class SearchEventsInput(BaseModel):
    query: Optional[str] = Field(None, description="A text-based search query to filter events by their summary, description, or location.")
    start_time: str = Field(description="The start of the search window in 'YYYY-MM-DD HH:MM:SS' format.")
    end_time: str = Field(description="The end of the search window in 'YYYY-MM-DD HH:MM:SS' format.")
    max_results: int = Field(default=10, description="The maximum number of events to return.")

@tool(args_schema=SearchEventsInput)
def search_calendar_events(start_time: str, end_time: str, query: Optional[str] = None, max_results: int = 10) -> str:
    """
    Searches the calendar for events within a given time range. Can also filter by a text query.
    This is the primary tool for finding events to read, update, or delete.
    """
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        
        time_min_iso = datetime.fromisoformat(start_time).isoformat() + 'Z'
        time_max_iso = datetime.fromisoformat(end_time).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId="primary",
            q=query,
            timeMin=time_min_iso,
            timeMax=time_max_iso,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        events = events_result.get("items", [])

        if not events:
            return "No events found matching your criteria."

        event_summaries = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            # Crucially, we return the event ID so the agent can use it
            event_summaries.append(f"- Summary: {event['summary']} | Starts: {start} | ID: {event['id']}")
        return "\n".join(event_summaries)
    except Exception as e:
        return f"An error occurred: {e}"

class CreateEventInput(BaseModel):
    summary: str = Field(description="The title of the event.")
    start_datetime: str = Field(description="The event start datetime in 'YYYY-MM-DD HH:MM:SS' format.")
    end_datetime: str = Field(description="The event end datetime in 'YYYY-MM-DD HH:MM:SS' format.")
    location: Optional[str] = Field(None, description="The location of the event.")
    description: Optional[str] = Field(None, description="The description for the event.")

@tool(args_schema=CreateEventInput)
def create_event(summary: str, start_datetime: str, end_datetime: str, location: Optional[str] = None, description: Optional[str] = None) -> str:
    """Creates a new event in the primary Google Calendar."""
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        event_body = {
            'summary': summary,
            'location': location,
            'description': description,
            'start': {'dateTime': datetime.fromisoformat(start_datetime).isoformat(), 'timeZone': 'Asia/Karachi'},
            'end': {'dateTime': datetime.fromisoformat(end_datetime).isoformat(), 'timeZone': 'Asia/Karachi'},
        }
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        return f"Event created successfully: {event.get('htmlLink')}"
    except Exception as e:
        return f"An error occurred: {e}"

class UpdateEventInput(BaseModel):
    event_id: str = Field(description="The unique ID of the event to update. You must find this ID first using the search_calendar_events tool.")
    new_summary: Optional[str] = Field(None, description="The new title for the event.")
    new_start_time: Optional[str] = Field(None, description="The new start datetime in 'YYYY-MM-DD HH:MM:SS' format.")
    new_end_time: Optional[str] = Field(None, description="The new end datetime in 'YYYY-MM-DD HH:MM:SS' format.")

@tool(args_schema=UpdateEventInput)
def update_event(event_id: str, new_summary: Optional[str] = None, new_start_time: Optional[str] = None, new_end_time: Optional[str] = None) -> str:
    """Updates an existing event's details using its unique ID."""
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        event = service.events().get(calendarId='primary', eventId=event_id).execute()

        if new_summary:
            event['summary'] = new_summary
        if new_start_time:
            event['start']['dateTime'] = datetime.fromisoformat(new_start_time).isoformat()
        if new_end_time:
            event['end']['dateTime'] = datetime.fromisoformat(new_end_time).isoformat()
        
        updated_event = service.events().update(calendarId='primary', eventId=event['id'], body=event).execute()
        return f"Event updated successfully: {updated_event.get('htmlLink')}"
    except Exception as e:
        return f"An error occurred: {e}"

class DeleteEventInput(BaseModel):
    event_id: str = Field(description="The unique ID of the event to delete. You must find this ID first using the search_calendar_events tool.")

@tool(args_schema=DeleteEventInput)
def delete_event(event_id: str) -> str:
    """Deletes an event from the calendar using its unique ID."""
    creds = get_credentials()
    try:
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return f"Event with ID {event_id} was deleted successfully."
    except Exception as e:
        return f"An error occurred: {e}"