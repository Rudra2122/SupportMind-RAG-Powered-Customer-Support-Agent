from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv
import glob
import shutil
import os

load_dotenv()

def ingest_docs():
    docs = []

    # Load .txt files
    for path in glob.glob("docs/*.txt"):
        loader = TextLoader(path)
        docs.extend(loader.load())

    # Load .pdf files
    for path in glob.glob("docs/*.pdf"):
        loader = PyPDFLoader(path)
        docs.extend(loader.load())

    if not docs:
        print("No documents found in docs/ folder")
        return None

    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )
    chunks = splitter.split_documents(docs)
    print(f"Ingested {len(chunks)} chunks from {len(docs)} documents")

    # Delete old ChromaDB if it exists
    if os.path.exists("./chroma_db"):
        shutil.rmtree("./chroma_db")
        print("Old ChromaDB deleted")

    # Free local embeddings, no OpenAI quota needed
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # Embed and store in ChromaDB
    vectorstore = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory="./chroma_db"
    )

    print("ChromaDB vector store created successfully")
    return vectorstore

if __name__ == "__main__":
    ingest_docs()