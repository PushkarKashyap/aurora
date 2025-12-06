import os
import time
import json
import ast
from core.store_utils import get_or_create_store
from core.tools import get_tool_definitions, list_files, read_file, search_knowledge_graph, set_workspace_path, get_repositories, get_graph_path



def ingest_files(directory_path, client, _, config): # store arg is ignored/deprecated
    """
    Finds all files in a directory, uploads them to the file search store,
    yields progress, and waits for completion.
    """
    log_messages = []
    def log(message):
        log_messages.append(message)
        return "\n".join(log_messages)

    if not directory_path or not os.path.isdir(directory_path):
        yield log("❌ Error: Please provide a valid directory path.")
        return

    # Dynamically get the correct store for this repo
    try:
        store = get_or_create_store(client, directory_path)
    except Exception as e:
        yield log(f"❌ Error connecting to Gemini Store: {e}")
        return

    yield log(f"Connected to: {store.display_name} ({store.name})")
    yield log(f"Scanning directory: {directory_path}")
    print(f"Scanning directory: {directory_path}")

    # Find all files in the directory
    all_files = []
    ignored_dirs = config["ingestion"]["ignored_directories"]
    ignored_files = config["ingestion"].get("ignored_files", [])
    allowed_extensions = config["ingestion"].get("allowed_extensions", [])

    for root, dirs, files in os.walk(directory_path):
        # Remove ignored directories from the search
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if file.startswith('.'):
                continue
            if file in ignored_files:
                continue
            if allowed_extensions and not any(file.endswith(ext) for ext in allowed_extensions):
                continue
            all_files.append(os.path.join(root, file))

    if not all_files:
        yield log("No files found in the specified directory.")
        return

    total_files = len(all_files)
    yield log(f"Found {total_files} files. Ingesting... This may take a few minutes.")
    print(f"Ingesting {total_files} files...")

    # Process one file at a time
    for i, file_path in enumerate(all_files):
        file_name = os.path.basename(file_path)
        progress_prefix = f"[{i+1}/{total_files}]"
        yield log(f"{progress_prefix} Uploading `{file_name}`...")
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

            print(f"DEBUG: File '{file_name}' ext='{file_ext}' mime_type='{upload_config['mime_type']}'")

            # This call should return a long-running operation
            operation = client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store.name,
                file=file_path,
                config=upload_config
            )

            # Wait for the current file's operation to complete before proceeding
            yield log(f"{progress_prefix} Indexing `{file_name}`...")
            while not operation.done:
                time.sleep(4)
                operation = client.operations.get(operation)

            yield log(f"✅ {progress_prefix} Indexed `{file_name}`")
        except Exception as e:
            yield log(f"❌ {progress_prefix} Error indexing `{file_name}`: {e}")
            print(f"Error indexing {file_name}: {e}")

    yield log(f"✅ Ingestion complete for {total_files} files. You can now use the Chat tab.")


class CodeAnalyzer(ast.NodeVisitor):
    """
    An AST node visitor that extracts nodes (files, functions, classes)
    and edges (imports, calls) from Python code.
    """
    def __init__(self, file_name):
        self.file_name = file_name
        self.nodes = []
        self.edges = []
        self.current_scope = file_name  # Start with file-level scope

    def visit_FunctionDef(self, node):
        self.nodes.append({"id": node.name, "type": "function", "file": self.file_name})
        parent_scope = self.current_scope
        self.current_scope = node.name
        self.generic_visit(node)
        self.current_scope = parent_scope

    def visit_ClassDef(self, node):
        self.nodes.append({"id": node.name, "type": "class", "file": self.file_name})
        parent_scope = self.current_scope
        self.current_scope = node.name
        self.generic_visit(node)
        self.current_scope = parent_scope

    def visit_Import(self, node):
        for alias in node.names:
            self.edges.append({"source": self.file_name, "target": alias.name, "type": "imports"})
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.edges.append({"source": self.file_name, "target": node.module, "type": "imports"})
        self.generic_visit(node)

    def visit_Call(self, node):
        # This is a simplified call analysis. It captures direct function names.
        if isinstance(node.func, ast.Name):
            self.edges.append({"source": self.current_scope, "target": node.func.id, "type": "calls"})
        self.generic_visit(node)


def build_knowledge_graph(directory_path, config):
    """
    Scans a directory, uses Python's AST module to extract entities and relationships
    from .py files, and builds a knowledge graph.
    """
    log_messages = []
    def log(message):
        log_messages.append(message)
        return "\n".join(log_messages)

    if not directory_path or not os.path.isdir(directory_path):
        yield log("❌ Error: Please provide a valid directory path to build the graph.")
        return

    yield log(f"Scanning directory for graph construction: {directory_path}")
    python_files = []
    ignored_dirs = config["ingestion"]["ignored_directories"]
    ignored_files = config["ingestion"].get("ignored_files", [])
    for root, dirs, files in os.walk(directory_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if file.startswith('.'):
                continue
            if file in ignored_files:
                continue
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    if not python_files:
        yield log("No Python (.py) files found to build graph.")
        return

    yield log(f"Found {len(python_files)} Python files. Building knowledge graph...")
    knowledge_graph = {"nodes": [], "edges": []}
    existing_node_ids = set()

    for file_path in python_files:
        file_name = os.path.basename(file_path)
        yield log(f"Analyzing `{file_name}`...")
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if not content.strip():
                yield log(f"Skipping empty file: `{file_name}`")
                continue

            # Add the file itself as a node
            if file_name not in existing_node_ids:
                knowledge_graph["nodes"].append({"id": file_name, "type": "file", "file": file_name})
                existing_node_ids.add(file_name)

            # Parse the code and analyze it
            tree = ast.parse(content)
            analyzer = CodeAnalyzer(file_name)
            analyzer.visit(tree)

            # Aggregate nodes and edges, avoiding duplicates
            for node in analyzer.nodes:
                if node.get("id") not in existing_node_ids:
                    knowledge_graph["nodes"].append(node)
                    existing_node_ids.add(node.get("id"))
            knowledge_graph["edges"].extend(analyzer.edges)

        except Exception as e:
            yield log(f"❌ Error analyzing `{file_name}`: {e}")

    # Remove duplicates from edges
    unique_edges = {f"{e['source']}-{e['target']}-{e['type']}": e for e in knowledge_graph["edges"]}
    knowledge_graph["edges"] = list(unique_edges.values())

    graph_file_path = get_graph_path(directory_path)

    if not graph_file_path:
        yield log("❌ Error: Could not generate graph path.")
        return

    try:
        with open(graph_file_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_graph, f, indent=2)
        yield log(f"✅ Knowledge graph built successfully and saved to `{graph_file_path}`.")
    except Exception as e:
        yield log(f"❌ Error saving knowledge graph: {e}")


def view_knowledge_graph(config, repo_path):
    """
    Reads the knowledge graph from the JSON file and returns it for display.
    """
    if not repo_path:
        return None, "❌ Error: No repository selected."

    graph_file_path = get_graph_path(repo_path)
    
    if not graph_file_path:
        return None, "❌ Error: Could not determine graph path."

    if not os.path.exists(graph_file_path):
        return None, f"❌ Error: Knowledge graph file not found at `{graph_file_path}`. Please build it first."

    try:
        with open(graph_file_path, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        json_string = json.dumps(graph_data, indent=2)
        return json_string, "✅ Knowledge graph loaded."
    except Exception as e:
        return None, f"❌ Error reading or parsing knowledge graph file: {e}"