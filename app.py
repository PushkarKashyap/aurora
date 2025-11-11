import gradio as gr
import os
import time
import yaml
from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- Configuration ---
def load_config():
    """Loads configuration from .env and prompts.yaml."""
    load_dotenv()
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file")
    
    with open("prompts.yaml", "r") as f:
        prompts = yaml.safe_load(f)
    return google_api_key, prompts

# --- Gemini Client Initialization ---
try:
    GOOGLE_API_KEY, PROMPTS = load_config()
    client = genai.Client(api_key=GOOGLE_API_KEY)
except (ValueError, FileNotFoundError) as e:
    print(f"Error initializing the application: {e}")
    # Exit or handle gracefully if running in a context that allows it
    exit()


# # --- Clean up old stores ---
# print("--- Cleaning up old File Search Stores ---")
# store_to_keep_display_name = "aurora-code-analysis-store"
# try:
#     for store_item in client.file_search_stores.list():
#         if store_item.display_name != store_to_keep_display_name:
#             print(f"Deleting store: {store_item.display_name} ({store_item.name})")
#             client.file_search_stores.delete(name=store_item.name, config={'force': True})
#         else:
#             print(f"Keeping store: {store_item.display_name}")
# except Exception as e:
#     print(f"An error occurred during store cleanup: {e}")
# print("--- Cleanup Complete ---")


# --- File Search Store Management ---
def get_or_create_store():
    """Gets the file search store or creates it if it doesn't exist."""
    print("--- Initializing File Search Store ---")
    store_display_name = "aurora-code-analysis-store"
    
    # Check if the store already exists
    for store in client.file_search_stores.list():
        if store.display_name == store_display_name:
            print(f"Found existing store: {store.name}")
            return store

    # If not found, create a new one
    print(f"Store not found, creating a new one: {store_display_name}")
    return client.file_search_stores.create(config={'display_name': store_display_name})

store = get_or_create_store()

# --- Core Functions ---
def ingest_files(files):
    """
    Uploads files to the file search store, yields progress, and waits for completion.
    """
    if not files:
        yield "No files uploaded. Please upload files to ingest."
        return

    yield f"Ingesting {len(files)} files... This may take a few minutes."
    print(f"Ingesting {len(files)} files...")

    # Process one file at a time to test the upload approach
    for file_obj in files:
        file_name = os.path.basename(file_obj.name)
        yield f"Uploading `{file_name}`..."
        print(f"Uploading: {file_name}")
        
        # This call should return a long-running operation
        operation = client.file_search_stores.upload_to_file_search_store(
            file_search_store_name=store.name,
            file=file_obj.name, # The path to the file from Gradio
            config={'display_name': file_name}
        )
        
        # Wait for the current file's operation to complete before proceeding
        yield f"Indexing `{file_name}`..."
        while not operation.done:
            time.sleep(4)
            operation = client.operations.get(operation)
        
        yield f"✅ Indexed `{file_name}`"

    yield f"✅ Ingestion complete for {len(files)} files. You can now use the Chat tab."

def chat_fn(message, history):
    """
    Handles the chat interaction, using the file search store as a tool.
    """
    # Use the file search store as a tool
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=message,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store.name]
                    )
                )
            ]
        )
    )

    return response.text

# --- Gradio UI ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# Code Impact Analysis Tool")

    with gr.Tab("Ingest Codebase"):
        gr.Markdown("## Step 1: Upload Your Code Files")
        gr.Markdown("Upload all relevant code files (`.py`, `.js`, `.ts`, `.md`, etc.). The tool will create a searchable index of your codebase.")
        file_uploader = gr.File(label="Upload Files", file_count="multiple")
        ingest_button = gr.Button("🚀 Ingest Files", variant="primary")
        ingest_status = gr.Markdown()
        
        ingest_button.click(
            fn=ingest_files, 
            inputs=[file_uploader], 
            outputs=[ingest_status],
            show_progress="hidden"
        )

    with gr.Tab("Chat"):
        gr.Markdown("## Step 2: Chat With Your Codebase")
        gr.Markdown("Ask questions about your code. For example: 'What does the `ingest_files` function do?' or 'Where is the Gemini API key configured?'")
        gr.ChatInterface(
            fn=chat_fn,
            type="messages",
            chatbot=gr.Chatbot(height=600, type="messages"),
            examples=[
                "Summarize the purpose of the main application file.",
                "What are the main dependencies in requirements.txt?",
                "Explain the `chat_fn` function and its parameters.",
            ]
        )

if __name__ == "__main__":
    demo.launch()
