from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
from dotenv import load_dotenv
import shelve
from datetime import date

# --- LangChain and Tool imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory

# Import ALL tools from ALL toolkits
from calendar_tools import search_calendar_events, create_event, update_event, delete_event
from gmail_tools import search_gmail, get_gmail_message, send_gmail_message, create_gmail_draft, trash_gmail_message
from tasks_tools import (
    list_task_lists, get_task_list, create_task_list, update_task_list, delete_task_list,
    get_tasks, get_task, create_task, update_task, complete_task, delete_task,
    move_task, clear_completed_tasks
)
# Corrected import name for keep tools
from gkeep_tools import list_notes, get_note, create_note, delete_note

# --- Initialize App ---
app = Flask(__name__)
load_dotenv()

# --- Persistent Memory Management ---
def get_user_memory(session_id):
    with shelve.open("conversation_db", flag='c') as db:
        return db.get(session_id, ConversationBufferMemory(memory_key="chat_history", return_messages=True))

def save_user_memory(session_id, memory):
    with shelve.open("conversation_db", flag='c') as db:
        db[session_id] = memory

# --- Agent Setup ---
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY")) # Switched to gemini-pro for potentially better reasoning

# Define the master list of all tools
tools = [
    # Calendar
    search_calendar_events, create_event, update_event, delete_event,
    # Gmail
    search_gmail, get_gmail_message, send_gmail_message, create_gmail_draft, trash_gmail_message,
    # Tasks
    list_task_lists, get_task_list, create_task_list, update_task_list, delete_task_list,
    get_tasks, get_task, create_task, update_task, complete_task, delete_task,
    move_task, clear_completed_tasks,
    # Keep (Note: Keep tools remain single-account due to gkeepapi limitations)
    list_notes, get_note, create_note, delete_note
]

# --- MODIFIED: System Prompt now includes account aliases ---
# Define your available account aliases here
AVAILABLE_ALIASES = ['personal', 'student', 'work', 'casual']
aliases_string = ", ".join(AVAILABLE_ALIASES)

base_prompt = ChatPromptTemplate.from_messages([
    ("system", f"""You are Jarvis, a proactive and highly intelligent personal assistant.

Your primary capability is your powerful language model. Use it for general queries, writing, brainstorming etc.

You also have special tools to interact with the user's Google services (Calendar, Gmail, Tasks) and Google Keep (via gkeepapi).

**CRITICAL RULES FOR GOOGLE SERVICE TOOLS (Calendar, Gmail, Tasks):**
1. These tools require an 'account_alias' to specify which user account to act upon.
2. The available account aliases are: **{aliases_string}**.
3. **If the user's request clearly specifies an account alias**, use that alias when calling the tool.
4. **If the user's request DOES NOT specify an account alias**, you MUST ask the user clarifying question: "Which account should I use for that ({aliases_string})?". Do NOT attempt to call the tool without an alias unless the user provides one.
5. Google Keep tools do NOT require an account alias as they connect to a single pre-configured account.

General Rules:
- Be concise and conversational. Do not expose tool names or internal processes.
- The current date is {{current_date}}.
"""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

@app.route("/webhook", methods=['POST'])
def webhook():
    """Handles incoming Twilio messages and interacts with the agent."""
    incoming_msg = request.values.get('Body', '').strip()
    sender_id = request.values.get('From', '')

    print(f"Received message '{incoming_msg}' from {sender_id}")

    memory = get_user_memory(sender_id)

    try:
        current_date_str = date.today().isoformat()
        prompt_with_date = base_prompt.partial(current_date=current_date_str)

        agent = create_tool_calling_agent(llm, tools, prompt_with_date)
        # Handle cases where the agent might need to ask for the alias
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            memory=memory,
            verbose=True,
            handle_parsing_errors=True # Helps if the LLM messes up arguments slightly
        )

        result = agent_executor.invoke({"input": incoming_msg})
        agent_response = result["output"]

    except Exception as e:
        print(f"An error occurred: {e}")
        agent_response = "Sorry, I encountered an error. Please try that again."

    save_user_memory(sender_id, memory)

    print(f"Sending response: {agent_response}")

    resp = MessagingResponse()
    resp.message(agent_response)

    return str(resp)

if __name__ == "__main__":
    # Ensure credentials directory exists before starting
    if not os.path.exists('credentials'):
        print("Error: 'credentials' directory not found. Please run add_account.py first.")
    else:
        print("Starting Flask server...")
        app.run(port=5000, debug=True) # Use debug=False for production