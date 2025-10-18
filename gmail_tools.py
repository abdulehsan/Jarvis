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
# Ensure this SCOPES list includes all necessary permissions and matches other tool files
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly", # Search, Read
    "https://www.googleapis.com/auth/gmail.compose", # Send, Draft
    "https://www.googleapis.com/auth/gmail.modify", # Trash/Modify (needed for trash)
    "https://www.googleapis.com/auth/tasks"
    # Add other scopes like Drive if/when needed
]
CREDENTIALS_DIR = 'credentials' # Directory for token files
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- UPDATED Authentication Function ---
def get_credentials(account_alias: str):
    """Handles loading and refreshing a specific account's credentials, adapting path for Render."""
    
    # Check if running on Render (Render sets this env var automatically)
    is_on_render = os.getenv('RENDER') == 'true'
    
    if is_on_render:
        # On Render, secret files are at the root
        token_path = f"{account_alias}.json"
        logger.info(f"Running on Render, looking for token at: {token_path}")
    else:
        # Locally, look inside the credentials directory
        token_path = os.path.join('credentials', f"{account_alias}.json")
        logger.info(f"Running locally, looking for token at: {token_path}")

    if not os.path.exists(token_path):
        # Check if the credentials.json exists (common setup error)
        if not os.path.exists("credentials.json"):
             raise FileNotFoundError("Main credentials.json not found. Cannot proceed.")
        # Specific error if the alias token is missing
        error_message = (f"Credentials file not found for alias '{account_alias}' at expected path: {token_path}. "
                         f"Ensure the secret file '{account_alias}.json' exists on Render or run add_account.py locally.")
        raise FileNotFoundError(error_message)

    creds = None
    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info(f"Refreshing expired credentials for '{account_alias}'.")
                creds.refresh(Request())
                # Save refreshed token back to the file (works locally and on Render's disk)
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
            else:
                raise ConnectionError(f"Credentials for '{account_alias}' are invalid/expired and cannot be refreshed. Please re-run add_account.py for this alias locally and re-upload the token.")
        return creds
    except Exception as e:
        logger.error(f"Error handling credentials for '{account_alias}' at {token_path}: {e}")
        raise ConnectionError(f"Could not load or refresh credentials for '{account_alias}'. Details: {e}") from e
# --- Helper Function for Sending Emails ---
def _create_message_body(sender, to, subject, body_text, cc=None, bcc=None):
    message = MIMEText(body_text)
    message['to'] = ', '.join(to)
    message['from'] = sender
    message['subject'] = subject
    if cc: message['cc'] = ', '.join(cc)
    if bcc: message['bcc'] = ', '.join(bcc)
    # Ensure correct encoding for Gmail API raw format
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')}

# --- Tool Definitions (Multi-Account Aware) ---

class SearchGmailInput(BaseModel):
    account_alias: str = Field(description="The alias of the Gmail account to search (e.g., 'personal', 'student').")
    query: str = Field(description="The search query, same as Gmail's search bar. E.g., 'from:friend@example.com', 'is:unread'")
    max_results: int = Field(default=10, description="Maximum number of emails to return.")

@tool(args_schema=SearchGmailInput)
def search_gmail(account_alias: str, query: str, max_results: int = 10) -> str:
    """Searches a specific Gmail account with a query and returns email threads with IDs and snippets."""
    try:
        creds = get_credentials(account_alias)
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        if not messages: return "No emails found matching your query."

        output = []
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
            headers = msg_data.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
            output.append(f"- From: {sender}\n  Subject: {subject}\n  Snippet: {msg_data.get('snippet', '')}\n  ID: {msg['id']}\n---")
        return "\n".join(output)
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred searching Gmail for '{account_alias}': {e}"

class GetGmailMessageInput(BaseModel):
    account_alias: str = Field(description="The alias of the Gmail account to use (e.g., 'personal', 'student').")
    message_id: str = Field(description="The unique ID of the email to be read. Get this ID from the search_gmail tool.")

@tool(args_schema=GetGmailMessageInput)
def get_gmail_message(account_alias: str, message_id: str) -> str:
    """Reads the full content of a single email from a specific Gmail account using its ID."""
    try:
        creds = get_credentials(account_alias)
        service = build("gmail", "v1", credentials=creds)
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        payload = message.get('payload', {})
        headers = payload.get('headers', [])
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')

        body = ""
        # Handle different email structures (plain text, multipart)
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain' and 'data' in part.get('body', {}):
                    body_data = part['body']['data']
                    body = base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8', errors='replace')
                    break # Found plain text body
        elif 'data' in payload.get('body', {}):
            body_data = payload['body']['data']
            body = base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8', errors='replace')

        return f"From: {sender}\nSubject: {subject}\n\nBody:\n{body if body else '[No plain text body found or email format not supported]'}"
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred getting message from '{account_alias}': {e}"

class SendMessageInput(BaseModel):
    account_alias: str = Field(description="The alias of the Gmail account to send from (e.g., 'personal', 'student').")
    to: List[str] = Field(description="A list of recipient email addresses.")
    subject: str = Field(description="The subject of the email.")
    body: str = Field(description="The plain text body of the email.")
    cc: Optional[List[str]] = Field(None, description="A list of CC recipient email addresses.")
    bcc: Optional[List[str]] = Field(None, description="A list of BCC recipient email addresses.")

@tool(args_schema=SendMessageInput)
def send_gmail_message(account_alias: str, to: List[str], subject: str, body: str, cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None) -> str:
    """Creates and sends a new email message from a specific Gmail account."""
    try:
        creds = get_credentials(account_alias)
        service = build("gmail", "v1", credentials=creds)
        user_email = service.users().getProfile(userId='me').execute().get('emailAddress')
        if not user_email: return f"Error: Could not retrieve email address for account '{account_alias}'."

        message_body = _create_message_body(user_email, to, subject, body, cc, bcc)
        sent_message = service.users().messages().send(userId='me', body=message_body).execute()
        return f"Message sent successfully from '{account_alias}'. Message ID: {sent_message.get('id')}"
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred sending message from '{account_alias}': {e}"

# NEW: Create Draft Tool
@tool(args_schema=SendMessageInput) # Reuses the same input schema as send_gmail_message
def create_gmail_draft(account_alias: str, to: List[str], subject: str, body: str, cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None) -> str:
    """Creates a new email draft in a specific Gmail account but does not send it."""
    try:
        creds = get_credentials(account_alias)
        service = build("gmail", "v1", credentials=creds)
        user_email = service.users().getProfile(userId='me').execute().get('emailAddress')
        if not user_email: return f"Error: Could not retrieve email address for account '{account_alias}'."

        message_body = _create_message_body(user_email, to, subject, body, cc, bcc)
        draft = {'message': message_body}
        created_draft = service.users().drafts().create(userId='me', body=draft).execute()
        return f"Draft created successfully in '{account_alias}'. Draft ID: {created_draft.get('id')}"
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred creating draft in '{account_alias}': {e}"

# NEW: Trash Message Tool
class TrashMessageInput(BaseModel):
    account_alias: str = Field(description="The alias of the Gmail account to use (e.g., 'personal', 'student').")
    message_id: str = Field(description="The unique ID of the email message to move to trash. Use search_gmail first.")

@tool(args_schema=TrashMessageInput)
def trash_gmail_message(account_alias: str, message_id: str) -> str:
    """Moves a specific email message to the trash in a specific Gmail account."""
    try:
        creds = get_credentials(account_alias)
        service = build("gmail", "v1", credentials=creds)
        # Using trash instead of delete is safer as it's recoverable
        service.users().messages().trash(userId='me', id=message_id).execute()
        return f"Message with ID {message_id} moved to trash in '{account_alias}' account."
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred trashing message in '{account_alias}': {e}"