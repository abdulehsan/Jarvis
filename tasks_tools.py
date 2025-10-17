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
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

# =============================================
# ===        Task List Management Tools     ===
# =============================================

@tool
def list_task_lists() -> str:
    """Lists all the user's task lists with their corresponding IDs."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        results = service.tasklists().list(maxResults=25).execute()
        items = results.get("items", [])
        if not items: return "No task lists found."
        return "\n".join([f"- Title: {item['title']} (ID: {item['id']})" for item in items])
    except Exception as e:
        return f"An error occurred: {e}"

class GetTaskListInput(BaseModel):
    task_list_id: str = Field(description="The unique ID of the task list to retrieve. Use list_task_lists to find this ID.")

@tool(args_schema=GetTaskListInput)
def get_task_list(task_list_id: str) -> str:
    """Retrieves a single task list by its ID."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        result = service.tasklists().get(tasklist=task_list_id).execute()
        return f"Task List Found: {result['title']} (ID: {result['id']})"
    except Exception as e:
        return f"An error occurred: {e}"

class CreateTaskListInput(BaseModel):
    title: str = Field(description="The title of the new task list to create.")

@tool(args_schema=CreateTaskListInput)
def create_task_list(title: str) -> str:
    """Creates a new task list."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        result = service.tasklists().insert(body={'title': title}).execute()
        return f"Task list '{result['title']}' created successfully with ID: {result['id']}"
    except Exception as e:
        return f"An error occurred: {e}"

class UpdateTaskListInput(BaseModel):
    task_list_id: str = Field(description="The ID of the task list to update.")
    new_title: str = Field(description="The new title for the task list.")

@tool(args_schema=UpdateTaskListInput)
def update_task_list(task_list_id: str, new_title: str) -> str:
    """Updates the title of an existing task list."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        tasklist_body = {'title': new_title}
        result = service.tasklists().patch(tasklist=task_list_id, body=tasklist_body).execute()
        return f"Task list updated to '{result['title']}'."
    except Exception as e:
        return f"An error occurred: {e}"

class DeleteTaskListInput(BaseModel):
    task_list_id: str = Field(description="The unique ID of the task list to delete. Use list_task_lists to find this ID.")

@tool(args_schema=DeleteTaskListInput)
def delete_task_list(task_list_id: str) -> str:
    """Permanently deletes an entire task list. This action cannot be undone."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        service.tasklists().delete(tasklist=task_list_id).execute()
        return f"Task list with ID {task_list_id} was deleted successfully."
    except Exception as e:
        return f"An error occurred: {e}"

# =============================================
# ===      Individual Task Management Tools   ===
# =============================================

class GetTasksInput(BaseModel):
    task_list_id: str = Field(description="The ID of the task list. Use list_task_lists to find this ID.")
    show_completed: bool = Field(default=False, description="Set to True to include completed tasks.")

@tool(args_schema=GetTasksInput)
def get_tasks(task_list_id: str, show_completed: bool = False) -> str:
    """Gets all tasks and subtasks from a specific list, including their unique IDs."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        results = service.tasks().list(tasklist=task_list_id, showCompleted=show_completed, maxResults=100).execute()
        items = results.get("items", [])
        if not items: return "No tasks found in this list."
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
    except Exception as e:
        return f"An error occurred: {e}"

class GetTaskInput(BaseModel):
    task_list_id: str = Field(description="The ID of the list containing the task.")
    task_id: str = Field(description="The unique ID of the task to retrieve. Use get_tasks to find this ID.")

@tool(args_schema=GetTaskInput)
def get_task(task_list_id: str, task_id: str) -> str:
    """Retrieves a single task by its ID, including its notes."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        result = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
        return f"Title: {result.get('title')}\nNotes: {result.get('notes', 'No notes.')}\nStatus: {result.get('status')}"
    except Exception as e:
        return f"An error occurred: {e}"

class CreateTaskInput(BaseModel):
    task_list_id: str = Field(description="The ID of the task list where the task will be added.")
    title: str = Field(description="The title of the task.")
    notes: Optional[str] = Field(None, description="Additional notes for the task.")
    parent_task_id: Optional[str] = Field(None, description="The ID of the parent task to make this a subtask.")

@tool(args_schema=CreateTaskInput)
def create_task(task_list_id: str, title: str, notes: Optional[str] = None, parent_task_id: Optional[str] = None) -> str:
    """Creates a new task or subtask in a specified task list."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        task_body = {"title": title, "notes": notes, "status": "needsAction"}
        result = service.tasks().insert(tasklist=task_list_id, parent=parent_task_id, body=task_body).execute()
        return f"Task '{result['title']}' created successfully."
    except Exception as e:
        return f"An error occurred: {e}"

class UpdateTaskInput(BaseModel):
    task_list_id: str = Field(description="The ID of the list containing the task.")
    task_id: str = Field(description="The ID of the task to update. Use get_tasks to find this ID.")
    new_title: Optional[str] = Field(None, description="The new title for the task.")
    new_notes: Optional[str] = Field(None, description="The new notes for the task.")

@tool(args_schema=UpdateTaskInput)
def update_task(task_list_id: str, task_id: str, new_title: Optional[str] = None, new_notes: Optional[str] = None) -> str:
    """Updates the title or notes of a specific task."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        task = service.tasks().get(tasklist=task_list_id, task=task_id).execute()
        if new_title: task['title'] = new_title
        if new_notes: task['notes'] = new_notes
        result = service.tasks().update(tasklist=task_list_id, task=task_id, body=task).execute()
        return f"Task '{result['title']}' was updated successfully."
    except Exception as e:
        return f"An error occurred: {e}"

class CompleteTaskInput(BaseModel):
    task_list_id: str = Field(description="The ID of the list containing the task.")
    task_id: str = Field(description="The ID of the task to mark as complete. Use get_tasks to find this ID.")

@tool(args_schema=CompleteTaskInput)
def complete_task(task_list_id: str, task_id: str) -> str:
    """Marks a specific task as completed."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        result = service.tasks().patch(tasklist=task_list_id, task=task_id, body={"status": "completed"}).execute()
        return f"Task '{result['title']}' marked as complete."
    except Exception as e:
        return f"An error occurred: {e}"

class DeleteTaskInput(BaseModel):
    task_list_id: str = Field(description="The ID of the list containing the task.")
    task_id: str = Field(description="The ID of the task to delete. Use get_tasks to find this ID.")

@tool(args_schema=DeleteTaskInput)
def delete_task(task_list_id: str, task_id: str) -> str:
    """Permanently deletes a specific task."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        service.tasks().delete(tasklist=task_list_id, task=task_id).execute()
        return f"Task with ID {task_id} deleted successfully."
    except Exception as e:
        return f"An error occurred: {e}"

class MoveTaskInput(BaseModel):
    task_list_id: str = Field(description="The ID of the list containing the task.")
    task_id: str = Field(description="The ID of the task to move.")
    parent_id: Optional[str] = Field(None, description="The ID of the new parent task. If omitted, the task becomes a top-level task.")
    previous_id: Optional[str] = Field(None, description="The ID of the task that the moved task should be placed after. If omitted, it's placed at the top.")

@tool(args_schema=MoveTaskInput)
def move_task(task_list_id: str, task_id: str, parent_id: Optional[str] = None, previous_id: Optional[str] = None) -> str:
    """Moves a task to a different position in the list or makes it a subtask."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        service.tasks().move(tasklist=task_list_id, task=task_id, parent=parent_id, previous=previous_id).execute()
        return f"Task with ID {task_id} was moved successfully."
    except Exception as e:
        return f"An error occurred: {e}"

class ClearCompletedTasksInput(BaseModel):
    task_list_id: str = Field(description="The ID of the task list from which to clear all completed tasks.")

@tool(args_schema=ClearCompletedTasksInput)
def clear_completed_tasks(task_list_id: str) -> str:
    """Permanently deletes all completed tasks from a specific list."""
    creds = get_credentials()
    try:
        service = build("tasks", "v1", credentials=creds)
        service.tasks().clear(tasklist=task_list_id).execute()
        return f"All completed tasks from list ID {task_list_id} have been cleared."
    except Exception as e:
        return f"An error occurred: {e}"