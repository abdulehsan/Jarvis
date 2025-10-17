# gmail_tools.py

import os.path
import base64
from email.mime.text import MIMEText
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import List, Optional

# --- Configuration & Setup ---
# Use the same, expanded SCOPES list as in your calendar tools.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/tasks"
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
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

# --- Helper Function for Sending Emails ---
def _create_message_body(sender, to, subject, body_text, cc=None, bcc=None):
    message = MIMEText(body_text)
    message['to'] = ', '.join(to)
    message['from'] = sender
    message['subject'] = subject
    if cc: message['cc'] = ', '.join(cc)
    if bcc: message['bcc'] = ', '.join(bcc)
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

# --- Tool Definitions ---

class SearchGmailInput(BaseModel):
    query: str = Field(description="The search query, same as Gmail's search bar. E.g., 'from:friend@example.com', 'is:unread', 'subject:Urgent'")
    max_results: int = Field(default=5, description="Maximum number of emails to return.")

@tool(args_schema=SearchGmailInput)
def search_gmail(query: str, max_results: int = 15) -> str:
    """Searches the user's Gmail inbox with a query and returns email threads with IDs and snippets."""
    creds = get_credentials()
    try:
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        if not messages: return "No emails found."
        output = []
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
            headers = msg_data['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            output.append(f"- From: {sender}\n  Subject: {subject}\n  Snippet: {msg_data['snippet']}\n  ID: {msg['id']}\n---")
        return "\n".join(output)
    except Exception as e:
        return f"An error occurred: {e}"

class GetGmailMessageInput(BaseModel):
    message_id: str = Field(description="The unique ID of the email to be read. Get this ID from the search_gmail tool.")

@tool(args_schema=GetGmailMessageInput)
def get_gmail_message(message_id: str) -> str:
    """Reads the full content of a single email using its ID."""
    creds = get_credentials()
    try:
        service = build("gmail", "v1", credentials=creds)
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        payload = message['payload']
        headers = payload['headers']
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
        body = ""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    body = base64.urlsafe_b64decode(part['body']['data'].encode('ASCII')).decode('utf-8')
                    break
        elif 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data'].encode('ASCII')).decode('utf-8')
        return f"From: {sender}\nSubject: {subject}\n\nBody:\n{body}"
    except Exception as e:
        return f"An error occurred: {e}"

class SendMessageInput(BaseModel):
    to: List[str] = Field(description="A list of recipient email addresses.")
    subject: str = Field(description="The subject of the email.")
    body: str = Field(description="The plain text body of the email.")

@tool(args_schema=SendMessageInput)
def send_gmail_message(to: List[str], subject: str, body: str) -> str:
    """Creates and sends a new email message."""
    creds = get_credentials()
    try:
        service = build("gmail", "v1", credentials=creds)
        user_email = service.users().getProfile(userId='me').execute().get('emailAddress')
        message_body = _create_message_body(user_email, to, subject, body)
        sent_message = service.users().messages().send(userId='me', body=message_body).execute()
        return f"Message sent successfully. Message ID: {sent_message['id']}"
    except Exception as e:
        return f"An error occurred: {e}"