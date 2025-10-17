# keep_tools.py

import os.path
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, MediaIoBaseDownload
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import Optional, List
import io

# --- Configuration & Setup ---
# We add the new Keep scope. Readonly is safer to start.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/keep.readonly", # NEW: To read notes
    "https://www.googleapis.com/auth/keep"          # NEW: To create/delete/share notes
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
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

# =============================================
# ===        Note Management Tools          ===
# =============================================

@tool
def list_notes() -> str:
    """Lists the user's most recent notes from Google Keep."""
    creds = get_credentials()
    try:
        service = build("keep", "v1", credentials=creds)
        results = service.notes().list().execute()
        notes = results.get("notes", [])
        if not notes:
            return "No notes found in Google Keep."
        # The note name is the unique ID, e.g., 'notes/12345'
        return "\n".join([f"- Title: {note.get('title', 'Untitled Note')}, ID: {note.get('name')}" for note in notes])
    except Exception as e:
        return f"An error occurred: {e}"

class GetNoteInput(BaseModel):
    note_id: str = Field(description="The unique ID of the note to retrieve, e.g., 'notes/12345'. Use list_notes to find this ID.")

@tool(args_schema=GetNoteInput)
def get_note(note_id: str) -> str:
    """Retrieves the full content of a single note by its ID."""
    creds = get_credentials()
    try:
        service = build("keep", "v1", credentials=creds)
        note = service.notes().get(name=note_id).execute()
        title = note.get('title', 'Untitled Note')
        content = ""
        if 'body' in note and 'text' in note['body']:
            content = note['body']['text']['text']
        return f"Title: {title}\n\nContent:\n{content}"
    except Exception as e:
        return f"An error occurred: {e}"

class CreateNoteInput(BaseModel):
    title: str = Field(description="The title for the new note.")
    body_text: Optional[str] = Field(None, description="The main text content of the note.")

@tool(args_schema=CreateNoteInput)
def create_note(title: str, body_text: Optional[str] = None) -> str:
    """Creates a new note in Google Keep."""
    creds = get_credentials()
    try:
        service = build("keep", "v1", credentials=creds)
        note_body = {
            "title": title,
            "body": {
                "text": {
                    "text": body_text or ""
                }
            }
        }
        note = service.notes().create(body=note_body).execute()
        return f"Note '{note.get('title')}' created successfully with ID: {note.get('name')}"
    except Exception as e:
        return f"An error occurred: {e}"

class DeleteNoteInput(BaseModel):
    note_id: str = Field(description="The unique ID of the note to delete, e.g., 'notes/12345'.")

@tool(args_schema=DeleteNoteInput)
def delete_note(note_id: str) -> str:
    """Permanently deletes a note by its ID."""
    creds = get_credentials()
    try:
        service = build("keep", "v1", credentials=creds)
        service.notes().delete(name=note_id).execute()
        return f"Note with ID {note_id} was deleted successfully."
    except Exception as e:
        return f"An error occurred: {e}"

# =============================================
# ===      Permission Management Tools      ===
# =============================================

class ShareNoteInput(BaseModel):
    note_id: str = Field(description="The unique ID of the note to share, e.g., 'notes/12345'.")
    email_address: str = Field(description="The email address of the user to share the note with.")
    role: str = Field(default="WRITER", description="The role to grant. Can be 'READER' or 'WRITER'. Defaults to 'WRITER'.")

@tool(args_schema=ShareNoteInput)
def share_note(note_id: str, email_address: str, role: str = "WRITER") -> str:
    """Shares a note with another user."""
    creds = get_credentials()
    try:
        service = build("keep", "v1", credentials=creds)
        permission_body = {
            "type": "USER",
            "role": role.upper(),
            "email": email_address
        }
        # The parent is the note itself
        service.notes().permissions().batchCreate(parent=note_id, body={'requests': [{'createPermission': permission_body}]}).execute()
        return f"Note {note_id} shared successfully with {email_address} as a {role.upper()}."
    except Exception as e:
        return f"An error occurred: {e}"