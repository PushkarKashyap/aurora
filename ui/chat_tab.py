import gradio as gr
from gradio.components import ChatMessage
import json
from core.chat_engine import (
    chat_fn, load_conversation_from_db, delete_conversation_from_db, 
    generate_report, generate_visualization, get_conversations,
    init_db
)
from core.tools import get_tool_definitions, list_files, read_file, search_knowledge_graph, set_workspace_path, get_repositories

# Local UI Helper Functions

def _get_conversation_controls_updates(visible: bool, report_file_value=None):
    """Helper to generate gr.update dictionaries for conversation-specific controls."""
    return (
        gr.update(visible=visible),  # delete_conversation_button
        gr.update(visible=visible),  # generate_report_button
        gr.update(visible=visible if report_file_value else False, value=report_file_value), # report_file
        gr.update(visible=visible),  # visualize_button
        gr.update(visible=visible)   # visualize_neighbors_checkbox
    )

def get_formatted_conversations(db_name, repo_path=None):
    """Fetches and formats conversations for the gr.Radio component."""
    convos = get_conversations(db_name, repo_path)
    return [(f"{title[:40]}..." if len(title) > 40 else title, conv_id) for conv_id, title in convos]

def refresh_conversation_list(db_name, repo_path=None):
    """Refreshes the list of conversations in the sidebar."""
    formatted_convos = get_formatted_conversations(db_name, repo_path)
    return gr.update(choices=formatted_convos), *_get_conversation_controls_updates(False)

def start_new_chat(db_name, repo_path=None):
    """Clears the chat interface and starts a new session."""
    formatted_convos = get_formatted_conversations(db_name, repo_path)
    conversation_list_update = gr.update(choices=formatted_convos, value=None)
    visualization_clear = "No visualization generated yet. Ask a question and then click 'Visualize Impact'."
    return None, None, None, conversation_list_update, visualization_clear, *_get_conversation_controls_updates(False)

def load_conversation(conversation_id, db_name):
    """Loads a past conversation from the database into the chat window."""
    if not conversation_id:
        return [], None, None, gr.update(value=None), *_get_conversation_controls_updates(False)

    print(f"Loading conversation: {conversation_id}")
    history = load_conversation_from_db(db_name, conversation_id)

    if not history:
        return [], None, None, gr.update(value=conversation_id), *_get_conversation_controls_updates(True)

    chat_history_formatted = []
    for query, response, tool_calls_json in history:
        chat_history_formatted.append(ChatMessage(role="user", content=query))
        
        tool_calls = []
        if tool_calls_json:
            try:
                tool_calls = json.loads(tool_calls_json)
            except (json.JSONDecodeError, TypeError):
                pass
        
        display_content = response if response else ""
        
        # Add tool calls to metadata. The UI won't show it unless we tell it to.
        metadata = {"tool_calls": tool_calls} if tool_calls else None

        # Re-create the visual tool call history as seen during live generation
        full_response_content = ""
        if tool_calls:
            for tool_call in tool_calls:
                func_name = tool_call.get("name", "tool")
                args = tool_call.get('args', {})
                arg_desc = ""
                if func_name == "read_file":
                    arg_desc = f"`{args.get('file_path', '?')}`"
                elif func_name == "search_knowledge_graph":
                    arg_desc = f"query: `{args.get('query', '?')}`"
                elif func_name == "list_files":
                    arg_desc = f"`{args.get('directory_path', 'workspace')}`"
                
                status_detail = f" → {arg_desc}" if arg_desc else ""
                full_response_content += f"✅ `{func_name}`{status_detail} ✓\n"
        
        full_response_content += display_content

        chat_history_formatted.append(ChatMessage(role="assistant", content=full_response_content, metadata=metadata))

    return chat_history_formatted, None, conversation_id, gr.update(value=conversation_id), *_get_conversation_controls_updates(True)

def delete_conversation(conversation_id, db_name, refresh_conversation_list_fn, repo_path=None):
    """Deletes a conversation and updates the UI."""
    if not conversation_id:
        return None, None, None, gr.update(), *_get_conversation_controls_updates(False)

    success = delete_conversation_from_db(db_name, conversation_id)

    if not success:
        return gr.update(), gr.update(), gr.update(), gr.update(), *_get_conversation_controls_updates(True)

    conversation_list_update, *control_updates = refresh_conversation_list_fn(repo_path)
    return None, None, None, conversation_list_update, *control_updates

def chat_wrapper(message, history, assess_criticality, chat_session, conversation_id_state, repo_path, client, prompts, config, refresh_conversation_list_fn):
    """
    Wrapper function to manage history for the custom chat UI.
    It calls the main chat_fn and handles history updates.
    """
    history.append(ChatMessage(role="user", content=message))
    history.append(ChatMessage(role="assistant", content="🧠 *Thinking...*"))
    
    yield history, "", chat_session, conversation_id_state, gr.update()

    final_message = message
    if assess_criticality:
        final_message += "\n\nPlease also provide a detailed criticality assessment for the identified impacts, prioritizing them from most to least critical."
    
    chat_gen = chat_fn(
        final_message, history[:-1], chat_session, conversation_id_state, client, repo_path, prompts, config
    )
    
    final_response_text = ""
    new_convo_started = False
    new_conversation_id = conversation_id_state
    new_chat_session = chat_session
    pending_tool_msg = None  # Track pending "executing" message to update with result
    
    for response_text, updated_session, updated_conv_id, new_convo_flag in chat_gen:
        new_chat_session = updated_session
        new_conversation_id = updated_conv_id
        new_convo_started = new_convo_flag
        
        # Check if this is a status update vs final response
        if response_text and response_text[0] in "🛠️✅❌🧠⚠️":
            # Extract tool name from content if present
            tool_name = response_text.split("`")[1] if "`" in response_text else "tool"
            
            if response_text.startswith("🛠️"):
                # Starting a tool - replace placeholder with executing message
                history[-1] = ChatMessage(
                    role="assistant",
                    content=response_text,
                    metadata={"title": f"🔄 Using {tool_name}..."}
                )
                pending_tool_msg = len(history) - 1
            elif response_text.startswith("✅"):
                # Tool completed - update the pending message with completion
                if pending_tool_msg is not None and pending_tool_msg < len(history):
                    history[pending_tool_msg] = ChatMessage(
                        role="assistant",
                        content=response_text,
                        metadata={"title": f"✅ {tool_name}"}
                    )
                pending_tool_msg = None
                # Add placeholder for next action (will be replaced)
                history.append(ChatMessage(role="assistant", content="🧠 *Analyzing...*"))
            elif response_text.startswith("❌"):
                # Tool error - update with error
                if pending_tool_msg is not None and pending_tool_msg < len(history):
                    history[pending_tool_msg] = ChatMessage(
                        role="assistant",
                        content=response_text,
                        metadata={"title": f"💥 {tool_name} error"}
                    )
                pending_tool_msg = None
                history.append(ChatMessage(role="assistant", content="🧠 *Continuing...*"))
            elif response_text.startswith("🧠"):
                # Processing - update last message
                history[-1].content = response_text
            elif response_text.startswith("⚠️"): # Handle warning/error messages
                history[-1].content = response_text
        else:
            # Final response - replace placeholder with actual content
            history[-1] = ChatMessage(role="assistant", content=response_text)
            final_response_text = response_text
        
        yield history, "", new_chat_session, new_conversation_id, gr.update()
    
    conversation_list_update = refresh_conversation_list_fn(repo_path) if new_convo_started else gr.update()
    yield history, "", new_chat_session, new_conversation_id, conversation_list_update



def create_chat_ui(client, _, prompts, config): # store passed is ignored
    """Creates the Gradio UI for the Chat tab."""
    db_name = config["database_name"]

    with gr.Tab("Chat") as chat_tab:
        with gr.Row():
            with gr.Sidebar(open=False):
                current_repos = get_repositories()
                initial_repo = current_repos[0] if current_repos else None
                
                repo_dropdown = gr.Dropdown(
                    label="Active Repository",
                    choices=current_repos,
                    value=initial_repo,
                    interactive=True,
                    allow_custom_value=True
                )
                
                new_chat_button = gr.Button("➕ New Chat", variant="primary")
                refresh_convos_button = gr.Button("🔄 Refresh", variant="secondary")
                
                initial_convos = get_formatted_conversations(db_name, initial_repo)

                conversation_list = gr.Radio(
                    choices=initial_convos,
                    label="Past Conversations",
                    interactive=True,
                    show_label=False,
                    elem_classes=["conversation-list-container"]
                )
                with gr.Group():
                    delete_conversation_button = gr.Button("🗑️ Delete Selected", variant="stop", visible=False, elem_id="delete_conversation_button")
                    generate_report_button = gr.Button("📄 Generate Report", variant="secondary", visible=False, elem_id="generate_report_button")
                    report_file = gr.File(label="Download Report", visible=False, interactive=False, elem_id="report_file")
                    visualize_button = gr.Button("🎨 Visualize Impact", variant="secondary", visible=False, elem_id="visualize_button")
                    visualize_neighbors_checkbox = gr.Checkbox(label="Show Neighbors", value=False, visible=False, scale=1, elem_id="visualize_neighbors_checkbox")

            with gr.Column(scale=4):
                chat_session_state = gr.State(None)
                conversation_id_state = gr.State(None)
                
                chatbot = gr.Chatbot(
                    height=600, type="messages", label="Chat with Aurora", show_label=True, container=True, show_copy_button=True,
                    examples=[
                        {"text": "What are the main dependencies in requirements.txt?"},
                        {"text": "Explain the `chat_fn` function and its parameters."}
                    ]
                )
                with gr.Row():
                    chat_input_multimodal = gr.MultimodalTextbox(show_label=False, placeholder="Enter your message...", scale=10, interactive=True, max_plain_text_length=5000, file_types=None)
                    assess_criticality_checkbox = gr.Checkbox(label="Assess Criticality", value=False, scale=2, elem_id="assess-criticality-checkbox")
        
        with gr.Tab("Visualization"):
            visualization_output = gr.Markdown("No visualization generated yet. Ask a question and then click 'Visualize Impact'.", elem_id="visualization-output")

        def populate_example(evt: gr.SelectData):
            return evt.value['text']

        # --- Event Handlers ---
        refresh_fn = lambda repo: refresh_conversation_list(db_name, repo)
        load_conversation_fn = lambda conv_id: load_conversation(conv_id, db_name)
        conversation_controls = [delete_conversation_button, generate_report_button, report_file, visualize_button, visualize_neighbors_checkbox]
        
        repo_dropdown.change(
             fn=lambda repo: (set_workspace_path(repo), None)[1], inputs=[repo_dropdown], outputs=[]
        ).then(
             fn=refresh_fn, inputs=[repo_dropdown], outputs=[conversation_list] + conversation_controls
        ).then(
             fn=lambda: (None, None, None, "No visualization generated yet. Ask a question and then click 'Visualize Impact'."), 
             outputs=[chatbot, chat_session_state, conversation_id_state, visualization_output]
        )

        def chat_wrapper_fn(msg, hist, crit, sess, conv_id, repo):
             user_message_text = msg['text'] # Extract the text content from the multimodal input
             yield from chat_wrapper(user_message_text, hist, crit, sess, conv_id, repo, client, prompts, config, refresh_fn)
        
        chat_input_multimodal.submit(
            fn=chat_wrapper_fn,
            inputs=[
                chat_input_multimodal,
                chatbot,
                assess_criticality_checkbox,
                chat_session_state,
                conversation_id_state,
                repo_dropdown
            ],
            outputs=[chatbot, chat_input_multimodal, chat_session_state, conversation_id_state, conversation_list]
        )

        chatbot.example_select(fn=populate_example, inputs=None, outputs=[chat_input_multimodal])

        refresh_convos_button.click(fn=refresh_fn, inputs=[repo_dropdown], outputs=[conversation_list] + conversation_controls)

        conversation_list.input(
            fn=load_conversation_fn,
            inputs=[conversation_list],
            outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list] + conversation_controls
        )

        new_chat_button.click(
            fn=lambda repo: start_new_chat(db_name, repo),
            inputs=[repo_dropdown],
            outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list, visualization_output] + conversation_controls,
            show_progress="hidden"
        )

        delete_conversation_fn = lambda conv_id, repo: delete_conversation(conv_id, db_name, refresh_fn, repo)
        delete_conversation_button.click(
            fn=delete_conversation_fn,
            inputs=[conversation_id_state, repo_dropdown],
            outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list] + conversation_controls
        )

        # Generate report wrapper for UI return
        def generate_report_ui(conv_id):
            path = generate_report(conv_id, db_name)
            if path:
                return gr.update(value=path, visible=True)
            return gr.update(value=None, visible=False)

        generate_report_button.click(fn=generate_report_ui, inputs=[conversation_id_state], outputs=[report_file])

        visualize_fn = lambda conv_id, repo, show_neighbors: generate_visualization(conv_id, db_name, config, repo, show_neighbors)
        visualize_button.click(fn=visualize_fn, inputs=[conversation_id_state, repo_dropdown, visualize_neighbors_checkbox], outputs=[visualization_output], show_progress="hidden")