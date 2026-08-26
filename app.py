import os

import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from rag_core import (
    answer_question_hybrid,
    build_db_uri,
    refresh_vectorstore_if_needed,
)


# Load .env values as optional defaults for DB fields.
# OpenAI key is intentionally entered in the UI, not loaded from .env.
load_dotenv()


def render_connection_sidebar() -> tuple[dict, bool]:
    with st.sidebar:
        st.header("Connection")

        db_host = st.text_input("DB Host", value=os.getenv("DB_HOST", ""))
        db_port = st.text_input("DB Port", value=os.getenv("DB_PORT", "5432"))
        db_name = st.text_input("DB Name", value=os.getenv("DB_NAME", ""))
        db_user = st.text_input("DB User", value=os.getenv("DB_USER", ""))
        db_password = st.text_input("DB Password", type="password", value=os.getenv("DB_PASSWORD", ""))
        db_schema = st.text_input("Schema", value=os.getenv("DB_SCHEMA", "public"))
        row_limit = st.number_input("Rows per table to ingest", min_value=100, max_value=100000, value=5000, step=100)
        chunk_size = st.number_input("Chunk size", min_value=200, max_value=4000, value=700, step=50)
        chunk_overlap = st.number_input("Chunk overlap", min_value=0, max_value=1000, value=120, step=20)

        st.header("OpenAI")
        # As requested, OpenAI key is entered directly in UI.
        openai_api_key = st.text_input("OpenAI API Key", type="password")
        model_name = st.text_input("Model", value="gpt-4o-mini")
        embedding_model = st.text_input("Embedding Model", value="text-embedding-3-small")

        connect_clicked = st.button("Connect / Refresh Index", type="primary")

    settings = {
        "db_host": db_host,
        "db_port": db_port,
        "db_name": db_name,
        "db_user": db_user,
        "db_password": db_password,
        "db_schema": db_schema,
        "row_limit": int(row_limit),
        "chunk_size": int(chunk_size),
        "chunk_overlap": int(chunk_overlap),
        "openai_api_key": openai_api_key,
        "model_name": model_name,
        "embedding_model": embedding_model,
    }
    return settings, connect_clicked


def connect_to_database(settings: dict) -> None:
    required = [
        settings["db_host"], settings["db_port"], settings["db_name"],
        settings["db_user"], settings["db_password"], settings["openai_api_key"],
    ]
    if not all(required):
        st.error("Please provide all DB fields and OpenAI API key.")
        return

    db_uri = build_db_uri(
        settings["db_host"], settings["db_port"], settings["db_name"],
        settings["db_user"], settings["db_password"],
    )
    embeddings = OpenAIEmbeddings(
        model=settings["embedding_model"], api_key=settings["openai_api_key"]
    )
    vectorstore, rebuilt = refresh_vectorstore_if_needed(
        db_uri=db_uri, schema=settings["db_schema"], row_limit=settings["row_limit"],
        embeddings=embeddings, chunk_size=settings["chunk_size"],
        chunk_overlap=settings["chunk_overlap"],
    )

    st.session_state.rag = {
        "db_uri": db_uri,
        "schema": settings["db_schema"],
        "row_limit": settings["row_limit"],
        "chunk_size": settings["chunk_size"],
        "chunk_overlap": settings["chunk_overlap"],
        "embedding_model": settings["embedding_model"],
        "api_key": settings["openai_api_key"],
        "model_name": settings["model_name"],
        "vectorstore": vectorstore,
    }
    message = (
        "Index created/refreshed from PostgreSQL tables."
        if rebuilt else "Index already up to date."
    )
    st.success(message)


def render_retrieved_sources(vectorstore, question: str) -> None:
    with st.expander("Retrieved sources"):
        hits = vectorstore.similarity_search(question, k=6)
        for index, doc in enumerate(hits, start=1):
            table_name = doc.metadata.get("table", "unknown")
            st.write(f"{index}. table={table_name}")
            st.code(doc.page_content)


def answer_user_question(question: str) -> None:
    rag = st.session_state.rag
    embeddings = OpenAIEmbeddings(model=rag["embedding_model"], api_key=rag["api_key"])
    vectorstore, rebuilt = refresh_vectorstore_if_needed(
        db_uri=rag["db_uri"], schema=rag["schema"], row_limit=rag["row_limit"],
        embeddings=embeddings, chunk_size=rag["chunk_size"],
        chunk_overlap=rag["chunk_overlap"],
    )
    llm = ChatOpenAI(model=rag["model_name"], temperature=0.0, api_key=rag["api_key"])
    result = answer_question_hybrid(
        question=question, db_uri=rag["db_uri"], schema=rag["schema"],
        vectorstore=vectorstore, llm=llm,
    )
    st.markdown(result["answer"])

    if rebuilt:
        st.caption("Detected schema/data change. Refreshed embeddings automatically.")
    if result["mode"] == "sql" and result["sql"]:
        st.caption("Answer mode: SQL")
        with st.expander("Generated SQL"):
            st.code(result["sql"], language="sql")
    if result["mode"] == "rag":
        st.caption("Answer mode: RAG")
    render_retrieved_sources(vectorstore, question)
    st.session_state.messages.append({"role": "assistant", "content": result["answer"]})


def render_chat() -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_question = st.chat_input("Ask a question about your PostgreSQL data...")
    if not user_question:
        return

    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.markdown(user_question)
    with st.chat_message("assistant"):
        try:
            answer_user_question(user_question)
        except Exception as ex:
            st.error(f"Chat error: {ex}")


def main() -> None:
    st.set_page_config(page_title="PostgreSQL RAG Chat", layout="wide")
    st.title("PostgreSQL RAG Chatbot (LangChain + OpenAI)")
    settings, connect_clicked = render_connection_sidebar()
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if connect_clicked:
        try:
            connect_to_database(settings)

        except Exception as ex:
            st.error(f"Connection/indexing error: {ex}")

    if "rag" not in st.session_state:
        st.info("Fill sidebar fields and click 'Connect / Refresh Index' to start chatting.")
        return
    render_chat()


if __name__ == "__main__":
    main()
