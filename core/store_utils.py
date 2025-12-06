import os

def get_store_name(directory_path):
    """Generates a consistent store display name based on the directory path."""
    if not directory_path or directory_path == ".":
        return "Aurora Store - Current"
    
    # Use the directory name as the identifier
    folder_name = os.path.basename(os.path.abspath(directory_path))
    return f"Aurora Store - {folder_name}"

def get_or_create_store(client, directory_path):
    """
    Gets the file search store for a specific repository or creates it if it doesn't exist.
    """
    store_display_name = get_store_name(directory_path)
    print(f"--- Accessing Store: {store_display_name} ---")

    # Check if the store already exists
    # Note: listing all stores might be slow if there are many. 
    # For a personal tool, this is acceptable.
    for store in client.file_search_stores.list():
        if store.display_name == store_display_name:
            # print(f"Found existing store: {store.name}")
            return store

    # If not found, create a new one
    print(f"Store not found, creating a new one: {store_display_name}")
    return client.file_search_stores.create(config={'display_name': store_display_name})
