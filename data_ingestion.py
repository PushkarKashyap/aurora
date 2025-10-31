import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
SOURCE_DIRECTORY = "./my_project_code" # Folder containing your source code
CHROMA_PATH = "vector_store"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200 

def load_documents(directory: str):
    """Loads all text documents (including code) from the specified directory."""
    print(f"📂 Loading documents from {directory}...")
    loader = DirectoryLoader(
        path=directory, 
        glob="**/*.*", 
        loader_cls=TextLoader,
        # Exclude common non-code files
        exclude=["**/*.md", "**/*.txt", "**/*.log", "**/*.jpg", "**/*.jpeg", "**/*.png"]
    )
    documents = loader.load()
    print(f"✅ Loaded {len(documents)} documents.")
    return documents

def split_text(documents):
    """Splits the loaded documents into smaller, manageable chunks."""
    print(f"✂️ Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"✅ Created {len(chunks)} chunks.")
    return chunks

def create_database(chunks):
    """Generates embeddings using OpenAI and saves them to Chroma."""
    if "OPENAI_API_KEY" not in os.environ:
        print("❌ Error: OPENAI_API_KEY environment variable not set. Check your .env file.")
        return
        
    print("🧠 Generating embeddings and building ChromaDB...")
    
    # OpenAIEmbeddings and ChatOpenAI are now imported directly from langchain_openai
    embeddings = OpenAIEmbeddings()
    
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PATH
    )
    
    vector_store.persist()
    print(f"✅ ChromaDB saved successfully to {CHROMA_PATH}")


def main():
    """Main function to run the indexing process."""
    if not os.path.exists(SOURCE_DIRECTORY):
        print(f"❌ Error: Source directory '{SOURCE_DIRECTORY}' not found.")
        print("Please create it and place your project code inside (e.g., 'my_project_code/main.py').")
        return

    documents = load_documents(SOURCE_DIRECTORY)
    if documents:
        chunks = split_text(documents)
        create_database(chunks)


if __name__ == "__main__":
    main()