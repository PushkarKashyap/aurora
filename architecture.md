
```mermaid
graph TD
    subgraph "User Interface (Gradio)"
        direction LR
        A[ui/app_ui.py]
        B[ui/ingest_tab.py]
        C[ui/chat_tab.py]

        A --> B & C
    end

    subgraph "Data & Configuration"
        direction LR
        D[repositories.json]
        E[config.yaml]
    end

    subgraph "Backend Core"
        direction LR
        F[core/tools.py]
        G[core/ingest.py]
        H[core/chat_engine.py]
        I[core/store_utils.py]
    end

    subgraph "External & Data Stores"
        direction LR
        J[Google Gemini API]
        K[Google AI File Search Stores]
        L[Knowledge Graphs]
        M[SQLite DB]
    end

    %% UI to Backend Interactions
    B -- "1. User selects/adds repo" --> F
    C -- "2. User selects repo" --> F
    F -- "Provides repo list" --> B
    F -- "Provides repo list" --> C
    D -- "Manages" --> F

    B -- "3. Ingest(repo_path)" --> G
    C -- "4a. Chat(repo_path)" --> H
    C -- "4b. Get History(repo_path)" --> M

    %% Backend Core Logic
    G -- "Uses" --> I
    H -- "Uses" --> I
    I -- "Manages Stores" --> K

    G -- "Scans files" --> F
    G -- "Creates/Updates" --> L
    G -- "Uploads to" --> K

    H -- "Sends prompts to" --> J
    H -- "Uses RAG data from" --> K
    H -- "Reads for visualization" --> L
    H -- "Logs chat to" --> M

    E -- "Reads" --> F
```

This diagram illustrates the multi-repository architecture of the Aurora Codex application. The key is that all major operations are isolated at a repository level, selected by the user in the UI.

*   **Configuration**:
    *   `config.yaml`: Main application configuration.
    *   `repositories.json`: A simple JSON file that stores the name and local path for each registered repository.

*   **User Interface (`ui/`)**:
    *   `ui/app_ui.py`: Composes the main Gradio interface with two primary tabs.
    *   `ui/ingest_tab.py`: Provides a dropdown to select a repository (from `repositories.json`) and a button to add new ones. When ingestion is triggered, it passes the selected repository's path to the backend.
    *   `ui/chat_tab.py`: Features a dropdown to switch between repository contexts. All chat interactions, history retrieval, and graph visualizations are scoped to the selected repository path.

*   **Backend Core (`core/`)**:
    *   `core/tools.py`: Contains helper functions, including the critical tools for loading the repository list from `repositories.json` and setting the active workspace path for the agent's file system tools.
    *   `core/ingest.py`: Receives a `repo_path` and handles file scanning, knowledge graph creation (`data/graphs/`), and file uploads to the appropriate data store.
    *   `core/store_utils.py`: Manages the lifecycle of Google AI File Search Stores. It ensures that each repository has its own isolated store by creating, loading, or deleting stores based on the provided `repo_path`.
    *   `core/chat_engine.py`: The main RAG and chat logic engine. It is instantiated with a specific `repo_path` and uses that path to:
        *   Interact with the correct Google AI File Search Store via `store_utils.py`.
        *   Query the corresponding knowledge graph.
        *   Filter chat history from the central SQLite database.

*   **Data Stores**:
    *   **Google AI File Search**: Each repository's vectorized data is stored in a separate, isolated File Search Store.
    *   **Knowledge Graphs**: Graph data (from AST analysis) is stored as individual JSON files in `data/graphs/`. The filename is a hash of the repository's path.
    *   **SQLite**: A single database (`aurora_history.db`) stores all chat history. A `repo_path` column is used to filter history for the UI.
