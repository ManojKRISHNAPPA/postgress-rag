import json
import os
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import quote_plus

import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


# Load .env values as optional defaults for DB fields.
# OpenAI key is intentionally entered in the UI, not loaded from .env.
load_dotenv()

APP_DIR = Path(__file__).parent
CACHE_DIR = APP_DIR / ".cache"
INDEX_DIR = CACHE_DIR / "faiss_index"
FINGERPRINT_FILE = CACHE_DIR / "table_fingerprints.json"


def build_db_uri(host: str, port: str, database: str, user: str, password: str) -> str:
    """Build a SQLAlchemy-compatible PostgreSQL URI."""
    safe_password = quote_plus(password)
    return f"postgresql+psycopg2://{user}:{safe_password}@{host}:{port}/{database}"


def get_table_fingerprint(db_uri: str, schema: str) -> Dict[str, Dict[str, object]]:
    """Return a lightweight signature of schema tables to detect new/changed tables."""
    engine = create_engine(db_uri)
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names(schema=schema))

    result: Dict[str, Dict[str, object]] = {}
    with engine.connect() as conn:
        for table_name in tables:
            columns = inspector.get_columns(table_name, schema=schema)
            column_names = [col["name"] for col in columns]

            # Counting rows lets us detect new data quickly without heavy checksums.
            qualified = f'"{schema}"."{table_name}"'
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {qualified}")) .scalar_one()

            result[table_name] = {
                "columns": column_names,
                "row_count": int(row_count),
            }

    return result


def load_saved_fingerprint() -> Dict[str, Dict[str, object]]:
    if not FINGERPRINT_FILE.exists():
        return {}
    return json.loads(FINGERPRINT_FILE.read_text())


def save_fingerprint(fingerprint: Dict[str, Dict[str, object]]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    FINGERPRINT_FILE.write_text(json.dumps(fingerprint, indent=2))


def table_to_documents(db_uri: str, schema: str, row_limit: int) -> List[Document]:
    """Read all tables and convert each row into searchable text documents."""
    engine = create_engine(db_uri)
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names(schema=schema))

    docs: List[Document] = []
    metadata = MetaData(schema=schema)

    with engine.connect() as conn:
        for table_name in tables:
            table = Table(table_name, metadata, autoload_with=engine)
            rows = conn.execute(select(table).limit(row_limit)).mappings().all()

            for idx, row in enumerate(rows):
                text_lines = [f"Table: {table_name}"]
                for col_name, value in row.items():
                    text_lines.append(f"{col_name}: {value}")

                docs.append(
                    Document(
                        page_content="\n".join(text_lines),
                        metadata={
                            "table": table_name,
                            "schema": schema,
                            "row_number": idx,
                        },
                    )
                )

    return docs


def refresh_vectorstore_if_needed(
    db_uri: str,
    schema: str,
    row_limit: int,
    embeddings: OpenAIEmbeddings,
) -> Tuple[FAISS, bool]:
    """
    Ensure vector index stays in sync with PostgreSQL tables.

    Rebuilds when:
    - no local index exists
    - table/row-count fingerprint changes (new table or updated data)
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    latest_fingerprint = get_table_fingerprint(db_uri, schema)
    saved_fingerprint = load_saved_fingerprint()

    index_exists = INDEX_DIR.exists() and any(INDEX_DIR.iterdir())
    requires_rebuild = (not index_exists) or (latest_fingerprint != saved_fingerprint)

    if requires_rebuild:
        docs = table_to_documents(db_uri=db_uri, schema=schema, row_limit=row_limit)
        if not docs:
            raise ValueError("No rows found in the selected schema/tables.")

        vectorstore = FAISS.from_documents(docs, embeddings)
        vectorstore.save_local(str(INDEX_DIR))
        save_fingerprint(latest_fingerprint)
        return vectorstore, True

    vectorstore = FAISS.load_local(
        str(INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    return vectorstore, False


def format_docs(docs: List[Document]) -> str:
    formatted = []
    for d in docs:
        table_name = d.metadata.get("table", "unknown")
        formatted.append(f"[source_table={table_name}]\n{d.page_content}")
    return "\n\n".join(formatted)


def build_rag_chain(vectorstore: FAISS, model_name: str, api_key: str):
    retriever = vectorstore.as_retriever(search_kwargs={"k": 6})
    llm = ChatOpenAI(model=model_name, temperature=0.0, api_key=api_key)

    # Chatbot pipeline:
    # 1) User question
    # 2) Retriever fetches related rows from vector DB
    # 3) Prompt combines retrieved context + question
    # 4) OpenAI model generates final answer
    prompt = ChatPromptTemplate.from_template(
        """
You are a PostgreSQL RAG assistant.
Use only the context below when answering.
If the answer is not in context, say you do not know.

Context:
{context}

Question:
{question}

Answer in concise business language.
""".strip()
    )

    chain = (
        {
            "context": retriever | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
    )

    return chain, retriever


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
            )

            chain, retriever = build_rag_chain(vectorstore, model_name=model_name, api_key=openai_api_key)

            st.session_state.rag = {
                "db_uri": db_uri,
                "schema": db_schema,
                "row_limit": int(row_limit),
                "embedding_model": embedding_model,
                "api_key": openai_api_key,
                "model_name": model_name,
                "vectorstore": vectorstore,
                "chain": chain,
                "retriever": retriever,
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
                )

                chain, retriever = build_rag_chain(
                    vectorstore,
                    model_name=rag["model_name"],
                    api_key=rag["api_key"],
                )

                response = chain.invoke(user_question)
                answer = response.content if hasattr(response, "content") else str(response)

                st.markdown(answer)

                if rebuilt:
                    st.caption("Detected schema/data change. Refreshed embeddings automatically.")

                with st.expander("Retrieved sources"):
                    hits = retriever.invoke(user_question)
                    for i, doc in enumerate(hits, start=1):
                        table_name = doc.metadata.get("table", "unknown")
                        st.write(f"{i}. table={table_name}")
                        st.code(doc.page_content)

                st.session_state.messages.append({"role": "assistant", "content": answer})

            except Exception as ex:
                st.error(f"Chat error: {ex}")


if __name__ == "__main__":
    main()
