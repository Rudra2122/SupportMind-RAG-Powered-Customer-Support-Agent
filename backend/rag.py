from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.llms import Ollama

PROMPT_TEMPLATE = """You are a helpful customer support agent.
Use the following context to answer the customer's question accurately.
If you don't know the answer from the context, say so honestly.

Context:
{context}

Question: {question}

Answer:"""

def get_rag_chain():
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    vectorstore = Chroma(
        persist_directory="./chroma_db",
        embedding_function=embeddings
    )

    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    # 🔥 Local LLM via Ollama
    llm = Ollama(model="llama3")   # or "mistral"

    class SimpleRAG:
        def invoke(self, inputs):
            question = inputs["query"]

            docs = retriever.invoke(question)
            context = "\n\n".join([doc.page_content for doc in docs])

            prompt = PROMPT_TEMPLATE.format(
                context=context,
                question=question
            )

            response = llm.invoke(prompt)

            return {
                "result": response,
                "source_documents": docs
            }

    return SimpleRAG(), retriever