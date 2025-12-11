# 🌌 Aurora Codex

## An Advanced Conversational Assistant for Codebase Impact Analysis

---

## The Problem: The Complexity of Codebases

- Understanding the impact of a single change in a large, complex codebase is difficult, time-consuming, and error-prone.
- Developers spend significant time manually tracing dependencies and potential side effects.
- This manual process can be a major bottleneck in development and release cycles.

---

## Introducing: Aurora Codex

A conversational AI assistant that transforms codebase analysis.

- **Ask questions in natural language:** "What is the impact of changing this function?"
- **Leverages cutting-edge technology:**
    - Google Gemini API for Retrieval-Augmented Generation (RAG).
    - Python's Abstract Syntax Tree (AST) for deep code analysis.
- **Interactive Web Interface:** Built with Gradio for a clean, user-friendly experience.

---

## ✨ Key Features

- **Refactored Architecture:** Scalable design with separate `core/` (logic) and `ui/` (interface) packages.
- **Dynamic Repository Management:** Support for multiple repositories with isolated knowledge graphs and vector stores.
- **Real-time Status Updates:** Provides immediate feedback on agent activities (tool execution, thinking) via streaming updates.
- **Advanced Impact Analysis:**
  - **Criticality Assessment:** Request a prioritized analysis of impacted components, classified as High, Medium, or Low, with justifications for each.
  - **Dynamic Dependency Visualization:** Generate on-the-fly dependency graphs using Mermaid.js based on your conversation to visually understand component relationships.
- **Exportable Reports:** Download your entire impact analysis conversation as a structured Markdown report for documentation or sharing.
- **Interactive UI:**
  - A clean, themeable interface powered by Gradio.
  - Collapsible sidebar to maximize chat space.
  - Separate tabs for file ingestion, chat, and visualization.

---

## How It Works: A Detailed Workflow

1.  **Repository Selection (ui/ingest_tab.py & ui/chat_tab.py):**
    - The user selects a pre-existing repository from a dropdown or adds a new one by providing a name and local path.
    - This information is stored in `repositories.json` and managed by helper functions in `core/tools.py`.

2.  **Ingestion & Analysis (core/ingest.py):**
    - When the user clicks "Ingest Files," the system scans all relevant files in the repository's path.
    - It creates an isolated **Google AI File Search Store** for vector embeddings (managed by `core/store_utils.py`).
    - It also builds a **Knowledge Graph** by parsing Python files with the AST module, storing the result in `data/graphs/`.

3.  **Conversational Interaction (core/chat_engine.py):**
    - The user asks questions in the chat interface (`ui/chat_tab.py`).
    - The chat engine is initialized with the selected repository's path.
    - It uses the corresponding Vector Store for Retrieval-Augmented Generation (RAG) and the Knowledge Graph for structural analysis.
    - Chat history is saved to a central SQLite database (`aurora_history.db`) but filtered by repository for the user.

4.  **Visualization & Reporting (ui/app_ui.py):**
    - After an analysis, the user can click "Visualize Impact" to generate a Mermaid.js graph, which is displayed in the "Visualization" tab.
    - The entire conversation and analysis can be exported as a clean Markdown report.

---

## Technology Stack

- **Backend Logic:** Python (`core/`)
- **Language Model:** Google Gemini 2.5 Flash
- **Frontend:** Gradio (`ui/`)
- **Database:** SQLite (Chat History) & Google AI File Search (Vector Embeddings)
- **Code Analysis:** Python AST (Abstract Syntax Tree)

---

## 📂 Project Structure

```
aurora/
├── core/                   # <-- Backend Business Logic
│   ├── chat_engine.py      # <-- Chat logic, RAG, and DB ops
│   ├── ingest.py           # <-- Ingestion and knowledge graph logic
│   ├── tools.py            # <-- Agent tools (file access, repo management)
│   └── store_utils.py      # <-- Vector store management (one per repo)
├── ui/                     # <-- Frontend UI Components
│   ├── app_ui.py           # <-- Main UI composition
│   ├── chat_tab.py         # <-- Chat tab implementation
│   └── ingest_tab.py       # <-- Ingest tab implementation
├── data/
│   └── graphs/             # <-- Stores generated knowledge graphs
├── app.py                  # <-- Main application entrypoint
├── config.yaml             # <-- Application-wide configuration
├── repositories.json       # <-- Stores paths to user-added codebases
├── .env                    # <-- Local environment configuration (API keys)
├── prompts.yaml            # <-- All LLM prompts
├── requirements.txt
├── README.md
```

---

## Use Case: Deprecating a Function

**Scenario:** A developer needs to remove a function named `calculate_discount()`.

**With Aurora Codex:**

1.  **User asks:** "What is the impact of removing the `calculate_discount` function?"
2.  **Aurora Finds:** Identifies all modules and functions that call `calculate_discount()` using its Knowledge Graph for the specific repository.
3.  **Aurora Assesses:** Classifies the impact on each component.
4.  **Aurora Visualizes:** Streaming updates keep the user informed while it generates a dependency graph showing breaking changes.

---

## Architecture at a Glance

```mermaid
graph TD
    subgraph "User Interface (Gradio)"
        A[UI Tabs <br> Ingest & Chat]
    end

    subgraph "Backend Core"
        B[Chat & Ingest Logic <br> (core/)]
    end

    subgraph "Data Stores (Per-Repository)"
        C[Google AI File Search Store]
        D[Knowledge Graph]
    end

    E[Shared Chat History <br> (SQLite)]

    A -- "User selects repository" --> B
    B -- "Operates on" --> C & D
    B -- "Logs to" --> E

```

---

## Getting Started

1.  **Get a Google API Key:** From Google AI Studio.
2.  **Set Up Project:** Clone the repo and create your `.env` file.
3.  **Install Dependencies:** `pip install -r requirements.txt`
4.  **Run the App:** `python app.py`

---

## Future Roadmap

- **Multi-Language Support:** Extend analysis beyond Python to languages like JavaScript, Java, and C++.
- **IDE Integration:** Create a plugin for VS Code or JetBrains IDEs for real-time impact analysis as you code.
- **Advanced Visualizations:** Offer more interactive and detailed graph visualizations.
- **Automated Refactoring Suggestions:** Propose code modifications to fix issues identified during analysis.

---

## Thank You

### Questions?
