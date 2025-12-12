import gradio as gr
from ui.ingest_tab import create_ingest_ui
from ui.chat_tab import create_chat_ui

from core.tools import get_tool_definitions, list_files, read_file, search_knowledge_graph, set_workspace_path, get_repositories

def create_ui(client, prompts, config):
    """
    Creates the main Gradio Blocks interface by combining tabs.
    """
    store = None # Deprecated global store concept
    
    css = """
    .conversation-list-container {
        max-height: 300px;
        overflow-y: auto;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
    #visualization-output {
        min-height: 600px;
        overflow: auto;
    }
    .svelte-14vb072 {
        margin-top: 2px;
    }
    """
    
    with gr.Blocks(theme=gr.themes.Ocean(), css=css) as demo:
        gr.Markdown("<h1 style='text-align: center;'>Aurora Codex</h1>")


        # Create the Ingest tab
        create_ingest_ui(client, store, config)

        # Create the Chat tab
        create_chat_ui(client, store, prompts, config)
        
    return demo
        
    return demo
