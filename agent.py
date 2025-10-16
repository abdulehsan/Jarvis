# local_tester.py

import os
from dotenv import load_dotenv
from datetime import date

# --- LangChain and Tool imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory

# Import ALL your tools
from get_date import get_todays_date
from calendar_tools import search_calendar_events, create_event, update_event, delete_event
from gmail_tools import search_gmail, get_gmail_message, send_gmail_message

# --- Setup (runs only once) ---
load_dotenv()

# 1. Initialize the LLM (using a stable, recommended model)
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))

# 2. Define the complete list of tools Jarvis can use
tools = [
    get_todays_date,
    search_calendar_events, create_event, update_event, delete_event,
    search_gmail, get_gmail_message, send_gmail_message
]

# 3. Create the influential system prompt
#    It now takes a dynamic {current_date} variable.
base_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are Jarvis, a proactive and highly intelligent personal assistant.

Your primary capability is your powerful language model. Use it to directly answer questions, write text, brainstorm ideas, and perform any creative or informational task.

In addition, you have a set of special tools to interact with the user's private Google services. Follow these rules for tool use:
1.  **If and only if** a request explicitly involves the user's personal schedule, events, or emails, you MUST use your specialized tools to interact with Google Calendar or Gmail.
2.  For all other general requests (e.g., 'write a short message to my friend', 'summarize this article'), you MUST answer directly using your own creative and analytical abilities.
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
        # ** THE FIX IS HERE **
        # 1. Get the current date every time a message is sent.
        current_date_str = date.today().isoformat()
        
        # 2. Pre-fill the prompt with today's date.
        prompt_with_date = base_prompt.partial(current_date=current_date_str)
        
        # 3. Create the agent and executor inside the loop to use the dated prompt.
        agent = create_tool_calling_agent(llm, tools, prompt_with_date)
        agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True)

        # 4. Invoke the agent with ONLY the 'input' key.
        result = agent_executor.invoke({"input": user_input})
        print(f"\nJarvis: {result['output']}")

    except Exception as e:
        print(f"An error occurred: {e}")