import os
import yaml
from dotenv import load_dotenv
from google import genai
from core.chat_engine import init_db
from ui.app_ui import create_ui

# --- Configuration ---
def load_config():
    """Loads configuration from .env and prompts.yaml."""
    load_dotenv()
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file")

    with open("prompts.yaml", "r") as f:
        prompts = yaml.safe_load(f)

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    return google_api_key, prompts, config

# --- Gemini Client Initialization ---
try:
    GOOGLE_API_KEY, PROMPTS, CONFIG = load_config()
    client = genai.Client(api_key=GOOGLE_API_KEY)
# except (ValueError, FileNotFoundError) as e:
except Exception as e:
    print(f"Error initializing the application: {e}")
    # Exit or handle gracefully if running in a context that allows it
    exit()

# --- Configuration Values ---
DB_NAME = CONFIG["database_name"]

# Initialize the database on startup
init_db(DB_NAME) 

# --- Gradio UI ---
if __name__ == "__main__":
    demo = create_ui(client, PROMPTS, CONFIG)
    demo.launch()
