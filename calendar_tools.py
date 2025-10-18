# calendar_tools.py

import os.path
from datetime import datetime
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import Optional

# --- Configuration & Setup ---
# Ensure this matches SCOPES in other files and add_account.py
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/tasks"
    # Add other scopes like Drive if/when needed
]
CREDENTIALS_DIR = 'credentials' # Directory for token files
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- UPDATED Authentication Function ---
def get_credentials(account_alias: str):
    """Handles loading and refreshing a specific account's credentials."""
    token_path = os.path.join(CREDENTIALS_DIR, f"{account_alias}.json")

    if not os.path.exists(token_path):
        raise FileNotFoundError(f"Credentials file not found for account alias '{account_alias}' at {token_path}. Please run add_account.py.")

    creds = None
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info(f"Refreshing expired credentials for '{account_alias}'.")
                creds.refresh(Request())
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
            else:
                raise ConnectionError(f"Credentials for '{account_alias}' are invalid and cannot be refreshed. Please re-run add_account.py for this alias.")
        return creds
    except Exception as e:
        logger.error(f"Error handling credentials for '{account_alias}': {e}")
        raise ConnectionError(f"Could not load or refresh credentials for '{account_alias}'.") from e

# --- Tool Definitions (Now Multi-Account Aware) ---

class SearchEventsInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    start_time: str = Field(description="The start of the search window in 'YYYY-MM-DD HH:MM:SS' format.")
    end_time: str = Field(description="The end of the search window in 'YYYY-MM-DD HH:MM:SS' format.")
    query: Optional[str] = Field(None, description="A text-based search query to filter events.")
    max_results: int = Field(default=10, description="Maximum number of events to return.")

@tool(args_schema=SearchEventsInput)
def search_calendar_events(account_alias: str, start_time: str, end_time: str, query: Optional[str] = None, max_results: int = 10) -> str:
    """Searches a specific Google Calendar account for events within a given time range."""
    try:
        creds = get_credentials(account_alias)
        service = build("calendar", "v3", credentials=creds)
        time_min_iso = datetime.fromisoformat(start_time).isoformat() + 'Z'
        time_max_iso = datetime.fromisoformat(end_time).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId="primary", q=query, timeMin=time_min_iso, timeMax=time_max_iso,
            maxResults=max_results, singleEvents=True, orderBy="startTime"
        ).execute()
        events = events_result.get("items", [])

        if not events: return "No events found matching your criteria."
        event_summaries = [f"- Summary: {event['summary']} | Starts: {event['start'].get('dateTime', event['start'].get('date'))} | ID: {event['id']}" for event in events]
        return "\n".join(event_summaries)
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred searching calendar for '{account_alias}': {e}"

class CreateEventInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    summary: str = Field(description="The title of the event.")
    start_datetime: str = Field(description="Start datetime in 'YYYY-MM-DD HH:MM:SS' format.")
    end_datetime: str = Field(description="End datetime in 'YYYY-MM-DD HH:MM:SS' format.")
    location: Optional[str] = Field(None, description="The location.")
    description: Optional[str] = Field(None, description="The description.")

@tool(args_schema=CreateEventInput)
def create_event(account_alias: str, summary: str, start_datetime: str, end_datetime: str, location: Optional[str] = None, description: Optional[str] = None) -> str:
    """Creates a new event in the specified Google Calendar account."""
    try:
        creds = get_credentials(account_alias)
        service = build("calendar", "v3", credentials=creds)
        timezone = 'Asia/Karachi' # Adjust timezone as needed

        event_body = {
            'summary': summary, 'location': location, 'description': description,
            'start': {'dateTime': datetime.fromisoformat(start_datetime).isoformat(), 'timeZone': timezone},
            'end': {'dateTime': datetime.fromisoformat(end_datetime).isoformat(), 'timeZone': timezone},
        }
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        return f"Event created successfully in '{account_alias}' account: {event.get('htmlLink')}"
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred creating event in '{account_alias}': {e}"

class UpdateEventInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    event_id: str = Field(description="The unique ID of the event to update. Use search_calendar_events first.")
    new_summary: Optional[str] = Field(None, description="The new title.")
    new_start_time: Optional[str] = Field(None, description="New start in 'YYYY-MM-DD HH:MM:SS' format.")
    new_end_time: Optional[str] = Field(None, description="New end in 'YYYY-MM-DD HH:MM:SS' format.")

@tool(args_schema=UpdateEventInput)
def update_event(account_alias: str, event_id: str, new_summary: Optional[str] = None, new_start_time: Optional[str] = None, new_end_time: Optional[str] = None) -> str:
    """Updates an existing event's details in a specific Google Calendar account using its unique ID."""
    try:
        creds = get_credentials(account_alias)
        service = build("calendar", "v3", credentials=creds)
        event = service.events().get(calendarId='primary', eventId=event_id).execute()

        if new_summary: event['summary'] = new_summary
        if new_start_time: event['start']['dateTime'] = datetime.fromisoformat(new_start_time).isoformat()
        if new_end_time: event['end']['dateTime'] = datetime.fromisoformat(new_end_time).isoformat()
        
        updated_event = service.events().update(calendarId='primary', eventId=event['id'], body=event).execute()
        return f"Event updated successfully in '{account_alias}' account: {updated_event.get('htmlLink')}"
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred updating event in '{account_alias}': {e}"

class DeleteEventInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    event_id: str = Field(description="The unique ID of the event to delete. Use search_calendar_events first.")

@tool(args_schema=DeleteEventInput)
def delete_event(account_alias: str, event_id: str) -> str:
    """Deletes an event from a specific Google Calendar account using its unique ID."""
    try:
        creds = get_credentials(account_alias)
        service = build("calendar", "v3", credentials=creds)
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return f"Event with ID {event_id} deleted successfully from '{account_alias}' account."
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred deleting event from '{account_alias}': {e}"