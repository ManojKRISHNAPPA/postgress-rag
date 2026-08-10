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


def main() -> None:
    st.set_page_config(page_title="PostgreSQL RAG Chat", layout="wide")
    st.title("PostgreSQL RAG Chatbot (LangChain + OpenAI)")

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

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if connect_clicked:
        try:
            if not all([db_host, db_port, db_name, db_user, db_password, openai_api_key]):
                st.error("Please provide all DB fields and OpenAI API key.")
                st.stop()

            db_uri = build_db_uri(db_host, db_port, db_name, db_user, db_password)
            embeddings = OpenAIEmbeddings(model=embedding_model, api_key=openai_api_key)

            vectorstore, rebuilt = refresh_vectorstore_if_needed(
                db_uri=db_uri,
                schema=db_schema,
                row_limit=int(row_limit),
                embeddings=embeddings,
                chunk_size=int(chunk_size),
                chunk_overlap=int(chunk_overlap),
            )

            st.session_state.rag = {
                "db_uri": db_uri,
                "schema": db_schema,
                "row_limit": int(row_limit),
                "chunk_size": int(chunk_size),
                "chunk_overlap": int(chunk_overlap),
                "embedding_model": embedding_model,
                "api_key": openai_api_key,
                "model_name": model_name,
                "vectorstore": vectorstore,
            }

            if rebuilt:
                st.success("Index created/refreshed from PostgreSQL tables.")
            else:
                st.success("Index already up to date.")

        except Exception as ex:
            st.error(f"Connection/indexing error: {ex}")

    if "rag" not in st.session_state:
        st.info("Fill sidebar fields and click 'Connect / Refresh Index' to start chatting.")
        return

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_question = st.chat_input("Ask a question about your PostgreSQL data...")

    if user_question:
        st.session_state.messages.append({"role": "user", "content": user_question})
        with st.chat_message("user"):
            st.markdown(user_question)

        with st.chat_message("assistant"):
            try:
                rag = st.session_state.rag
                embeddings = OpenAIEmbeddings(model=rag["embedding_model"], api_key=rag["api_key"])

                # Auto-sync before each answer so newly created tables are embedded automatically.
                vectorstore, rebuilt = refresh_vectorstore_if_needed(
                    db_uri=rag["db_uri"],
                    schema=rag["schema"],
                    row_limit=rag["row_limit"],
                    embeddings=embeddings,
                    chunk_size=rag["chunk_size"],
                    chunk_overlap=rag["chunk_overlap"],
                )

                llm = ChatOpenAI(model=rag["model_name"], temperature=0.0, api_key=rag["api_key"])
                result = answer_question_hybrid(
                    question=user_question,
                    db_uri=rag["db_uri"],
                    schema=rag["schema"],
                    vectorstore=vectorstore,
                    llm=llm,
                )
                answer = result["answer"]

                st.markdown(answer)

                if rebuilt:
                    st.caption("Detected schema/data change. Refreshed embeddings automatically.")

                if result["mode"] == "sql" and result["sql"]:
                    st.caption("Answer mode: SQL")
                    with st.expander("Generated SQL"):
                        st.code(result["sql"], language="sql")

                if result["mode"] == "rag":
                    st.caption("Answer mode: RAG")

                with st.expander("Retrieved sources"):
                    hits = vectorstore.similarity_search(user_question, k=6)
                    for i, doc in enumerate(hits, start=1):
                        table_name = doc.metadata.get("table", "unknown")
                        st.write(f"{i}. table={table_name}")
                        st.code(doc.page_content)

                st.session_state.messages.append({"role": "assistant", "content": answer})

            except Exception as ex:
                st.error(f"Chat error: {ex}")


if __name__ == "__main__":
    main()
