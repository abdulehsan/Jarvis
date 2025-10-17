# keep_tools.py

import os
import gkeepapi
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import Optional

# --- Global Instance to Maintain Session ---
# This avoids logging in for every single tool call.
_keep_instance = None

# --- UPDATED Authentication Function ---
def get_keep_instance():
    """Initializes and authenticates with gkeepapi using a Master Key."""
    global _keep_instance
    if _keep_instance is None:
        # These must now be set as environment variables
        email = os.getenv("GKEEP_EMAIL")
        master_key = os.getenv("GKEEP_MASTER_KEY") # We now use the Master Key

        if not email or not master_key:
            raise ValueError("GKEEP_EMAIL and GKEEP_MASTER_KEY environment variables must be set.")

        keep = gkeepapi.Keep()
        try:
            # Use the new, more reliable authentication method
            keep.authenticate(email, master_key)
            _keep_instance = keep
        except gkeepapi.exception.LoginException as e:
            raise ConnectionError(f"Failed to authenticate with Google Keep. Check your Master Key. Error: {e}")
    
    # Syncs the library with the latest state of your Keep notes
    _keep_instance.sync()
    return _keep_instance

# --- Tool Definitions (No changes needed below this line) ---

@tool
def list_notes() -> str:
    """Lists the user's most recent notes from Google Keep, including their unique IDs."""
    keep = get_keep_instance()
    notes = keep.all()
    if not notes:
        return "No notes found in Google Keep."
    return "\n".join([f"- Title: {note.title or 'Untitled Note'} (ID: {note.id})" for note in notes])

class GetNoteInput(BaseModel):
    note_id: str = Field(description="The unique ID of the note to retrieve. Use list_notes to find this ID.")

@tool(args_schema=GetNoteInput)
def get_note(note_id: str) -> str:
    """Retrieves the full content of a single Google Keep note by its ID."""
    keep = get_keep_instance()
    note = keep.get(note_id)
    if not note:
        return f"No note found with ID: {note_id}"
    return f"Title: {note.title}\n\nContent:\n{note.text}"

class CreateNoteInput(BaseModel):
    title: str = Field(description="The title for the new note.")
    body_text: Optional[str] = Field(None, description="The main text content of the note.")

@tool(args_schema=CreateNoteInput)
def create_note(title: str, body_text: Optional[str] = None) -> str:
    """Creates a new note in Google Keep."""
    keep = get_keep_instance()
    new_note = keep.createNote(title, body_text or "")
    keep.sync() # Sync to confirm creation
    return f"Note '{new_note.title}' created successfully with ID: {new_note.id}"

class DeleteNoteInput(BaseModel):
    note_id: str = Field(description="The unique ID of the note to delete. Use list_notes to find this ID.")

@tool(args_schema=DeleteNoteInput)
def delete_note(note_id: str) -> str:
    """Finds a note by its ID and deletes it."""
    keep = get_keep_instance()
    note_to_delete = keep.get(note_id)
    if not note_to_delete:
        return f"No note found with ID: {note_id} to delete."
    
    note_title = note_to_delete.title
    note_to_delete.delete()
    keep.sync() # Sync to confirm deletion
    return f"Note '{note_title}' was deleted successfully."