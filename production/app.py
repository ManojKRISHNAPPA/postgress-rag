"""Lesson 8: a thin classroom UI; business behavior lives in RagService."""

import json
import logging
import uuid
from pathlib import Path

import streamlit as st

from production.chunking import ChunkSettings
from production.config import Settings, TableSpec
from production.database import make_engine
from production.service import RagService

logger = logging.getLogger(__name__)


def main() -> None:
    st.set_page_config(page_title="PostgreSQL RAG", layout="wide")
    st.title("PostgreSQL RAG")
    if "production_messages" not in st.session_state:
        st.session_state.production_messages = []

    with st.sidebar:
        st.header("PostgreSQL")
        host = st.text_input("Host", value="localhost")
        port = st.number_input("Port", min_value=1, max_value=65535, value=5432)
        database = st.text_input("Database", value="rag_demo")
        username = st.text_input("Read-only user", value="rag_reader")
        password = st.text_input("Database password", type="password")
        schema = st.text_input("Schema", value="rag_demo")
        sslmode = st.selectbox("TLS mode", ["verify-full", "require", "disable"])
        certificate = st.text_input("CA certificate path")
        allowed = st.text_area("Allowed tables and columns (JSON)", value=json.dumps(
            {"notes": ["id", "subject", "body"]}, indent=2))
        st.header("Models")
        # Keys come only from password inputs, never environment defaults.
        api_key = st.text_input("OpenAI API key", type="password")
        chat_model = st.text_input("Chat model", value="gpt-4o-mini")
        embedding_model = st.text_input("Embedding model", value="text-embedding-3-small")
        with st.expander("Index settings"):
            size = st.number_input("Chunk tokens", min_value=32, max_value=2000, value=400)
            overlap = st.number_input("Overlap tokens", min_value=0, max_value=500, value=60)
            max_rows = st.number_input("Maximum rows per table", min_value=1, max_value=100000,
                                       value=10000)
            multi_query = st.checkbox("Multi-query retrieval", value=False)
        connect = st.button("Connect and Refresh", icon=":material/sync:", type="primary")
        disconnect = st.button("Disconnect", icon=":material/link_off:")

    if disconnect:
        previous = st.session_state.pop("production_service", None)
        if previous:
            previous.engine.dispose()
        st.session_state.production_messages = []

    if connect:
        engine = None
        try:
            if not all((host, database, username, password, api_key)):
                raise ValueError("Database fields and API key are required.")
            mapping = json.loads(allowed)
            if not isinstance(mapping, dict) or any(
                not isinstance(name, str) or not isinstance(columns, list) or
                any(not isinstance(column, str) for column in columns)
                for name, columns in mapping.items()
            ):
                raise ValueError("Allowlist must map table names to lists of column names.")
            settings = Settings(
                schema=schema, tables=tuple(TableSpec(name, tuple(columns))
                                           for name, columns in mapping.items()),
                chunks=ChunkSettings(size=int(size), overlap=int(overlap)),
                # Never use st.cache_resource for a credential-bearing service:
                # its global cache could share one user's engine with another.
                cache_dir=Path(".cache/production"), chat_model=chat_model,
                embedding_model=embedding_model, max_rows_per_table=int(max_rows),
                multi_query=multi_query,
            )
            engine = make_engine(host, int(port), database, username, password, sslmode, certificate)
            service = RagService(engine, settings, api_key)
            with st.spinner("Refreshing index..."):
                stats = service.refresh()
            previous = st.session_state.get("production_service")
            if previous:
                previous.engine.dispose()
            st.session_state.production_service = service
            st.session_state.production_messages = []
            st.session_state.production_stats = stats
        except (ValueError, json.JSONDecodeError):
            if engine:
                engine.dispose()
            st.error("Invalid configuration, unavailable columns, or dataset budget exceeded.")
        except Exception:
            if engine:
                engine.dispose()
            # Raw database/provider exceptions may contain credentials or data.
            request_id = uuid.uuid4().hex[:12]
            logger.error("connection_failed request_id=%s", request_id)
            st.error(f"Connection or indexing failed. Reference: {request_id}")

    service = st.session_state.get("production_service")
    if service is None:
        return
    stats = st.session_state.production_stats
    columns = st.columns(3)
    columns[0].metric("Rows", stats["rows"])
    columns[1].metric("Chunks", stats["chunks"])
    columns[2].metric("Index", "Rebuilt" if stats["rebuilt"] else "Unchanged")
    mode = st.segmented_control("Query mode", ["auto", "rag", "sql"], default="auto")
    if st.button("Clear Conversation", icon=":material/delete:"):
        st.session_state.production_messages = []

    for message in st.session_state.production_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input("Ask about your PostgreSQL data")
    if not question:
        return
    history = st.session_state.production_messages[-4:]
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Querying..."):
                result = service.answer(question, mode=mode or "auto", history=history)
            if result["mode"] == "sql":
                st.dataframe(result["rows"], column_config={
                    position: name for position, name in enumerate(result["columns"])
                }, hide_index=True)
                with st.expander("SQL"):
                    st.code(result["sql"], language="sql")
                if result["capped"]:
                    st.warning("Result reached the row cap; additional rows may exist.")
                content = f"SQL returned {len(result['rows'])} rows."
            else:
                content = result["answer"]
                st.markdown(content)
                with st.expander("Sources"):
                    for source in result["sources"]:
                        st.caption(f"[{source['citation']}] {source['source_id']}")
                        st.text(source["excerpt"])
            st.session_state.production_messages.extend([
                {"role": "user", "content": question},
                {"role": "assistant", "content": content},
            ])
            st.session_state.production_messages = st.session_state.production_messages[-20:]
        except ValueError:
            st.error("Query rejected by validation or SQL policy. Try a narrower question or select RAG mode.")
        except Exception:
            request_id = uuid.uuid4().hex[:12]
            logger.error("query_failed request_id=%s", request_id)
            st.error(f"Query failed. Reference: {request_id}")


if __name__ == "__main__":
    main()