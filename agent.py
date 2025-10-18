# local_tester.py

import os
from dotenv import load_dotenv
from datetime import date

# --- LangChain and Tool imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory

# Import ALL tools from ALL toolkits
from get_date import get_todays_date # Assuming you have this simple tool
from calendar_tools import search_calendar_events, create_event, update_event, delete_event
from gmail_tools import search_gmail, get_gmail_message, send_gmail_message, create_gmail_draft, trash_gmail_message
from tasks_tools import (
    list_task_lists, get_task_list, create_task_list, update_task_list, delete_task_list,
    get_tasks, get_task, create_task, update_task, complete_task, delete_task,
    move_task, clear_completed_tasks
)
from keep_tools import list_notes, get_note, create_note, delete_note # Corrected import name

# --- Setup (runs only once) ---
load_dotenv()
# Setting this environment variable *might* help with minor scope mismatches, but ensure SCOPES lists are identical in all tool files.
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = 'True'

# --- Check if credentials directory exists ---
CREDENTIALS_DIR = 'credentials'
if not os.path.exists(CREDENTIALS_DIR) or not os.listdir(CREDENTIALS_DIR):
    print(f"\n--- WARNING ---")
    print(f"The '{CREDENTIALS_DIR}/' directory is missing or empty.")
    print(f"Please run 'python add_account.py' for each Google account you want Jarvis to use.")
    print(f"---------------")
    # Decide if you want to exit or continue with limited functionality
    # exit() # Uncomment to force exit if no credentials

# 1. Initialize the LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY")) # Using gemini-pro for better reasoning

# 2. Define the complete list of tools Jarvis can use
tools = [
    get_todays_date,
    # Calendar
    search_calendar_events, create_event, update_event, delete_event,
    # Gmail
    search_gmail, get_gmail_message, send_gmail_message, create_gmail_draft, trash_gmail_message,
    # Tasks
    list_task_lists, get_task_list, create_task_list, update_task_list, delete_task_list,
    get_tasks, get_task, create_task, update_task, complete_task, delete_task,
    move_task, clear_completed_tasks,
    # Keep (Single Account)
    list_notes, get_note, create_note, delete_note
]

# --- MODIFIED: Define available aliases and update system prompt ---
# !!! IMPORTANT: Make sure these aliases exactly match your .json filenames in the credentials/ folder !!!
AVAILABLE_ALIASES = ['personal', 'student', 'work', 'casual'] # Adjust as needed
aliases_string = ", ".join(AVAILABLE_ALIASES)

base_prompt = ChatPromptTemplate.from_messages([
    ("system", f"""You are Jarvis, a proactive and highly intelligent personal assistant.

Your primary capability is your powerful language model. Use it for general queries, writing, brainstorming etc.

You also have special tools to interact with the user's Google services (Calendar, Gmail, Tasks) and Google Keep (via gkeepapi).

**CRITICAL RULES FOR GOOGLE SERVICE TOOLS (Calendar, Gmail, Tasks):**
1. These tools require an 'account_alias' to specify which user account to act upon.
2. The available account aliases are: **{aliases_string}**.
3. **If the user's request clearly specifies an account alias** (e.g., 'check my *student* email'), use that alias when calling the tool.
4. **If the user's request DOES NOT specify an account alias** for Calendar, Gmail, or Tasks, you MUST ask the user a clarifying question: "Which account should I use for that ({aliases_string})?". Do NOT attempt to call the tool without an alias unless the user provides one.
5. Google Keep tools do NOT require an account alias as they connect to a single pre-configured account.

General Rules:
- Be concise and conversational. Do not expose tool names or internal processes.
- The current date is {{current_date}}.
"""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 4. Initialize the conversation memory
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# --- Main Conversation Loop ---
print("\nJarvis is ready for multi-account local testing. Ask anything (or type 'exit' to quit).")
while True:
    user_input = input("\n> ")

    if user_input.lower() == 'exit':
        print("Goodbye!")
        break

    try:
        current_date_str = date.today().isoformat()
        prompt_with_date = base_prompt.partial(current_date=current_date_str)

        agent = create_tool_calling_agent(llm, tools, prompt_with_date)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            memory=memory,
            verbose=True,
            handle_parsing_errors="Check your output and make sure it conforms!", # More informative error handling
            max_iterations=10 # Prevent overly long loops if agent gets stuck
            )

        result = agent_executor.invoke({"input": user_input})
        print(f"\nJarvis: {result['output']}")

    except Exception as e:
        print(f"An error occurred: {e}")