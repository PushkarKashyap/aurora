import sqlite3
import time
from datetime import datetime
import tempfile
import json
import os
from google.genai import types, errors

# --- SQLite Datetime Adapters ---
def adapt_datetime_iso(val):
    return val.isoformat()

def convert_datetime(val):
    return datetime.fromisoformat(val.decode())

sqlite3.register_adapter(datetime, adapt_datetime_iso)
sqlite3.register_converter("DATETIME", convert_datetime)

from core.tools import get_tool_definitions, list_files, read_file, search_knowledge_graph, set_workspace_path, get_graph_path
from core.store_utils import get_or_create_store

def send_message_with_retry(chat_session, content, max_retries=3):
    """Sends a message to the chat session with retry logic for rate limits."""
    for attempt in range(max_retries):
        try:
            return chat_session.send_message(content)
        except errors.ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 10  # Exponential-ish backoff: 10s, 20s, 30s
                    print(f"Rate limit hit (429). Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
            raise e
    return None # Should raise before this

available_tools = {
    "list_files": list_files,
    "read_file": read_file,
    "search_knowledge_graph": search_knowledge_graph,
    "set_workspace_path": set_workspace_path
}

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
                    response TEXT NOT NULL,
                    repo_path TEXT,
                    tool_calls TEXT
                )
            """)
            # Migration check
            cursor.execute("PRAGMA table_info(chat_history)")
            columns = [info[1] for info in cursor.fetchall()]
            if "repo_path" not in columns:
                print("Migrating database: adding 'repo_path' column.")
                cursor.execute("ALTER TABLE chat_history ADD COLUMN repo_path TEXT")

            if "tool_calls" not in columns:
                print("Migrating database: adding 'tool_calls' column.")
                cursor.execute("ALTER TABLE chat_history ADD COLUMN tool_calls TEXT")

            conn.commit()
        print("Database initialized successfully.")
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")

def add_chat_history(db_name, conversation_id, query, response, repo_path=None, tool_calls=None):
    """Adds a new chat interaction to the history database."""
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            tool_calls_json = json.dumps(tool_calls) if tool_calls is not None else None
            cursor.execute(
                "INSERT INTO chat_history (conversation_id, timestamp, query, response, repo_path, tool_calls) VALUES (?, ?, ?, ?, ?, ?)",
                (conversation_id, datetime.now(), query, response, repo_path, tool_calls_json)
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding to chat history: {e}")

def get_conversations(db_name, repo_path=None):
    """Retrieves a list of unique conversation IDs and their first query as the title."""
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            sql = """
                SELECT T1.conversation_id, T1.query
                FROM chat_history T1
                JOIN (
                    SELECT conversation_id, MIN(timestamp) AS min_ts
                    FROM chat_history
                    GROUP BY conversation_id
                ) T2 ON T1.conversation_id = T2.conversation_id AND T1.timestamp = T2.min_ts
            """
            params = []
            if repo_path:
                sql += " WHERE T1.repo_path = ?"
                params.append(repo_path)
            
            sql += " ORDER BY T1.timestamp DESC;"
            cursor.execute(sql, tuple(params))
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
                "SELECT query, response, tool_calls FROM chat_history WHERE conversation_id = ? ORDER BY timestamp ASC",
                (conversation_id,)
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error loading conversation: {e}")
        return []

def generate_report(conversation_id, db_name):
    """Generates a markdown report from a conversation and returns the file path."""
    if not conversation_id:
        return None

    history = load_conversation_from_db(db_name, conversation_id)
    if not history:
        return None

    report_content = f"# Impact Analysis Report\n\n"
    report_content += f"**Conversation ID:** `{conversation_id}`\n"
    report_content += f"**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report_content += "---\n\n"

    for i, (query, response, tool_calls_json) in enumerate(history):
        report_content += f"### Interaction {i+1}\n\n"
        report_content += f"**User Query:**\n```\n{query or ''}\n```\n\n"
        
        # Add tool info if present
        if tool_calls_json:
            try:
                tool_calls = json.loads(tool_calls_json)
                if tool_calls:
                    report_content += "**Tools used:** "
                    tool_names = [f"`{tc.get('name', 'tool')}`" for tc in tool_calls]
                    report_content += ", ".join(tool_names) + "\n\n"
            except:
                pass

        report_content += f"**Aurora's Response:**\n{response or ''}\n\n"
        report_content += "---\n\n"

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md', encoding='utf-8') as temp_file:
        temp_file.write(report_content)
        return temp_file.name

def generate_visualization(conversation_id, db_name, config, repo_path, show_neighbors=False):
    """Generates a Mermaid diagram from conversation context."""
    if not conversation_id:
        return "```mermaid\ngraph TD;\n  A[No conversation selected.];\n```"

    if not repo_path:
        return "```mermaid\ngraph TD;\n  A[No repository selected.];\n```"

    graph_file_path = get_graph_path(repo_path)
    if not graph_file_path or not os.path.exists(graph_file_path):
        return "```mermaid\ngraph TD;\n  A[Knowledge graph not found. Please build it on the Ingest page.];\n```"
    
    with open(graph_file_path, 'r', encoding='utf-8') as f:
        knowledge_graph = json.load(f)

    node_map = {node['id']: node for node in knowledge_graph['nodes']}
    history = load_conversation_from_db(db_name, conversation_id)
    if not history:
        return "```mermaid\ngraph TD;\n  A[Could not load conversation history.];\n```"

    # History rows can include (query, response) or (query, response, tool_calls).
    # Safely concatenate the query and response fields without assuming tuple length.
    all_text = "".join([str(item[0] or "") + str(item[1] or "") for item in history])
    all_node_ids = set(node_map.keys())
    mentioned_nodes = {node_id for node_id in all_node_ids if node_id in all_text}

    if not mentioned_nodes:
        return "```mermaid\ngraph TD;\n  A[No specific code entities found in this conversation to visualize.];\n```"

    subgraph_nodes = set(mentioned_nodes)
    subgraph_edges = []
    
    if show_neighbors:
        for edge in knowledge_graph['edges']:
            source, target = edge['source'], edge['target']
            if source in mentioned_nodes or target in mentioned_nodes:
                subgraph_nodes.add(source)
                subgraph_nodes.add(target)
                subgraph_edges.append(edge)
    else:
        for edge in knowledge_graph['edges']:
            source, target = edge['source'], edge['target']
            if source in subgraph_nodes and target in subgraph_nodes:
                subgraph_edges.append(edge)
        edge_nodes = {node for edge in subgraph_edges for node in (edge['source'], edge['target'])}
        subgraph_nodes = subgraph_nodes.union(edge_nodes)

    mermaid_lines = ["graph TD"]
    files_to_nodes = {}
    
    mermaid_lines.append("  %% Dark Theme Styles")
    mermaid_lines.append("  classDef fileNode fill:#1e3a5f,stroke:#4fc3f7,stroke-width:2px,color:#fff;")
    mermaid_lines.append("  classDef classNode fill:#5d4037,stroke:#ffb74d,stroke-width:2px,color:#fff;")
    mermaid_lines.append("  classDef funcNode fill:#2e4a3a,stroke:#81c784,stroke-width:2px,color:#fff;")
    mermaid_lines.append("  classDef default fill:#37474f,stroke:#90a4ae,stroke-width:1px,color:#fff;")

    def safe(nid):
        return nid.replace('.', '_').replace('-', '_').replace(' ', '_')

    for node_id in subgraph_nodes:
        node_data = node_map.get(node_id, {"type": "unknown", "file": "unknown"})
        file_parent = node_data.get("file", "unknown")
        if node_data.get("type") == "file":
            file_parent = "Files"
        if file_parent not in files_to_nodes:
            files_to_nodes[file_parent] = []
        files_to_nodes[file_parent].append(node_id)

    for file_group, nodes in files_to_nodes.items():
        if file_group != "unknown" and file_group != "Files":
             mermaid_lines.append(f"  subgraph {safe(file_group)} [{file_group}]")
        for node_id in nodes:
            node_data = node_map.get(node_id, {})
            n_type = node_data.get("type", "unknown")
            s_id = safe(node_id)
            if n_type == 'file':
                mermaid_lines.append(f"    {s_id}[[{node_id}]]:::fileNode")
            elif n_type == 'class':
                mermaid_lines.append(f"    {s_id}{{{{{node_id}}}}}:::classNode") # Hexagon
            elif n_type == 'function':
                mermaid_lines.append(f"    {s_id}({node_id}):::funcNode") # Rounded
            else:
                mermaid_lines.append(f"    {s_id}[{node_id}]")
        if file_group != "unknown" and file_group != "Files":
            mermaid_lines.append("  end")

    for edge in subgraph_edges:
        s = safe(edge['source'])
        t = safe(edge['target'])
        mermaid_lines.append(f"  {s} -->|{edge.get('type','uses')}| {t}")

    return "```mermaid\n" + "\n".join(mermaid_lines) + "\n```"

def chat_fn(message, history, chat_session, conversation_id_state, client, repo_path, prompts, config):

    """

    Handles the chat interaction, using the file search store and local tools.

    """

    db_name = config["database_name"]

    new_conversation_started = False



    try:

        store = get_or_create_store(client, repo_path)

    except Exception as e:

        yield f"Error connecting to store: {e}", chat_session, conversation_id_state, new_conversation_started

        return



    if not conversation_id_state:

        new_conversation_started = True

        conversation_id_state = f"conv_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        print(f"New conversation started with ID: {conversation_id_state}")



    if not chat_session:

        chat_session = None

        gemini_history = []

        if history:

            for msg in history:

                if isinstance(msg, dict):

                    role = 'model' if msg.get('role') == 'assistant' else msg.get('role')

                    content = msg.get('content')

                    metadata = msg.get('metadata')

                else: 

                    role = 'model' if getattr(msg, 'role', '') == 'assistant' else getattr(msg, 'role', '')

                    content = getattr(msg, 'content', '')

                    metadata = getattr(msg, 'metadata', None)



                if not role: continue

                

                # User message

                if role == 'user':

                    gemini_history.append(types.Content(role=role, parts=[types.Part(text=content)]))

                    continue



                # Assistant message

                tool_calls = []

                if metadata and "tool_calls" in metadata:

                    tool_calls = metadata["tool_calls"]

                

                if tool_calls:

                    function_calls_parts = []

                    tool_outputs_parts = []

                    for tc in tool_calls:

                        args = tc.get('args', {})

                        if isinstance(args, str):

                            try:

                                args = json.loads(args)

                            except json.JSONDecodeError:

                                args = {}

                        

                        function_calls_parts.append(

                            types.Part(function_call=types.FunctionCall(name=tc['name'], args=args))

                        )

                        tool_outputs_parts.append(

                            types.Part(function_response=types.FunctionResponse(name=tc['name'], response={"result": tc['result']}))

                        )

                    

                    if function_calls_parts:

                        gemini_history.append(types.Content(role='model', parts=function_calls_parts))

                    if tool_outputs_parts:

                        gemini_history.append(types.Content(role='user', parts=tool_outputs_parts)) # Use 'user' role for function responses



                if content:

                    # Check if the content is just a repeat of the tool call display

                    is_redundant = False

                    if tool_calls:

                        first_tool_line = f"✅ `{tool_calls[0].get('name', 'tool')}`"

                        if content.strip().startswith(first_tool_line):

                            is_redundant = True



                    if not is_redundant:

                         gemini_history.append(types.Content(role='model', parts=[types.Part(text=content)]))

        

        tool_config = types.GenerateContentConfig(

            tools=[

                types.Tool(

                    file_search=types.FileSearch(

                        file_search_store_names=[store.name]

                    ),

                    function_declarations=get_tool_definitions()

                )

            ],

            system_instruction=prompts.get("chat_prompt"),

            automatic_function_calling={"disable": True} 

        )

        

        chat_session = client.chats.create(  # type: ignore

            history=gemini_history,

            model=config["gemini_model"]["chat_model_name"],

            config=tool_config

        )



    try:

        executed_tool_calls = []

        

        response = send_message_with_retry(chat_session, message)

        

        while True:

            function_calls = []

            if response.candidates and response.candidates[0].content.parts:

                for part in response.candidates[0].content.parts:

                    if part.function_call:

                        function_calls.append(part.function_call)

            

            if not function_calls:

                break 

            

            tool_outputs = []

            for fc in function_calls:

                func_name = fc.name

                func_args = dict(fc.args) # Convert to dict for serialization

                

                # Build descriptive status with tool arguments

                if func_name == "read_file":

                    arg_desc = f"`{func_args.get('file_path', '?')}`"

                elif func_name == "search_knowledge_graph":

                    arg_desc = f"query: `{func_args.get('query', '?')}`"

                elif func_name == "list_files":

                    arg_desc = f"`{func_args.get('directory_path', 'workspace')}`"

                else:

                    arg_desc = ""

                

                status_detail = f" → {arg_desc}" if arg_desc else ""

                yield f"🛠️ `{func_name}`{status_detail}...", chat_session, conversation_id_state, new_conversation_started

                

                if func_name in available_tools:

                    try:

                        if func_name == "search_knowledge_graph":

                            func_args["repo_path"] = repo_path

                        if func_name == "list_files" and not func_args.get("directory_path"):

                            func_args["directory_path"] = repo_path

                        if func_name == "set_workspace_path" and not func_args.get("path"):

                            func_args["path"] = repo_path

                            

                        result = available_tools[func_name](**func_args)

                        print(f"Executed {func_name} -> Length: {len(str(result))}")

                        yield f"✅ `{func_name}`{status_detail} ✓", chat_session, conversation_id_state, new_conversation_started

                    except Exception as e:

                        result = f"Error executing {func_name}: {e}"

                        yield f"❌ Error in `{func_name}`: {e}", chat_session, conversation_id_state, new_conversation_started

                else:

                    result = f"Error: Function {func_name} is not available."

                

                executed_tool_calls.append({

                    "name": func_name,

                    "args": func_args,

                    "result": str(result)

                })



                tool_outputs.append(

                    types.Part(

                        function_response=types.FunctionResponse(

                            name=func_name,

                            response={"result": result}

                        )

                    )

                )



            yield "🧠 Processing tool outputs...", chat_session, conversation_id_state, new_conversation_started

            response = send_message_with_retry(chat_session, tool_outputs)



        response_text = ""

        if response.candidates and response.candidates[0].content.parts:

            for part in response.candidates[0].content.parts:

                if part.text:

                    response_text += part.text



    except Exception as e:

        print(f"Error during chat session: {e}")

        error_message = f"I'm sorry, but I encountered an error: {e}. Please try again."

        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):

             error_message = (

                "⚠️ **High Traffic / Quota Exceeded**\n\n"

                "The AI model is currently busy or the context is too large (429 Resource Exhausted).\n"

                "Please wait about a minute and try again. If the problem persists, try clearing the chat history."

            )

        yield error_message, chat_session, conversation_id_state, new_conversation_started

        return



    try:

        if response.candidates:

            grounding = response.candidates[0].grounding_metadata

            if grounding and grounding.grounding_chunks:

                sources = {chunk.retrieved_context.title for chunk in grounding.grounding_chunks}

                if sources:

                    yield f"📚 `file_search` → found {len(sources)} source{'s' if len(sources) > 1 else ''}", chat_session, conversation_id_state, new_conversation_started

                    citations = "\n\n**Sources:**\n" + "\n".join(f"- `{source}`" for source in sorted(list(sources)))

                    response_text += citations

    except (AttributeError, IndexError):

        pass



    if message and (response_text or executed_tool_calls) and conversation_id_state:

        add_chat_history(

            db_name,

            conversation_id_state,

            message,

            response_text,

            repo_path=repo_path,

            tool_calls=executed_tool_calls

        )



    if not response_text:

        response_text = "(No response text generated by the model.)"

    yield response_text, chat_session, conversation_id_state, new_conversation_started