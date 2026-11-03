# Classroom reference: rag_core.py owns database ingestion, chunking, FAISS
# persistence, SQL routing, and answer generation. This file owns the UI.
#
# Follow the application in this order:
# main -> render_connection_sidebar -> connect_to_database -> render_chat
#      -> answer_user_question -> answer_question_hybrid (in rag_core.py).
#
# Streamlit reruns this script when a widget changes. Local variables are
# recreated; st.session_state keeps connection settings and displayed messages
# across reruns within the current browser session.
import os

import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
# Reuse the core functions instead of duplicating retrieval logic in the UI.
from rag_core import (
    answer_question_hybrid,
    build_db_uri,
    refresh_vectorstore_if_needed,
)


# Load .env values as optional defaults for DB fields.
# OpenAI key is intentionally entered in the UI, not loaded from .env.
load_dotenv()


def render_connection_sidebar() -> tuple[dict, bool]:
    # Collect settings only. Editing a field must not immediately trigger an
    # expensive database scan or embedding request; the button starts that work.
    with st.sidebar:
        st.header("Connection")

        # Environment values are optional defaults, not a successful connection.
        # A password widget masks its display; it does not encrypt session memory.
        db_host = st.text_input("DB Host", value=os.getenv("DB_HOST", ""))
        db_port = st.text_input("DB Port", value=os.getenv("DB_PORT", "5432"))
        db_name = st.text_input("DB Name", value=os.getenv("DB_NAME", ""))
        db_user = st.text_input("DB User", value=os.getenv("DB_USER", ""))
        db_password = st.text_input("DB Password", type="password", value=os.getenv("DB_PASSWORD", ""))
        db_schema = st.text_input("Schema", value=os.getenv("DB_SCHEMA", "public"))
        # row_limit bounds ingestion per table, NOT the number of SQL results.
        # rag_core.table_to_documents reads that sample before splitting rows.
        row_limit = st.number_input("Rows per table to ingest", min_value=100, max_value=100000, value=5000, step=100)
        # rag_core.split_documents_recursive uses character counts, not tokens.
        # Overlap repeats boundary text so a sentence is less likely to lose
        # context. It must be smaller than chunk_size; the splitter validates it.
        chunk_size = st.number_input("Chunk size", min_value=200, max_value=4000, value=700, step=50)
        chunk_overlap = st.number_input("Chunk overlap", min_value=0, max_value=1000, value=120, step=20)

        st.header("OpenAI")
        # As requested, OpenAI key is entered directly in UI.
        openai_api_key = st.text_input("OpenAI API Key", type="password")
        # The chat model generates text/SQL. The embedding model converts text
        # into vectors for similarity search. These are separate responsibilities.
        model_name = st.text_input("Model", value="gpt-4o-mini")
        embedding_model = st.text_input("Embedding Model", value="text-embedding-3-small")

        # Auto uses the core heuristic. RAG and SQL override it for ambiguous
        # questions; this choice can change without rebuilding the vector index.
        st.selectbox("Answer mode", options=["auto", "rag", "sql"], key="answer_mode")
        connect_clicked = st.button("Connect / Refresh Index", type="primary")

    # Return one configuration dictionary and a one-rerun button flag. Explicit
    # integer conversion keeps widget values suitable for the core function APIs.
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
    # Fail before constructing clients if required input is missing. This checks
    # presence only; database access and provider validity are checked by use.
    required = [
        settings["db_host"], settings["db_port"], settings["db_name"],
        settings["db_user"], settings["db_password"], settings["openai_api_key"],
    ]
    if not all(required):
        st.error("Please provide all DB fields and OpenAI API key.")
        return

    # Reference: rag_core.build_db_uri percent-encodes the database password.
    # The resulting URI contains credentials: do not print it or commit it.
    db_uri = build_db_uri(
        settings["db_host"], settings["db_port"], settings["db_name"],
        settings["db_user"], settings["db_password"],
    )
    # Creating the embedding client does not itself embed the database. The core
    # refresh function uses it when building vectors or searching a loaded index.
    embeddings = OpenAIEmbeddings(
        model=settings["embedding_model"], api_key=settings["openai_api_key"]
    )
    # Reference: rag_core.refresh_vectorstore_if_needed either loads saved FAISS
    # vectors or runs rows -> Documents -> recursive chunks -> embeddings -> FAISS.
    # rebuilt tells the UI which path ran; it is not a database connection flag.
    # Demo limitation: the core checks table columns/counts, not changed row values.
    # Its shared disk cache also does not isolate databases or embedding settings.
    # Use only trusted local index files: the core permits pickle deserialization.
    vectorstore, rebuilt = refresh_vectorstore_if_needed(
        db_uri=db_uri, schema=settings["db_schema"], row_limit=settings["row_limit"],
        embeddings=embeddings, chunk_size=settings["chunk_size"],
        chunk_overlap=settings["chunk_overlap"],
    )

    # Persist only after indexing succeeds. Later reruns/questions reuse these
    # captured settings, even if sidebar fields have been edited meanwhile.
    # Session state is browser-session-local; the core's disk cache is still shared.
    # API keys stay in memory here. Never put this dictionary in logs or a global
    # st.cache_resource cache that could share credentials across user sessions.
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


def render_retrieved_sources(sources: list[dict]) -> None:
    # Display exactly the excerpts supplied to the answer prompt, not a separate
    # similarity search. Their labels match the [S1], [S2] labels shown to the LLM.
    # Citation labels show provenance; they do not guarantee factual correctness.
    if not sources:
        return
    with st.expander("Retrieved sources"):
        for source in sources:
            table_name = source["metadata"].get("table", "unknown")
            st.write(f"[{source['citation']}] table={table_name}")
            st.code(source["page_content"])


def answer_user_question(question: str) -> None:
    # Read the successfully connected configuration, not uncommitted sidebar edits.
    rag = st.session_state.rag
    # Match the embedding model used during connection. Existing vectors must
    # share the query vector's model/dimensions for meaningful similarity search.
    embeddings = OpenAIEmbeddings(model=rag["embedding_model"], api_key=rag["api_key"])
    # This demo refreshes before EVERY answer. Unchanged fingerprints skip costly
    # re-embedding, but fingerprint checks still query the DB. Same-count UPDATEs
    # are not detected; a separate production ingest job needs stronger tracking.
    vectorstore, rebuilt = refresh_vectorstore_if_needed(
        db_uri=rag["db_uri"], schema=rag["schema"], row_limit=rag["row_limit"],
        embeddings=embeddings, chunk_size=rag["chunk_size"],
        chunk_overlap=rag["chunk_overlap"],
    )
    # Low temperature reduces variability; it does not guarantee factual answers
    # or safe SQL. The core supplies prompts, routing, retrieval, and SQL checks.
    llm = ChatOpenAI(model=rag["model_name"], temperature=0.0, api_key=rag["api_key"])
    # Reference: rag_core.answer_question_hybrid routes keyword-based analytics
    # to generated SQL, and semantic questions to retrieved-context generation.
    # Auto-mode SQL rejection/errors fall back to RAG with a warning. Explicit
    # SQL mode reports failure instead of presenting a sampled semantic answer.
    # The core's regex SQL guard is not a security boundary: use a least-privilege
    # read-only DB role and stronger execution controls before real deployment.
    result = answer_question_hybrid(
        question=question, db_uri=rag["db_uri"], schema=rag["schema"],
        vectorstore=vectorstore, llm=llm,
        mode=st.session_state.get("answer_mode", "auto"),
    )
    if result.get("warning"):
        st.warning(result["warning"])
    st.markdown(result["answer"])

    # The core returns mode, answer, optional SQL, and the actual RAG sources.
    # Show generated SQL for inspection without exposing connection credentials.
    if rebuilt:
        st.caption("Detected schema/data change. Refreshed embeddings automatically.")
    if result["mode"] == "sql" and result["sql"]:
        st.caption("Answer mode: SQL")
        with st.expander("Generated SQL"):
            st.code(result["sql"], language="sql")
    if result["mode"] == "rag":
        st.caption("Answer mode: RAG")
    render_retrieved_sources(result.get("sources", []))
    # Save the answer so the next rerun can redraw the conversation. This list
    # is display history only: it is not sent to the model as conversational memory.
    st.session_state.messages.append({"role": "assistant", "content": result["answer"]})


def render_chat() -> None:
    # Redraw earlier messages first. Each st.chat_message container styles one
    # message according to its role; it does not call the language model.
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_question = st.chat_input("Ask a question about your PostgreSQL data...")
    # On ordinary reruns there is no newly submitted question: stop here to avoid
    # generating duplicate answers or making unnecessary paid provider requests.
    if not user_question:
        return

    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user"):
        st.markdown(user_question)
    with st.chat_message("assistant"):
        try:
            answer_user_question(user_question)
        except Exception as ex:
            # Teaching demo feedback only. Production should show a generic
            # error/reference ID; raw DB/provider exceptions can expose details.
            st.error(f"Chat error: {ex}")


def main() -> None:
    # Configure the page before rendering UI elements, then collect sidebar state.
    st.set_page_config(page_title="PostgreSQL RAG Chat", layout="wide")
    st.title("PostgreSQL RAG Chatbot (LangChain + OpenAI)")
    settings, connect_clicked = render_connection_sidebar()
    # Initialize once per session, not once per script rerun; otherwise every
    # widget interaction would erase the displayed conversation.
    if "messages" not in st.session_state:
        st.session_state.messages = []

    if connect_clicked:
        # Connection/indexing errors are caught separately from per-question errors.
        try:
            connect_to_database(settings)

        except Exception as ex:
            st.error(f"Connection/indexing error: {ex}")

    # Presence of rag means a connection/index setup previously succeeded. It
    # does not prove the database is still reachable or credentials still valid.
    if "rag" not in st.session_state:
        st.info("Fill sidebar fields and click 'Connect / Refresh Index' to start chatting.")
        return
    render_chat()


# Standard script entry point. Run with: streamlit run app.py
# Importing this module from tests does not automatically start the application.
if __name__ == "__main__":
    main()
