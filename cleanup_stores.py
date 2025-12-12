import os
from dotenv import load_dotenv
from google import genai

def cleanup_stores():
    """
    Connects to the Google AI API, lists all file search stores, 
    and allows the user to select which store(s) to delete.
    """
    try:
        load_dotenv()
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            print("❌ Error: GOOGLE_API_KEY not found in .env file.")
            return

        print("--- Initializing Google AI Client ---")
        client = genai.Client(api_key=google_api_key)

        stores = list(client.file_search_stores.list())
        if not stores:
            print("✅ No file search stores found to delete.")
            return

        while True:
            print("\nAvailable file search stores:")
            for i, store in enumerate(stores):
                print(f"  [{i+1}] {store.display_name} ({store.name})")

            print("\nSelect a store to delete, or choose an option:")
            print("  [a] Delete ALL stores")
            print("  [q] Quit")

            choice = input("\nEnter your choice (e.g., 1, a, q): ").lower().strip()

            if choice == 'q':
                print("\nAborted. No stores were deleted.")
                break
            
            elif choice == 'a':
                confirm = input("\nAre you sure you want to delete ALL of these stores? This is permanent. (yes/no): ").lower().strip()
                if confirm == 'yes':
                    print("\n--- Starting Deletion Process (ALL) ---")
                    for store in stores:
                        try:
                            print(f"Deleting store: {store.display_name} ({store.name})...")
                            client.file_search_stores.delete(name=store.name, config={'force': True})
                            print(f"✅ Deleted successfully.")
                        except Exception as e:
                            print(f"❌ Failed to delete {store.display_name}: {e}")
                    print("\n--- All Stores Deleted ---")
                    break 
                else:
                    print("\nAborted. No stores were deleted.")
                    break

            elif choice.isdigit() and 1 <= int(choice) <= len(stores):
                store_index = int(choice) - 1
                selected_store = stores[store_index]
                
                confirm = input(f"\nAre you sure you want to permanently delete '{selected_store.display_name}'? (yes/no): ").lower().strip()
                
                if confirm == 'yes':
                    try:
                        print(f"--- Deleting Store: {selected_store.display_name} ---")
                        client.file_search_stores.delete(name=selected_store.name, config={'force': True})
                        print(f"✅ Deleted successfully.")
                        # Refresh the list
                        stores.pop(store_index) 
                        if not stores:
                            print("\nAll stores have been deleted.")
                            break
                    except Exception as e:
                        print(f"❌ Failed to delete {selected_store.display_name}: {e}")
                else:
                    print("Aborted.")
            
            else:
                print("❌ Invalid choice. Please try again.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    cleanup_stores()