from core.tools import list_files, read_file, search_knowledge_graph, get_graph_path
import json
import os

def test_tools():
    print("Testing list_files...")
    files_json = list_files(".")
    files = json.loads(files_json) if not files_json.startswith("Error") else []
    if "app.py" in str(files):
        print("[PASS] list_files passed")
    else:
        print(f"[FAIL] list_files failed: {files_json}")

    print("\nTesting read_file...")
    content = read_file("requirements.txt")
    if "google-genai" in content:
        print("[PASS] read_file passed")
    else:
        print(f"[FAIL] read_file failed: {content}")

    print("\nTesting search_knowledge_graph (assuming graph exists)...")
    # Use the centralized graph path
    graph_path = get_graph_path(".")
    if graph_path and os.path.exists(graph_path):
        result = search_knowledge_graph("chat")
        if "nodes" in result:
             print("[PASS] search_knowledge_graph passed")
        else:
             print(f"[FAIL] search_knowledge_graph failed: {result}")
    else:
        print(f"[WARN] Centralized knowledge graph does not exist at '{graph_path}'. Skipping graph test.")

if __name__ == "__main__":
    test_tools()
