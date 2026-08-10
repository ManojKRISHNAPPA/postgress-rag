import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple
from urllib.parse import quote_plus

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text

APP_DIR = Path(__file__).parent
CACHE_DIR = APP_DIR / ".cache"
INDEX_DIR = CACHE_DIR / "faiss_index"
FINGERPRINT_FILE = CACHE_DIR / "table_fingerprints.json"


def build_db_uri(host: str, port: str, database: str, user: str, password: str) -> str:
    """Build a SQLAlchemy-compatible PostgreSQL URI."""
    safe_password = quote_plus(password)
    return f"postgresql+psycopg2://{user}:{safe_password}@{host}:{port}/{database}"


def load_saved_fingerprint() -> Dict[str, Dict[str, object]]:
    if not FINGERPRINT_FILE.exists():
        return {}
    return json.loads(FINGERPRINT_FILE.read_text())


def save_fingerprint(fingerprint: Dict[str, Dict[str, object]]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    FINGERPRINT_FILE.write_text(json.dumps(fingerprint, indent=2))


def get_table_fingerprint(db_uri: str, schema: str) -> Dict[str, Dict[str, object]]:
    """Return a lightweight table signature to detect changed data/index drift."""
    engine = create_engine(db_uri)
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names(schema=schema))

    result: Dict[str, Dict[str, object]] = {}
    with engine.connect() as conn:
        for table_name in tables:
            columns = inspector.get_columns(table_name, schema=schema)
            column_names = [col["name"] for col in columns]
            qualified = f'"{schema}"."{table_name}"'
            row_count = conn.execute(text(f"SELECT COUNT(*) FROM {qualified}")).scalar_one()

            result[table_name] = {
                "columns": column_names,
                "row_count": int(row_count),
            }

    return result


def split_documents_recursive(
    docs: Sequence[Document],
    chunk_size: int = 700,
    chunk_overlap: int = 120,
) -> List[Document]:
    """Split long rows/records into retrieval-friendly chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ", ", " ", ""],
    )
    return splitter.split_documents(list(docs))


def table_to_documents(
    db_uri: str,
    schema: str,
    row_limit: int,
    chunk_size: int = 700,
    chunk_overlap: int = 120,
) -> List[Document]:
    """Read all tables and convert rows into chunked searchable documents."""
    engine = create_engine(db_uri)
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names(schema=schema))

    row_docs: List[Document] = []
    metadata = MetaData(schema=schema)

    with engine.connect() as conn:
        for table_name in tables:
            table = Table(table_name, metadata, autoload_with=engine)
            rows = conn.execute(select(table).limit(row_limit)).mappings().all()

            for idx, row in enumerate(rows):
                text_lines = [f"Table: {table_name}"]
                for col_name, value in row.items():
                    text_lines.append(f"{col_name}: {value}")

                row_docs.append(
                    Document(
                        page_content="\n".join(text_lines),
                        metadata={
                            "table": table_name,
                            "schema": schema,
                            "row_number": idx,
                        },
                    )
                )

    return split_documents_recursive(
        row_docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def refresh_vectorstore_if_needed(
    db_uri: str,
    schema: str,
    row_limit: int,
    embeddings: Any,
    chunk_size: int = 700,
    chunk_overlap: int = 120,
) -> Tuple[FAISS, bool]:
    """Ensure vector index is available and synced with table fingerprints."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    latest_fingerprint = get_table_fingerprint(db_uri, schema)
    saved_fingerprint = load_saved_fingerprint()

    index_exists = INDEX_DIR.exists() and any(INDEX_DIR.iterdir())
    requires_rebuild = (not index_exists) or (latest_fingerprint != saved_fingerprint)

    if requires_rebuild:
        docs = table_to_documents(
            db_uri=db_uri,
            schema=schema,
            row_limit=row_limit,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
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


def format_docs(docs: Iterable[Document]) -> str:
    formatted = []
    for d in docs:
        table_name = d.metadata.get("table", "unknown")
        formatted.append(f"[source_table={table_name}]\n{d.page_content}")
    return "\n\n".join(formatted)


def build_rag_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_template(
        """
You are a PostgreSQL RAG assistant.
Use only the context below when answering.
If the answer is not in context, say exactly: I don't know based on the indexed data.

Context:
{context}

Question:
{question}

Answer in concise business language.
""".strip()
    )


def needs_sql_query(question: str) -> bool:
    """Heuristic router: list/count/filter/report style questions should use SQL."""
    q = question.lower()
    patterns = [
        r"\blist\b",
        r"\bshow\b",
        r"\bcount\b",
        r"\btop\b",
        r"\bhighest\b",
        r"\blowest\b",
        r"\bgroup by\b",
        r"\border by\b",
        r"\btotal\b",
        r"\baverage\b",
        r"\bsum\b",
        r"\bhow many\b",
        r"\brevenue\b",
        r"\bcustomer(s)?\b",
    ]
    return any(re.search(p, q) for p in patterns)


def build_schema_description(db_uri: str, schema: str) -> str:
    """Build compact table/column summary used for SQL generation prompts."""
    engine = create_engine(db_uri)
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names(schema=schema))

    lines = []
    for table in tables:
        cols = inspector.get_columns(table, schema=schema)
        col_desc = ", ".join(f"{c['name']} ({str(c['type'])})" for c in cols)
        lines.append(f"- {schema}.{table}: {col_desc}")

    return "\n".join(lines)


def extract_sql(text_response: str) -> str:
    sql_block = re.search(r"```sql\s*(.*?)\s*```", text_response, flags=re.IGNORECASE | re.DOTALL)
    if sql_block:
        return sql_block.group(1).strip()
    return text_response.strip()


def is_safe_read_only_sql(sql: str) -> bool:
    """Allow a single read-only SELECT/CTE statement only."""
    normalized = re.sub(r"\s+", " ", sql.strip().lower())

    if ";" in normalized[:-1]:
        return False

    if not (normalized.startswith("select ") or normalized.startswith("with ")):
        return False

    blocked = [
        " insert ",
        " update ",
        " delete ",
        " drop ",
        " alter ",
        " create ",
        " truncate ",
        " grant ",
        " revoke ",
        " execute ",
    ]
    return not any(token in f" {normalized} " for token in blocked)


def ensure_limit(sql: str, default_limit: int = 200, max_limit: int = 1000) -> str:
    """Cap result sizes to avoid returning massive payloads in chat."""
    m = re.search(r"\blimit\s+(\d+)\b", sql, flags=re.IGNORECASE)
    if not m:
        return f"{sql.rstrip(';')} LIMIT {default_limit}"

    current = int(m.group(1))
    if current <= max_limit:
        return sql.rstrip(";")

    return re.sub(
        r"\blimit\s+\d+\b",
        f"LIMIT {max_limit}",
        sql,
        flags=re.IGNORECASE,
    ).rstrip(";")


def generate_sql_for_question(question: str, schema_description: str, llm: Any) -> str:
    prompt = ChatPromptTemplate.from_template(
        """
You generate PostgreSQL SQL only.
Return SQL only (no explanation) for the user's question.
Use schema below and produce a read-only query.
Prefer explicit column names and deterministic ordering.

Schema:
{schema}

Question:
{question}
""".strip()
    )

    response = llm.invoke(prompt.format(schema=schema_description, question=question))
    raw = response.content if hasattr(response, "content") else str(response)
    return extract_sql(raw)


def execute_sql_query(db_uri: str, sql: str, fetch_limit: int = 1000) -> Tuple[List[str], List[Tuple[Any, ...]], bool]:
    """Execute read-only SQL and return rows with truncation metadata."""
    engine = create_engine(db_uri)
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = result.fetchall()

    truncated = len(rows) > fetch_limit
    if truncated:
        rows = rows[:fetch_limit]

    return columns, rows, truncated


def format_sql_results(columns: Sequence[str], rows: Sequence[Sequence[Any]], truncated: bool) -> str:
    if not rows:
        return "No rows matched this query."

    header = " | ".join(columns)
    sep = " | ".join(["---"] * len(columns))
    body = [" | ".join(str(v) for v in row) for row in rows]

    result = "\n".join([header, sep, *body])
    if truncated:
        result += "\n\nResult was truncated for safety. Refine filters to narrow results."
    return result


def answer_with_rag(question: str, vectorstore: Any, llm: Any, similarity_threshold: float = 0.2) -> Dict[str, str]:
    scored = vectorstore.similarity_search_with_relevance_scores(question, k=20)
    if not scored:
        return {
            "mode": "rag",
            "answer": "I don't know based on the indexed data.",
            "sql": "",
        }

    selected_docs = [doc for doc, score in scored if score >= similarity_threshold][:8]
    if not selected_docs:
        return {
            "mode": "rag",
            "answer": "I don't know based on the indexed data.",
            "sql": "",
        }

    prompt = build_rag_prompt()
    response = llm.invoke(
        prompt.format(context=format_docs(selected_docs), question=question)
    )
    content = response.content if hasattr(response, "content") else str(response)

    return {
        "mode": "rag",
        "answer": content,
        "sql": "",
    }


def answer_question_hybrid(
    question: str,
    db_uri: str,
    schema: str,
    vectorstore: Any,
    llm: Any,
) -> Dict[str, str]:
    """Route structured analytics/listing to SQL, fallback to RAG for semantics."""
    if needs_sql_query(question):
        try:
            schema_desc = build_schema_description(db_uri, schema)
            sql = generate_sql_for_question(question, schema_desc, llm)
            if is_safe_read_only_sql(sql):
                safe_sql = ensure_limit(sql)
                columns, rows, truncated = execute_sql_query(db_uri, safe_sql)
                return {
                    "mode": "sql",
                    "answer": format_sql_results(columns, rows, truncated),
                    "sql": safe_sql,
                }
        except Exception:
            # SQL generation/execution is best effort; if it fails we fallback to RAG.
            pass

    return answer_with_rag(question=question, vectorstore=vectorstore, llm=llm)
