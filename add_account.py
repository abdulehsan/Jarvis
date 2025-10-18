# add_account.py
import os
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request # Needed for potential refresh

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define ALL the scopes your application will EVER need across ALL accounts.
# This ensures the generated token has permission for everything.
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/tasks",
    # Add any other scopes you plan to use (Drive, Classroom, etc.) here
    # "https://www.googleapis.com/auth/drive",
    # "https://www.googleapis.com/auth/classroom.announcements.readonly", etc.
]
CREDENTIALS_DIR = 'credentials' # Folder to store token files

def main():
    """Runs the authentication flow for a new account and saves its token."""
    logger.info("--- Starting Google Authentication for a New Account ---")

    # Ensure the main Google Cloud credentials file exists
    if not os.path.exists("credentials.json"):
        logger.error("FATAL: credentials.json not found.")
        logger.error("Please download your OAuth 2.0 Client ID JSON file from the Google Cloud Console")
        logger.error("and ensure it's named 'credentials.json' in this directory.")
        return

    # Ensure the directory for storing tokens exists
    if not os.path.exists(CREDENTIALS_DIR):
        os.makedirs(CREDENTIALS_DIR)
        logger.info(f"Created directory: {CREDENTIALS_DIR}")

    # Get a unique alias for this account
    account_alias = input("Enter a short, unique alias for this account (e.g., 'personal', 'student', 'work1'): ").strip().lower().replace(" ", "_")
    if not account_alias:
        logger.error("Account alias cannot be empty.")
        return

    token_path = os.path.join(CREDENTIALS_DIR, f"{account_alias}.json")

    # Check if a token for this alias already exists
    if os.path.exists(token_path):
        logger.warning(f"A token file already exists for alias '{account_alias}' at {token_path}.")
        overwrite = input("Do you want to overwrite it? (yes/no): ").strip().lower()
        if overwrite != 'yes':
            logger.info("Aborting authentication.")
            return
        else:
            logger.info(f"Proceeding to overwrite {token_path}.")

    creds = None
    try:
        # Initiate the OAuth flow using the main credentials.json
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        # This will open the browser for the user to log in and grant consent
        creds = flow.run_local_server(port=0)

    except Exception as e:
        logger.error(f"Failed to complete the OAuth flow: {e}")
        return

    if creds:
        # Save the obtained credentials to the specific alias file
        try:
            with open(token_path, "w") as token:
                token.write(creds.to_json())
            logger.info(f"✅ Successfully authenticated and saved credentials for '{account_alias}' to: {token_path}")
        except Exception as e:
            logger.error(f"Failed to save the token file: {e}")
    else:
        logger.error("❌ Authentication failed. Could not obtain credentials.")

if __name__ == "__main__":
    main()