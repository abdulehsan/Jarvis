from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
from dotenv import load_dotenv
import shelve
from datetime import date

# --- All your existing LangChain and Tool imports ---
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from calendar_tools import search_calendar_events, create_event, update_event, delete_event

# --- Initialize App and Agent (runs only once on startup) ---
app = Flask(__name__)
load_dotenv()

# --- 1. Persistent Memory Management ---
def get_user_memory(session_id):
    """Retrieves or creates a conversation memory for a given user."""
    with shelve.open("conversation_db", flag='c') as db:
        return db.get(session_id, ConversationBufferMemory(memory_key="chat_history", return_messages=True))

def save_user_memory(session_id, memory):
    """Saves the updated conversation memory for a given user."""
    with shelve.open("conversation_db", flag='c') as db:
        db[session_id] = memory

# --- 2. Agent Setup ---
# The core components are defined once to be efficient
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))
tools = [search_calendar_events, create_event, update_event, delete_event]

# The base prompt template is created once
base_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are Jarvis, a witty and highly intelligent personal assistant. Be concise and conversational. Do not reveal that you are an AI or talk about your internal tools. Simply perform the request and give a natural, helpful response. The current date is {current_date}."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

@app.route("/webhook", methods=['POST'])
def webhook():
    """This function is called by Twilio when a message is received."""
    incoming_msg = request.values.get('Body', '').strip()
    sender_id = request.values.get('From', '')

    print(f"Received message '{incoming_msg}' from {sender_id}")

    memory = get_user_memory(sender_id)

    # --- Run the agent ---
    try:
        # ** THE FIX IS HERE **
        # 1. Get the current date as a string
        current_date_str = date.today().isoformat()
        
        # 2. "Partial" the prompt, pre-filling the date
        prompt_with_date = base_prompt.partial(current_date=current_date_str)
        
        # 3. Create the agent and executor with the dated prompt
        agent = create_tool_calling_agent(llm, tools, prompt_with_date)
        agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, verbose=True)

        # 4. Invoke the agent with ONLY the 'input' key
        result = agent_executor.invoke({"input": incoming_msg})
        agent_response = result["output"]

    except Exception as e:
        print(f"An error occurred: {e}")
        agent_response = "Sorry, I seem to have encountered an error. Please try that again."
    
    save_user_memory(sender_id, memory)
    
    print(f"Sending response: {agent_response}")

    # Create a TwiML response to send back to WhatsApp
    resp = MessagingResponse()
    resp.message(agent_response)

    return str(resp)

if __name__ == "__main__":
    app.run(port=5000, debug=True)