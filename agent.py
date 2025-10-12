import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder # NEW
from langchain.memory import ConversationBufferMemory # NEW

# Your custom tool
from get_date import get_todays_date
from calendar_tools import search_calendar_events, create_event, update_event, delete_event


load_dotenv()

# 1. Initialize the LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))

# 2. Define the tools
tools = [get_todays_date,search_calendar_events, create_event, update_event, delete_event]

# 3. Create the prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant named Jarvis. The current date is October 12, 2025."),
    MessagesPlaceholder(variable_name="chat_history"), # NEW: This will hold the conversation history
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# 4. Create the agent
agent = create_tool_calling_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True)


# --- Main Conversation Loop ---
print("\nJarvis is ready. Ask anything (or type 'exit' to quit).")
while True:
    # Get user input from the command line
    user_input = input("\n> ")

    # Check for the exit command
    if user_input.lower() == 'exit':
        print("Goodbye!")
        break

    # 5. Run the agent with the user's input
    try:
        result = agent_executor.invoke({"input": user_input})
        print(result["output"])
    except Exception as e:
        print(f"An error occurred: {e}")
