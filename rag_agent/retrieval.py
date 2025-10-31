import os
import yaml
from typing import List, Tuple
from langchain_core.prompts import PromptTemplate

import os
import yaml
from typing import List, Tuple
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from langchain_core.runnables import RunnablePassthrough

PROMPT_FILE = os.path.join(os.path.dirname(__file__), '..', 'prompts.yaml')
VECTOR_STORE_PATH = "vector_store"

class CodeRetrievalAgent:
    def __init__(self):
        # Load Prompts
        self.prompts = self._load_prompts()

        # Initialize LLM and Embeddings
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY not set in environment variables.")
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        self.embeddings = OpenAIEmbeddings()

        # Initialize Vector Store and Retriever
        if not os.path.exists(VECTOR_STORE_PATH):
            raise FileNotFoundError(f"Vector store not found at '{VECTOR_STORE_PATH}'. Please run data_ingestion.py first.")
        self.vector_store = Chroma(
            persist_directory=VECTOR_STORE_PATH,
            embedding_function=self.embeddings
        )
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 50})

        # Define the LCEL RAG chain
        prompt = ChatPromptTemplate.from_template(
            self.prompts.get('retrieval_prompt', "Answer the following question using the provided context.\n\nContext:\n{context}\n\nQuestion: {input}")
        )
        self.qa_chain = (
            {
                "input": RunnablePassthrough(),
                "context": (lambda x: x["input"]) | self.retriever | (lambda docs: "\n\n".join([doc.page_content for doc in docs]))
            }
            | prompt
            | self.llm
        )

    def _load_prompts(self):
        try:
            with open(PROMPT_FILE, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Error loading YAML prompts: {e}")

    def query(self, question: str, history: List[Tuple[str, str]]):
        # For now, history is not used. You can extend this for chat memory.
        result = self.qa_chain.invoke({"input": question})
        answer = result.content if hasattr(result, 'content') else str(result)
        # Optionally, you can return sources if you want to extend the chain
        return answer, []

    def generate_graph_mermaid(self):
        # Retrieve a broad set of documents for the overall code structure
        all_docs = self.vector_store.similarity_search(query="function class module", k=50)
        context_text = "\n---\n".join([doc.page_content for doc in all_docs])
        # Use the LLM directly for Mermaid generation
        mermaid_prompt = self.prompts.get('mermaid_prompt', "")
        response = self.llm.invoke(f"{mermaid_prompt}\n\n{context_text}")
        return response.content