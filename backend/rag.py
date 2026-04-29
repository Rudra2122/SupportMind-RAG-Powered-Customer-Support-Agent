from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

PROMPT_TEMPLATE = """You are a helpful customer support agent. 
Use the following context to answer the customer's question accurately.
If you don't know the answer from the context, say so honestly.
Always cite which part of the documentation you used.

Context:
{context}

Customer question: {question}

Answer:"""

def get_rag_chain():
    embeddings = OpenAIEmbeddings()
    vectorstore = Chroma(
        persist_directory="./chroma_db",
        embedding_function=embeddings
    )
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 3} 
    )
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    prompt = PromptTemplate(
        template=PROMPT_TEMPLATE,
        input_variables=["context", "question"]
    )
    
    chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True, 
        chain_type_kwargs={"prompt": prompt}
    )
    return chain, retriever
