import os
import time
import gradio as gr


def get_or_create_store(client, store_display_name):
    """Gets the file search store or creates it if it doesn't exist."""
    print(f"--- Initializing File Search Store: {store_display_name} ---")

    # Check if the store already exists
    for store in client.file_search_stores.list():
        if store.display_name == store_display_name:
            print(f"Found existing store: {store.name}")
            return store

    # If not found, create a new one
    print(f"Store not found, creating a new one: {store_display_name}")
    return client.file_search_stores.create(config={'display_name': store_display_name})


def ingest_files(directory_path, client, store, config):
    """
    Finds all files in a directory, uploads them to the file search store,
    yields progress, and waits for completion.
    """
    if not directory_path or not os.path.isdir(directory_path):
        # Return a final message if the path is invalid
        yield "❌ Error: Please provide a valid directory path."
        return

    yield f"Scanning directory: {directory_path}"
    print(f"Scanning directory: {directory_path}")

    # Find all files in the directory
    all_files = []
    ignored_dirs = config["ingestion"]["ignored_directories"]
    for root, dirs, files in os.walk(directory_path):
        # Remove ignored directories from the search
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            all_files.append(os.path.join(root, file))

    if not all_files:
        yield "No files found in the specified directory."
        return

    yield f"Found {len(all_files)} files. Ingesting... This may take a few minutes."
    print(f"Ingesting {len(all_files)} files...")

    # Process one file at a time
    for file_path in all_files:
        file_name = os.path.basename(file_path)
        yield f"Uploading `{file_name}`..."
        print(f"Uploading: {file_name} from {file_path}")

        try:
            upload_config = {'display_name': file_name}

            # Get file extension and map to mime type
            mime_type_map = config.get("mime_type_map", {})
            file_ext = os.path.splitext(file_name)[1].lower()

            if file_ext in mime_type_map:
                upload_config['mime_type'] = mime_type_map[file_ext]
            else:
                # Default to plain text if mime type is not mapped
                upload_config['mime_type'] = 'text/plain'

            # This call should return a long-running operation
            operation = client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store.name,
                file=file_path,
                config=upload_config
            )

            # Wait for the current file's operation to complete before proceeding
            yield f"Indexing `{file_name}`..."
            while not operation.done:
                time.sleep(4)
                operation = client.operations.get(operation)

            yield f"✅ Indexed `{file_name}`"
        except Exception as e:
            yield f"❌ Error indexing `{file_name}`: {e}"
            print(f"Error indexing {file_name}: {e}")

    final_message = f"✅ Ingestion complete for {len(all_files)} files. You can now use the Chat tab."
    yield final_message


def create_ingest_ui(client, store, config, delete_store_fn):
    """Creates the Gradio UI for the Ingest Codebase tab."""
    with gr.Tab("Ingest Codebase"):
        gr.Markdown("## Provide Local Codebase Path")
        gr.Markdown("Enter the local path to your codebase. The tool will scan this directory and create a searchable index of your files.")
        local_repo_path = gr.Textbox(label="Local Codebase Path", placeholder="e.g., /path/to/my/local/repo")
        with gr.Row():
            ingest_button = gr.Button("🚀 Ingest Files", variant="primary")
            delete_store_button = gr.Button("🗑️ Delete Store", variant="stop")
        ingest_status = gr.Markdown()

        ingest_button.click(
            fn=lambda path, cfg: (yield from ingest_files(path, client, store, cfg)),
            inputs=[local_repo_path, gr.State(config)],
            outputs=[ingest_status],
            show_progress="hidden"
        )

        delete_store_button.click(
            fn=delete_store_fn,
            inputs=[],
            outputs=[ingest_status]
        )