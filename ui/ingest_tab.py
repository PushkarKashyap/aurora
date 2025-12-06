import gradio as gr
from core.ingest import ingest_files, build_knowledge_graph, view_knowledge_graph
from core.tools import add_repository, get_repositories

def create_ingest_ui(client, store, config):
    """Creates the Gradio UI for the Ingest Codebase tab."""
    with gr.Tab("Ingest Codebase"):
        with gr.Row():
            with gr.Sidebar(open=False):
                current_repos = get_repositories()
                initial_repo = current_repos[0] if current_repos else None
                
                ingest_repo_dropdown = gr.Dropdown(
                    label="Active Repository",
                    choices=current_repos,
                    value=initial_repo,
                    interactive=True,
                    allow_custom_value=True
                )
                
                view_graph_button = gr.Button("👁️ View Graph", variant="secondary")

            with gr.Column(scale=4):
                gr.Markdown("### Add a New Codebase")
                local_repo_path = gr.Textbox(label="Local Path", placeholder="e.g., C:\\Users\\me\\my-project")

                with gr.Accordion("Supported File Extensions", open=False):
                    allowed_extensions = config.get("ingestion", {}).get("allowed_extensions", [])
                    gr.Markdown(f"```\n{' '.join(allowed_extensions)}\n```")

                with gr.Row():
                    ingest_button = gr.Button("🚀 Ingest Files", variant="primary")
                    build_graph_button = gr.Button("🕸️ Build Graph", variant="secondary")

                ingest_status = gr.Textbox(label="Status", interactive=False, lines=4, show_copy_button=True)
                graph_view = gr.Code(language="json", label="Knowledge Graph", visible=False, lines=20)

        ingest_button.click(
            fn=lambda path, cfg: (add_repository(path), (yield from ingest_files(path, client, None, cfg)))[1], 
            inputs=[local_repo_path, gr.State(config)],
            outputs=[ingest_status],
            show_progress="hidden"
        )

        build_graph_button.click(
            fn=lambda path: (add_repository(path), (yield from build_knowledge_graph(path, config)))[1],
            inputs=[local_repo_path],
            outputs=[ingest_status]
        )
        
        def view_graph_handler(path, selected_repo, current_status):
            target_path = path if path and path.strip() else selected_repo
            if not target_path:
                new_status = (current_status + "\n" if current_status else "") + "❌ Error: No repository selected."
                return gr.update(visible=False), new_status
            
            json_str, msg = view_knowledge_graph(config, target_path)
            new_status = (current_status + "\n" if current_status else "") + msg
            if json_str:
                return gr.update(value=json_str, visible=True), new_status
            else:
                return gr.update(visible=False), new_status

        view_graph_button.click(
            fn=view_graph_handler,
            inputs=[local_repo_path, ingest_repo_dropdown, ingest_status],
            outputs=[graph_view, ingest_status]
        )
