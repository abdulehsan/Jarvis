# tasks_tools.py

import os.path
import logging

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import Optional

# --- Configuration & Setup ---
# Ensure this SCOPES list matches ALL other tool files and add_account.py
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify", # Needed for trash_gmail_message
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

# =============================================
# ===        Task List Management Tools     ===
# =============================================

# MODIFIED: Added account_alias
class ListTaskListsInput(BaseModel):
     account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")

@tool(args_schema=ListTaskListsInput)
def list_task_lists(account_alias: str) -> str:
    """Lists all task lists for a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        results = service.tasklists().list(maxResults=25).execute()
        items = results.get("items", [])
        if not items: return f"No task lists found for account '{account_alias}'."
        return "\n".join([f"- Title: {item['title']} (ID: {item['id']})" for item in items])
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred listing task lists for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class GetTaskListInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The unique ID of the task list to retrieve.")

@tool(args_schema=GetTaskListInput)
def get_task_list(account_alias: str, task_list_id: str) -> str:
    """Retrieves a single task list by its ID from a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        result = service.tasklists().get(tasklist=task_list_id).execute()
        return f"Task List Found in '{account_alias}': {result['title']} (ID: {result['id']})"
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred getting task list for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class CreateTaskListInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    title: str = Field(description="The title of the new task list.")

@tool(args_schema=CreateTaskListInput)
def create_task_list(account_alias: str, title: str) -> str:
    """Creates a new task list in a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        result = service.tasklists().insert(body={'title': title}).execute()
        return f"Task list '{result['title']}' created successfully in '{account_alias}' with ID: {result['id']}"
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred creating task list for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class UpdateTaskListInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The ID of the task list to update.")
    new_title: str = Field(description="The new title for the task list.")

@tool(args_schema=UpdateTaskListInput)
def update_task_list(account_alias: str, task_list_id: str, new_title: str) -> str:
    """Updates the title of an existing task list in a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        result = service.tasklists().patch(tasklist=task_list_id, body={'title': new_title}).execute()
        return f"Task list in '{account_alias}' updated to '{result['title']}'."
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred updating task list for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class DeleteTaskListInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The unique ID of the task list to delete.")

@tool(args_schema=DeleteTaskListInput)
def delete_task_list(account_alias: str, task_list_id: str) -> str:
    """Permanently deletes an entire task list from a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        service.tasklists().delete(tasklist=task_list_id).execute()
        return f"Task list with ID {task_list_id} was deleted successfully from '{account_alias}'."
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred deleting task list for '{account_alias}': {e}"

# =============================================
# ===      Individual Task Management Tools   ===
# =============================================

# MODIFIED: Added account_alias
class GetTasksInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The ID of the task list.")
    show_completed: bool = Field(default=False, description="Set True to include completed tasks.")

@tool(args_schema=GetTasksInput)
def get_tasks(account_alias: str, task_list_id: str, show_completed: bool = False) -> str:
    """Gets all tasks and subtasks from a specific list in a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        results = service.tasks().list(tasklist=task_list_id, showCompleted=show_completed, maxResults=100).execute()
        items = results.get("items", [])
        if not items: return f"No tasks found in list ID {task_list_id} for account '{account_alias}'."
        # Logic to display subtasks correctly
        tasks_with_subtasks = {item['id']: {'task': item, 'subtasks': []} for item in items if 'parent' not in item}
        for item in items:
            if 'parent' in item and item['parent'] in tasks_with_subtasks:
                tasks_with_subtasks[item['parent']]['subtasks'].append(item)
        output = []
        for task_id, data in tasks_with_subtasks.items():
            task = data['task']
            status = '[x]' if task.get('status') == 'completed' else '[ ]'
            output.append(f"- {status} {task['title']} (ID: {task['id']})")
            for subtask in data['subtasks']:
                sub_status = '[x]' if subtask.get('status') == 'completed' else '[ ]'
                output.append(f"  - {sub_status} {subtask['title']} (ID: {subtask['id']})")
        return "\n".join(output)
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred getting tasks for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class GetTaskInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The ID of the list containing the task.")
    task_id: str = Field(description="The unique ID of the task to retrieve.")

@tool(args_schema=GetTaskInput)
def get_task(account_alias: str, task_list_id: str, task_id: str) -> str:
    """Retrieves a single task by its ID from a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        result = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
        return f"Title: {result.get('title')}\nNotes: {result.get('notes', 'No notes.')}\nStatus: {result.get('status')}"
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred getting task for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class CreateTaskInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The ID of the task list.")
    title: str = Field(description="The title of the task.")
    notes: Optional[str] = Field(None, description="Additional notes.")
    parent_task_id: Optional[str] = Field(None, description="The ID of the parent task for subtask.")

@tool(args_schema=CreateTaskInput)
def create_task(account_alias: str, task_list_id: str, title: str, notes: Optional[str] = None, parent_task_id: Optional[str] = None) -> str:
    """Creates a new task or subtask in a specified list for a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        task_body = {"title": title, "notes": notes, "status": "needsAction"}
        result = service.tasks().insert(tasklist=task_list_id, parent=parent_task_id, body=task_body).execute()
        return f"Task '{result['title']}' created successfully in '{account_alias}'."
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred creating task for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class UpdateTaskInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The ID of the list.")
    task_id: str = Field(description="The ID of the task to update.")
    new_title: Optional[str] = Field(None, description="The new title.")
    new_notes: Optional[str] = Field(None, description="The new notes.")

@tool(args_schema=UpdateTaskInput)
def update_task(account_alias: str, task_list_id: str, task_id: str, new_title: Optional[str] = None, new_notes: Optional[str] = None) -> str:
    """Updates the title or notes of a specific task in a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        task = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
        if new_title: task['title'] = new_title
        if new_notes: task['notes'] = new_notes
        result = service.tasks().update(tasklist=task_list_id, task=task_id, body=task).execute()
        return f"Task '{result['title']}' in '{account_alias}' was updated successfully."
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred updating task for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class CompleteTaskInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The ID of the list.")
    task_id: str = Field(description="The ID of the task to complete.")

@tool(args_schema=CompleteTaskInput)
def complete_task(account_alias: str, task_list_id: str, task_id: str) -> str:
    """Marks a specific task as completed in a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        result = service.tasks().patch(tasklist=task_list_id, task=task_id, body={"status": "completed"}).execute()
        return f"Task '{result['title']}' in '{account_alias}' marked as complete."
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred completing task for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class DeleteTaskInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The ID of the list.")
    task_id: str = Field(description="The ID of the task to delete.")

@tool(args_schema=DeleteTaskInput)
def delete_task(account_alias: str, task_list_id: str, task_id: str) -> str:
    """Permanently deletes a specific task from a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        service.tasks().delete(tasklist=task_list_id, task=task_id).execute()
        return f"Task with ID {task_id} deleted successfully from '{account_alias}'."
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred deleting task for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class MoveTaskInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The ID of the list.")
    task_id: str = Field(description="The ID of the task to move.")
    parent_id: Optional[str] = Field(None, description="New parent task ID for subtask.")
    previous_id: Optional[str] = Field(None, description="Task ID to place this task after.")

@tool(args_schema=MoveTaskInput)
def move_task(account_alias: str, task_list_id: str, task_id: str, parent_id: Optional[str] = None, previous_id: Optional[str] = None) -> str:
    """Moves a task to a different position or makes it a subtask in a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        service.tasks().move(tasklist=task_list_id, task=task_id, parent=parent_id, previous=previous_id).execute()
        return f"Task with ID {task_id} in '{account_alias}' was moved successfully."
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred moving task for '{account_alias}': {e}"

# MODIFIED: Added account_alias
class ClearCompletedTasksInput(BaseModel):
    account_alias: str = Field(description="The alias of the Google account to use (e.g., 'personal', 'student').")
    task_list_id: str = Field(description="The ID of the task list to clear.")

@tool(args_schema=ClearCompletedTasksInput)
def clear_completed_tasks(account_alias: str, task_list_id: str) -> str:
    """Permanently deletes all completed tasks from a specific list in a specific Google account."""
    try:
        creds = get_credentials(account_alias)
        service = build("tasks", "v1", credentials=creds)
        service.tasks().clear(tasklist=task_list_id).execute()
        return f"All completed tasks from list ID {task_list_id} in '{account_alias}' have been cleared."
    except FileNotFoundError as e: return str(e)
    except ConnectionError as e: return str(e)
    except Exception as e: return f"An error occurred clearing tasks for '{account_alias}': {e}"