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

## Key Features

- **Conversational Code Analysis:** Ingest any codebase and start a conversation to understand its structure and dependencies.
- **Knowledge Graph Generation:** Automatically builds a structural map of your Python code to understand relationships between components.
- **Refactored Architecture:** Clean separation of concerns with `core/` (logic) and `ui/` (interface) packages.
- **Real-time Status Updates:** Provides immediate feedback on agent activities (tool execution, thinking) via streaming updates.
- **Dynamic Repository Management:** Support for multiple repositories with isolated knowledge graphs and vector stores.
- **Advanced Impact Analysis:**
    - **Criticality Assessment:** Prioritizes impacted components (High, Medium, Low).
    - **Dynamic Dependency Visualization:** Generates Mermaid.js graphs on-the-fly to visualize impact.
- **Exportable Reports:** Download your analysis as a structured Markdown file for documentation and sharing.

---

## How It Works: A Simple Workflow

1.  **Select or Add Repository:** The user chooses a repository from a dropdown in the UI. The list is managed by `repositories.json`.
2.  **Ingest Codebase:** For the selected repository, the system creates or loads its dedicated Vector Store and Knowledge Graph. Logic is handled by `core/ingest.py` and `core/store_utils.py`.
3.  **Chat & Analyze:** The user interacts with the AI. The chat engine (`core/chat_engine.py`) is scoped to the selected repository, ensuring all analysis, RAG, and history are contextually correct.
4.  **Visualize & Report:** The system generates dependency graphs and reports based on the analysis of the selected repository.

---

## Technology Stack

- **Backend Logic:** Python (`core/`)
- **Language Model:** Google Gemini 2.5 Flash
- **Frontend:** Gradio (`ui/`)
- **Database:** SQLite (Chat History) & Google AI File Search (Vector Embeddings)
- **Code Analysis:** Python AST (Abstract Syntax Tree)

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
