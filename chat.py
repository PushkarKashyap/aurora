import sqlite3
from datetime import datetime
from gradio.components import ChatMessage
import gradio as gr
from google.genai import types


# --- SQLite Datetime Adapters (for Python 3.12+ DeprecationWarning) ---
def adapt_datetime_iso(val):
    """Adapt datetime.datetime to timezone-naive ISO 8601 format."""
    return val.isoformat()


def convert_datetime(val):
    """Convert ISO 8601 formatted string to datetime.datetime object."""
    return datetime.fromisoformat(val.decode())


# Register the adapter and converter
sqlite3.register_adapter(datetime, adapt_datetime_iso)
sqlite3.register_converter("DATETIME", convert_datetime)

# --- Database Management ---
def init_db(db_name):
    """Initializes the SQLite database and creates the history table if it doesn't exist."""
    print(f"--- Initializing Database: {db_name} ---")
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL
                )
            """)
            conn.commit()
        print("Database initialized successfully.")
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")


def add_chat_history(db_name, conversation_id, query, response):
    """Adds a new chat interaction to the history database."""
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_history (conversation_id, timestamp, query, response) VALUES (?, ?, ?, ?)",
                (conversation_id, datetime.now(), query, response)
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding to chat history: {e}")


def get_conversations(db_name):
    """Retrieves a list of unique conversation IDs and their first query as the title."""
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            # Use a subquery to get the first message for each conversation
            cursor.execute("""
                SELECT T1.conversation_id, T1.query
                FROM chat_history T1
                JOIN (
                    SELECT conversation_id, MIN(timestamp) AS min_ts
                    FROM chat_history
                    GROUP BY conversation_id
                ) T2 ON T1.conversation_id = T2.conversation_id AND T1.timestamp = T2.min_ts
                ORDER BY T1.timestamp DESC;
            """)
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching conversations: {e}")
        return []


def delete_conversation_from_db(db_name, conversation_id):
    """Deletes all messages for a given conversation_id from the database."""
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM chat_history WHERE conversation_id = ?",
                (conversation_id,)
            )
            conn.commit()
        print(f"Deleted conversation: {conversation_id}")
        return True
    except sqlite3.Error as e:
        print(f"Error deleting conversation {conversation_id}: {e}")
        return False


def load_conversation_from_db(db_name, conversation_id):
    """Loads a past conversation from the database."""
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT query, response FROM chat_history WHERE conversation_id = ? ORDER BY timestamp ASC",
                (conversation_id,)
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error loading conversation: {e}")
        return []


# --- Core Chat Logic ---
def chat_fn(message, history, chat_session, conversation_id_state, client, store, prompts, config):
    """
    Handles the chat interaction, using the file search store as a tool.
    """
    db_name = config["database_name"]
    new_conversation_started = False

    # If conversation_id is missing, it's a new conversation.
    if not conversation_id_state:
        new_conversation_started = True
        # Generate a new conversation ID for this new session
        conversation_id_state = f"conv_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print(f"New conversation started with ID: {conversation_id_state}")

    # If the backend chat session doesn't exist (e.g., after loading a convo), create it.
    if not chat_session:
        chat_session = None  # Ensure any previous session object is discarded

        # Convert Gradio's ChatMessage history to Gemini's Content format before creating the session
        gemini_history = []
        if history:
            for msg in history:
                # The Gemini API uses 'model' for the assistant's role
                if isinstance(msg, dict):
                    role = 'model' if msg['role'] == 'assistant' else msg['role']
                    content = msg['content']
                else:  # It's a ChatMessage object
                    role = 'model' if msg.role == 'assistant' else msg.role
                    content = msg.content
                gemini_history.append(types.Content(role=role, parts=[types.Part(text=content)]))

        # Configure the tools for the chat session
        tool_config = types.GenerateContentConfig(
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store.name]
                    )
                )
            ],
            system_instruction=prompts.get("chat_prompt")
        )
        # Start a chat session with the tool config
        chat_session = client.chats.create(  # type: ignore
            history=gemini_history,
            model=config["gemini_model"]["chat_model_name"],
            config=tool_config
        )

    # Send the user's message to the existing chat session
    try:
        response = chat_session.send_message(message)
        response_text = response.text
    except Exception as e:
        print(f"Error during chat session: {e}")
        error_message = (
            "I'm sorry, but I encountered an error while processing your request. "
            "This could be due to a temporary issue with the service. Please try again in a moment."
        )
        return error_message, chat_session, conversation_id_state, new_conversation_started

    # Add citations from grounding metadata
    try:
        # Grounding metadata is nested in the first candidate
        grounding = response.candidates[0].grounding_metadata
        if grounding and grounding.grounding_chunks:
            sources = {chunk.retrieved_context.title for chunk in grounding.grounding_chunks}
            if sources:
                citations = "\n\n**Sources:**\n" + "\n".join(f"- `{source}`" for source in sorted(list(sources)))
                response_text += citations
    except (AttributeError, IndexError):
        # This can happen if there are no candidates or no grounding metadata.
        pass

    # Save the interaction to the database
    if message and response_text and conversation_id_state:
        add_chat_history(db_name, conversation_id_state, message, response_text)

    return response_text, chat_session, conversation_id_state, new_conversation_started


def load_conversation(conversation_id, db_name):
    """Loads a past conversation from the database into the chat window."""
    from gradio import update as gr_update # Local import to avoid circular dependency issues
    if not conversation_id:
        return [], None, None, gr_update(value=None), gr_update(visible=False)

    print(f"Loading conversation: {conversation_id}")
    history = load_conversation_from_db(db_name, conversation_id)

    if not history:
        # Handle case where history is not found or there was a DB error
        return [], None, None, gr_update(value=conversation_id), gr_update(visible=True)

    # Reconstruct Gradio's chatbot history format for type="messages"
    chat_history_formatted = []
    for query, response in history:
        chat_history_formatted.extend([ChatMessage(role="user", content=query), ChatMessage(role="assistant", content=response)])

    # When loading a conversation, we must start a new backend chat session
    # because the session object cannot be serialized and stored.
    # The context is rebuilt by Gradio's history.
    return chat_history_formatted, None, conversation_id, gr_update(value=conversation_id), gr_update(visible=True)


# --- UI Wrapper Functions ---
def chat_wrapper(message, history, chat_session, conversation_id_state, client, store, prompts, config, refresh_conversation_list_fn):
    """
    Wrapper function to manage history for the custom chat UI.
    It calls the main chat_fn and handles history updates.
    """
    # Append the user's message to the history for display
    history.append(ChatMessage(role="user", content=message))
    
    # Get the bot's response by calling the core chat logic
    response_text, new_chat_session, new_conversation_id, new_convo_started = chat_fn(
        message, history, chat_session, conversation_id_state, client, store, prompts, config
    )
    
    # Append the bot's response to the history
    history.append(ChatMessage(role="assistant", content=response_text))
    
    # If a new conversation was started, refresh the list
    conversation_list_update = refresh_conversation_list_fn() if new_convo_started else gr.update()

    # Return all the updated states, clearing the input textbox
    return history, "", new_chat_session, new_conversation_id, conversation_list_update

def start_new_chat():
    """Clears the chat interface and starts a new session."""
    return None, None, None, gr.update(value=None), gr.update(visible=False)

def refresh_conversation_list(db_name):
    """Refreshes the list of conversations in the sidebar."""
    convos = get_conversations(db_name)
    # Format for gr.Radio: list of (label, value) tuples
    formatted_convos = [(f"{title[:40]}..." if len(title) > 40 else title, conv_id) for conv_id, title in convos]
    return gr.update(choices=formatted_convos)

def delete_conversation(conversation_id, db_name, refresh_conversation_list_fn):
    """Deletes a conversation and updates the UI."""
    if not conversation_id:
        return None, None, None, gr.update(), gr.update(visible=False)

    success = delete_conversation_from_db(db_name, conversation_id)

    if not success:
        # If deletion fails, don't change the UI, just log the error.
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(visible=True)

    # After successful deletion, clear the chat, refresh the list, and hide the button
    return None, None, None, refresh_conversation_list_fn(), gr.update(visible=False)

def create_chat_ui(client, store, prompts, config):
    """Creates the Gradio UI for the Chat tab."""
    db_name = config["database_name"]

    with gr.Tab("Chat") as chat_tab:
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## Conversations")
                new_chat_button = gr.Button("➕ New Chat", variant="primary")
                refresh_convos_button = gr.Button("🔄 Refresh")
                conversation_list = gr.Radio(
                    label="Past Conversations",
                    interactive=True,
                    elem_classes=["conversation-list"]
                )
                delete_conversation_button = gr.Button("🗑️ Delete Selected", variant="stop", visible=False)

            with gr.Column(scale=4):
                gr.Markdown("## Chat With Your Codebase")
                chat_session_state = gr.State(None)
                conversation_id_state = gr.State(None)
                
                chatbot = gr.Chatbot(height=600, type="messages", label="Chat with Aurora", show_label=False)
                with gr.Row():
                    chat_input = gr.Textbox(show_label=False, placeholder="Enter your message...", scale=4, container=False)
                    send_button = gr.Button("Send", variant="primary", scale=1)
                gr.Examples(
                    examples=["What are the main dependencies in requirements.txt?", "Explain the `chat_fn` function and its parameters."],
                    inputs=[chat_input]
                )

        # --- Event Handlers ---
        refresh_fn = lambda: refresh_conversation_list(db_name)
        
        chat_wrapper_fn = lambda msg, hist, sess, conv_id: chat_wrapper(msg, hist, sess, conv_id, client, store, prompts, config, refresh_fn)
        send_button.click(fn=chat_wrapper_fn, inputs=[chat_input, chatbot, chat_session_state, conversation_id_state], outputs=[chatbot, chat_input, chat_session_state, conversation_id_state, conversation_list])
        chat_input.submit(fn=chat_wrapper_fn, inputs=[chat_input, chatbot, chat_session_state, conversation_id_state], outputs=[chatbot, chat_input, chat_session_state, conversation_id_state, conversation_list])

        chat_tab.select(fn=refresh_fn, outputs=[conversation_list])
        refresh_convos_button.click(fn=refresh_fn, outputs=[conversation_list])

        load_conversation_fn = lambda conv_id: load_conversation(conv_id, db_name)
        conversation_list.input(fn=load_conversation_fn, inputs=[conversation_list], outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list, delete_conversation_button])

        new_chat_button.click(fn=start_new_chat, outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list, delete_conversation_button])

        delete_conversation_fn = lambda conv_id: delete_conversation(conv_id, db_name, refresh_fn)
        delete_conversation_button.click(fn=delete_conversation_fn, inputs=[conversation_id_state], outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list, delete_conversation_button])