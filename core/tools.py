import os
import json
import ast
import yaml # Added import

# Tool Definitions for Gemini
from google.genai import types

# Global state for the active workspace
_WORKSPACE_PATH = "."

def set_workspace_path(path):
    """
    Sets the active workspace path for the agent. 
    All subsequent relative file operations will be based on this path.
    """
    global _WORKSPACE_PATH
    if not path:
        return "Error: No path provided."
    if not os.path.exists(path):
        return f"Error: Path '{path}' does not exist."
    _WORKSPACE_PATH = path
    return f"Workspace path set to: {_WORKSPACE_PATH}"

import hashlib

def get_graph_path(repo_path):
    """
    Returns the centralized path for the knowledge graph JSON based on the repo path hash.
    Ensures the directory exists.
    """
    if not repo_path:
        return None
    
    # Create a unique filename based on the repository path
    repo_hash = hashlib.md5(repo_path.encode('utf-8')).hexdigest()
    filename = f"graph_{repo_hash}.json"
    
    # Store in data/graphs/ relative to the application root
    # Assuming running from 'aurora' root directory
    base_dir = os.path.join(os.getcwd(), "data", "graphs")
    os.makedirs(base_dir, exist_ok=True)
    
    return os.path.join(base_dir, filename)

def get_repositories():
    """Available repositories from persistent storage."""
    repo_file = "repositories.json"
    if os.path.exists(repo_file):
        with open(repo_file, "r") as f:
            return json.load(f)
    return []

def add_repository(path):
    """Adds a repository path to persistent storage if it exists."""
    if not os.path.exists(path):
         return False
    
    repos = get_repositories()
    if path not in repos:
        repos.append(path)
        with open("repositories.json", "w") as f:
            json.dump(repos, f)
    return True

def list_files(directory_path=None):
    """
    Lists all files in the given directory, respecting ignored directories from config.yaml.
    If directory_path is not provided, uses the current active workspace.
    """
    target_dir = directory_path if directory_path else _WORKSPACE_PATH
    try:
        files_list = []
        
        # Load ignored directories from config.yaml
        config_path = os.path.join(os.getcwd(), "config.yaml") # Assuming config.yaml is in the project root
        all_ignored_dirs = set() # Initialize an empty set
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)
            all_ignored_dirs = set(config_data.get("ingestion", {}).get("ignored_directories", []))
        
        for root, dirs, files in os.walk(target_dir):
            # Skip irrelevant directories (including those starting with '.')
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in all_ignored_dirs]
            
            for file in files:
                if not file.startswith('.'):
                    files_list.append(os.path.join(root, file))
        
        # Serialize and truncate if massive
        output = json.dumps(files_list)
        if len(output) > 50000:
            return f"Error: File list is too long ({len(output)} chars). Truncated. Found {len(files_list)} files. Please list a specific subdirectory."
            
        return output
    except Exception as e:
        return f"Error listing files: {e}"

def read_file(file_path):
    """
    Reads the content of a specific file. 
    Resolves relative paths against the active workspace.
    """
    try:
        # Resolve path against workspace if it's relative
        if not os.path.isabs(file_path):
            full_path = os.path.join(_WORKSPACE_PATH, file_path)
        else:
            full_path = file_path

        # Basic security check to prevent traversing above the intended root (optional, but good practice)
        # For a personal tool, we might be lenient, but let's keep basic ".." check relative to the resolved path?
        # Actually, allowing absolute paths implies trust. Let's just check existence.
        
        if not os.path.exists(full_path):
            return f"Error: File '{full_path}' does not exist."

        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading file: {e}"

def search_knowledge_graph(query, repo_path=None):
    """
    Searches the centralized knowledge graph for nodes or edges matching the query.
    Useful for finding relationships between components.
    If repo_path is provided, uses that; otherwise falls back to _WORKSPACE_PATH.
    """
    try:
        # Use provided repo_path or fall back to global workspace
        target_path = repo_path if repo_path else _WORKSPACE_PATH
        graph_path = get_graph_path(target_path)
        
        if not graph_path or not os.path.exists(graph_path):
             return f"Error: Knowledge graph not found for '{target_path}'. Please build it first on the Ingest page."

        with open(graph_path, 'r', encoding='utf-8') as f:
            graph = json.load(f)
        
        results = {"nodes": [], "edges": []}
        query_lower = query.lower()

        for node in graph.get("nodes", []):
            if query_lower in node.get("id", "").lower() or query_lower in node.get("file", "").lower():
                results["nodes"].append(node)
        
        for edge in graph.get("edges", []):
            if query_lower in edge.get("source", "").lower() or query_lower in edge.get("target", "").lower():
                results["edges"].append(edge)
                
        return json.dumps(results, indent=2)

    except Exception as e:
        return f"Error searching knowledge graph: {e}"

def get_tool_definitions():
    """
    Returns the function declarations for the Gemini API.
    """
    return [
        types.FunctionDeclaration(
            name="set_workspace_path",
            description="Sets the active workspace/repository path. Call this first when switching to a new repository.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(
                        type="STRING",
                        description="The absolute path to the repository root."
                    )
                },
                required=["path"]
            )
        ),
        types.FunctionDeclaration(
            name="list_files",
            description="Lists all files in the active workspace or a specific directory.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "directory_path": types.Schema(
                        type="STRING",
                        description="Optional specific directory to list. If omitted, lists the current workspace."
                    )
                },
            )
        ),
        types.FunctionDeclaration(
            name="read_file",
            description="Reads the content of a specific file.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "file_path": types.Schema(
                        type="STRING",
                        description="The path of the file to read (relative to workspace or absolute)."
                    )
                },
                required=["file_path"]
            )
        ),
        types.FunctionDeclaration(
            name="search_knowledge_graph",
            description="Searches the centralized knowledge graph for nodes or edges matching the query. Use repo_path to specify which repository's graph to search.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(
                        type="STRING",
                        description="The search query string (e.g., 'chat_fn', 'ingest')."
                    ),
                    "repo_path": types.Schema(
                        type="STRING",
                        description="Optional. The absolute path to the repository whose graph to search. If omitted, uses the active workspace."
                    )
                },
                required=["query"]
            )
        )
    ]
