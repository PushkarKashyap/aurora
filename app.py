import gradio as gr
from dotenv import load_dotenv
from rag_agent.retrieval import CodeRetrievalAgent
from typing import List, Tuple

# Load environment variables (OPENAI_API_KEY)
load_dotenv()

try:
    # 1. Initialize our RAG agent
    agent = CodeRetrievalAgent()
    print("✅ Agent initialized successfully.")

    # 2. Define the chat function for Gradio
    def query_agent(message: str, history: List[Tuple[str, str]]):
        # Gradio history already contains the current message, 
        # but we pass the history up to the current turn's START.
        answer, sources = agent.query(message, history)
        
        response = answer
        if sources:
            response += "\n\n--- 📚 SOURCES ---"
            unique_sources = set(doc.metadata.get('source', 'N/A') for doc in sources)
            for i, source_file in enumerate(unique_sources):
                response += f"\n{i+1}. {source_file.replace('./my_project_code/', '')}" # Clean up path
        return response

    # 3. Define the graph function
    def render_graph():
        mermaid_code = agent.generate_graph_mermaid()
        return mermaid_code

    # 4. Create the Gradio App with gr.Blocks and Tabs
    with gr.Blocks(theme="soft", title="🤖 Code Partner AI") as demo:
        gr.Markdown("# 🤖 Code Partner AI: Conversational RAG for Code")
        
        with gr.Tabs():
            # Chat Interface Tab
            with gr.TabItem("Chat Agent"):
                gr.ChatInterface(
                    fn=query_agent,
                    examples=[
                        "What is the function of the vector_store in the app?",
                        "Explain the purpose of the function 'create_database' in data_ingestion.py",
                        "What is the best way to run this application?",
                        "What dependency is used for embeddings?"
                    ]
                )
            
            # Dependency Graph Tab
            with gr.TabItem("Dependency Graph"):
                with gr.Column():
                    gr.Markdown("Click the button to generate and display the code dependency graph in **Mermaid syntax**.")
                    graph_btn = gr.Button("🚀 Generate Graph")
                    # gr.Markdown renders the Mermaid string as a visual graph
                    graph_output = gr.Markdown(label="Generated Graph")
                
                graph_btn.click(fn=render_graph, inputs=None, outputs=graph_output)

    # Launch the app!
    demo.launch()

except Exception as e:
    print(f"❌ An error occurred during initialization or launch: {e}")
    print("Please ensure your OPENAI_API_KEY is set and you have run 'python data_ingestion.py'.")