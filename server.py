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
from gmail_tools import search_gmail, send_email,get_gmail_message

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
tools = [search_calendar_events, create_event, update_event, delete_event,search_gmail,get_gmail_message,send_email]

# The base prompt template is created once
# In server.py

base_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are Jarvis, a proactive and highly intelligent personal assistant.

Your primary capability is your powerful language model. Use it to directly answer questions, write text, brainstorm ideas, and perform any creative or informational task.

In addition, you have a set of special tools to interact with the user's private Google services. Follow these rules for tool use:
1.  **If and only if** a request explicitly involves the user's personal schedule, events, or emails, you MUST use your specialized tools to interact with Google Calendar or Gmail.
2.  For all other general requests (e.g., 'write a short message to my friend', 'summarize this article', 'give me a business idea'), you MUST answer directly using your own creative and analytical abilities.
3.  Always be concise and conversational. Do not expose the names of your tools or explain your internal processes. Simply perform the task and provide the result in a natural way.

The current date is {current_date}."""),
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