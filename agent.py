# local_tester.py

import os
from dotenv import load_dotenv
from datetime import date

# --- LangChain and Tool imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory

# Import ALL your tools from ALL your toolkits
from get_date import get_todays_date
from calendar_tools import search_calendar_events, create_event, update_event, delete_event
from gmail_tools import search_gmail, get_gmail_message, send_gmail_message
# NEW: Import the complete set of Google Tasks tools
from tasks_tools import (
    list_task_lists, get_task_list, create_task_list, update_task_list, delete_task_list,
    get_tasks, get_task, create_task, update_task, complete_task, delete_task,
    move_task, clear_completed_tasks
)

# --- Setup (runs only once) ---
load_dotenv()

# 1. Initialize the LLM (using a stable, recommended model)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))

# 2. Define the complete list of tools Jarvis can use
tools = [
    get_todays_date,
    # Calendar Tools
    search_calendar_events, create_event, update_event, delete_event,
    # Gmail Tools
    search_gmail, get_gmail_message, send_gmail_message,
    # Complete Google Tasks Toolkit (NEW)
    list_task_lists, get_task_list, create_task_list, update_task_list, delete_task_list,
    get_tasks, get_task, create_task, update_task, complete_task, delete_task,
    move_task, clear_completed_tasks
]

# 3. Create the influential system prompt with updated instructions
base_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are Jarvis, a proactive and highly intelligent personal assistant.

Your primary capability is your powerful language model. Use it to directly answer questions, write text, brainstorm ideas, and perform any creative or informational task.

In addition, you have a set of special tools to interact with the user's private Google services. Follow these rules for tool use:
1.  **If and only if** a request explicitly involves the user's personal data, you MUST use your specialized tools to interact with:
    - **Google Calendar:** For managing events and schedules.
    - **Gmail:** For reading, searching, and sending emails.
    - **Google Tasks:** For full management of to-do lists, including creating/deleting lists, adding/completing/moving tasks, and managing subtasks.
2.  For all other general requests (e.g., 'write a poem'), you MUST answer directly using your own creative abilities.
3.  Always be concise and conversational. Do not expose the names of your tools or explain your internal processes.

The current date is {current_date}."""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

# 4. Initialize the conversation memory
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# --- Main Conversation Loop ---
print("\nJarvis is ready for local testing. Ask anything (or type 'exit' to quit).")
while True:
    user_input = input("\n> ")

    if user_input.lower() == 'exit':
        print("Goodbye!")
        break

    try:
        current_date_str = date.today().isoformat()
        prompt_with_date = base_prompt.partial(current_date=current_date_str)
        
        agent = create_tool_calling_agent(llm, tools, prompt_with_date)
        agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True)

        result = agent_executor.invoke({"input": user_input})
        print(f"\nJarvis: {result['output']}")

    except Exception as e:
        print(f"An error occurred: {e}")