from types import SimpleNamespace

from langchain_core.documents import Document

from rag_core import (
    answer_question_hybrid,
    answer_with_rag,
    build_db_uri,
    ensure_limit,
    extract_sql,
    format_sql_results,
    is_safe_read_only_sql,
    needs_sql_query,
    split_documents_recursive,
)
import rag_core


# Test doubles for deterministic unit tests.
class FakeLLM:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def invoke(self, _prompt):
        return SimpleNamespace(content=self.response_text)


class SequencedLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def invoke(self, _prompt):
        if self.responses:
            return SimpleNamespace(content=self.responses.pop(0))
        return SimpleNamespace(content="")


class FakeVectorStore:
    def __init__(self, scored_docs):
        self.scored_docs = scored_docs

    def similarity_search_with_relevance_scores(self, _question, k=20):
        return self.scored_docs[:k]


# ---------------------------------------------------------------------------
# Core utility tests: URI building and recursive chunk splitting
# ---------------------------------------------------------------------------
def test_build_db_uri_encodes_password():
    uri = build_db_uri("localhost", "5432", "sales", "user", "a+b c")
    assert uri == "postgresql+psycopg2://user:a%2Bb+c@localhost:5432/sales"


def test_split_documents_recursive_generates_more_chunks_for_long_input():
    long_text = "customer details " * 400
    docs = [Document(page_content=long_text, metadata={"table": "customers"})]

    chunks = split_documents_recursive(docs, chunk_size=120, chunk_overlap=20)

    assert len(chunks) > 1
    assert all(c.metadata.get("table") == "customers" for c in chunks)


# ---------------------------------------------------------------------------
# Routing tests: decide whether a query should go to SQL or semantic RAG
# ---------------------------------------------------------------------------
def test_needs_sql_query_detects_analytic_request():
    assert needs_sql_query("List top 50 customers by total revenue") is True
    assert needs_sql_query("Explain customer churn reasons") is False


def test_needs_sql_query_allows_semantic_question():
    assert needs_sql_query("What does onboarding process mean in this business?") is False


# ---------------------------------------------------------------------------
# SQL sanitization tests: extraction, safety checks, and limit enforcement
# ---------------------------------------------------------------------------
def test_extract_sql_from_fenced_block():
    raw = """Here is query:\n```sql\nSELECT id FROM customers LIMIT 5;\n```"""
    assert extract_sql(raw) == "SELECT id FROM customers LIMIT 5;"


def test_is_safe_read_only_sql_accepts_select_and_cte():
    assert is_safe_read_only_sql("SELECT * FROM customers LIMIT 10") is True
    assert is_safe_read_only_sql("WITH x AS (SELECT 1) SELECT * FROM x") is True


def test_is_safe_read_only_sql_blocks_mutations_and_multi_statement():
    assert is_safe_read_only_sql("DELETE FROM customers") is False
    assert is_safe_read_only_sql("SELECT * FROM customers; DROP TABLE customers;") is False


def test_ensure_limit_adds_default_when_missing():
    sql = "SELECT id, name FROM customers ORDER BY id"
    assert ensure_limit(sql, default_limit=200, max_limit=1000).endswith("LIMIT 200")


def test_ensure_limit_caps_large_limit():
    sql = "SELECT id FROM customers LIMIT 100000"
    assert ensure_limit(sql, default_limit=200, max_limit=1000) == "SELECT id FROM customers LIMIT 1000"


# ---------------------------------------------------------------------------
# SQL output formatting tests
# ---------------------------------------------------------------------------
def test_format_sql_results_returns_markdown_like_table():
    text = format_sql_results(["id", "name"], [(1, "Alice"), (2, "Bob")], truncated=False)
    assert "id | name" in text
    assert "1 | Alice" in text


# ---------------------------------------------------------------------------
# RAG behavior tests: strict unknown fallback and answer generation path
# ---------------------------------------------------------------------------
def test_answer_with_rag_returns_unknown_when_no_relevant_docs():
    docs = [
        (Document(page_content="not relevant", metadata={"table": "x"}), 0.05),
        (Document(page_content="also not relevant", metadata={"table": "x"}), 0.1),
    ]
    vectorstore = FakeVectorStore(docs)
    llm = FakeLLM("should not be used")

    result = answer_with_rag("Who are my customers?", vectorstore, llm, similarity_threshold=0.2)

    assert result["mode"] == "rag"
    assert result["answer"] == "I don't know based on the indexed data."


def test_answer_with_rag_uses_llm_when_relevant_docs_exist():
    docs = [
        (Document(page_content="customer_name: Alice", metadata={"table": "customers"}), 0.85),
    ]
    vectorstore = FakeVectorStore(docs)
    llm = FakeLLM("Alice is a customer in the indexed records.")

    result = answer_with_rag("Who is Alice?", vectorstore, llm, similarity_threshold=0.2)

    assert result["mode"] == "rag"
    assert "Alice" in result["answer"]


# ---------------------------------------------------------------------------
# Hybrid orchestration tests: RAG fallback, SQL success, SQL safety fallback
# ---------------------------------------------------------------------------
def test_answer_question_hybrid_falls_back_to_rag_for_semantic_question():
    docs = [
        (Document(page_content="policy: onboarding includes KYC", metadata={"table": "policies"}), 0.91),
    ]
    vectorstore = FakeVectorStore(docs)
    llm = FakeLLM("Onboarding includes KYC verification.")

    result = answer_question_hybrid(
        question="What is onboarding policy?",
        db_uri="postgresql+psycopg2://user:pass@localhost:5432/db",
        schema="public",
        vectorstore=vectorstore,
        llm=llm,
    )

    assert result["mode"] == "rag"
    assert "KYC" in result["answer"]


def test_answer_question_hybrid_uses_sql_mode_when_safe(monkeypatch):
    vectorstore = FakeVectorStore([])
    llm = FakeLLM("SELECT id, name FROM customers ORDER BY id LIMIT 500")

    monkeypatch.setattr(rag_core, "build_schema_description", lambda *_: "public.customers(id int, name text)")
    monkeypatch.setattr(rag_core, "execute_sql_query", lambda *_: (["id", "name"], [(1, "Alice"), (2, "Bob")], False))

    result = answer_question_hybrid(
        question="List customers",
        db_uri="postgresql+psycopg2://user:pass@localhost:5432/db",
        schema="public",
        vectorstore=vectorstore,
        llm=llm,
    )

    assert result["mode"] == "sql"
    assert "id | name" in result["answer"]
    assert "LIMIT 500" in result["sql"]


def test_answer_question_hybrid_falls_back_when_generated_sql_is_unsafe(monkeypatch):
    docs = [
        (Document(page_content="customer_name: Alice", metadata={"table": "customers"}), 0.85),
    ]
    vectorstore = FakeVectorStore(docs)
    llm = SequencedLLM(["DELETE FROM customers", "Alice is in customers table."])

    monkeypatch.setattr(rag_core, "build_schema_description", lambda *_: "public.customers(id int, name text)")

    result = answer_question_hybrid(
        question="List customers",
        db_uri="postgresql+psycopg2://user:pass@localhost:5432/db",
        schema="public",
        vectorstore=vectorstore,
        llm=llm,
    )

    assert result["mode"] == "rag"
    assert "Alice" in result["answer"]
    assert "indexed excerpts" in result["warning"]


def test_semantic_customer_question_does_not_generate_sql(monkeypatch):
    def unexpected_sql(*_):
        raise AssertionError("Semantic explanation should not request SQL schema")
    monkeypatch.setattr(rag_core, "build_schema_description", unexpected_sql)
    llm = FakeLLM("Delayed support contributes to churn [S1].")
    vectorstore = FakeVectorStore([
        (Document(page_content="churn_reason: delayed support", metadata={"table": "customers"}), 0.9)
    ])
    result = answer_question_hybrid("Explain customer churn reasons", "unused", "public", vectorstore, llm)
    assert result["mode"] == "rag"
    assert result["sources"][0]["page_content"] == "churn_reason: delayed support"


def test_explicit_sql_failure_never_calls_rag(monkeypatch):
    monkeypatch.setattr(rag_core, "build_schema_description", lambda *_: "customers(id int)")
    llm = SequencedLLM(["DELETE FROM customers", "This must not be generated"])
    result = answer_question_hybrid("List customers", "unused", "public", FakeVectorStore([]), llm, mode="sql")
    assert result["mode"] == "sql"
    assert "could not be safely completed" in result["answer"]
    assert len(llm.responses) == 1


def test_explicit_rag_overrides_analytic_keywords():
    result = answer_question_hybrid("Explain total revenue terminology", "unused", "public",
                                    FakeVectorStore([]), FakeLLM("unused"), mode="rag")
    assert result["mode"] == "rag"
    assert result["sources"] == []


def test_invalid_question_mode_and_chunk_overlap():
    import pytest
    with pytest.raises(ValueError, match="question"):
        answer_question_hybrid(" ", "unused", "public", None, None)
    with pytest.raises(ValueError, match="mode"):
        answer_question_hybrid("Hello", "unused", "public", None, None, mode="invalid")
    with pytest.raises(ValueError, match="chunk_overlap"):
        split_documents_recursive([], chunk_size=100, chunk_overlap=100)


def test_ui_renders_exact_prompt_sources(monkeypatch):
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    import langchain_openai

    document = Document(page_content="policy: proof of purchase required", metadata={"table": "policies"})
    vectorstore = FakeVectorStore([(document, 0.9)])
    # FakeVectorStore deliberately has no similarity_search method: the UI
    # must not retrieve a second, potentially different set of source passages.
    monkeypatch.setattr(rag_core, "refresh_vectorstore_if_needed", lambda **_: (vectorstore, False))
    monkeypatch.setattr(langchain_openai, "OpenAIEmbeddings", lambda **_: object())
    monkeypatch.setattr(langchain_openai, "ChatOpenAI", lambda **_: FakeLLM("Proof of purchase is required [S1]."))
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py")
    app.session_state["rag"] = {
        "db_uri": "unused", "schema": "public", "row_limit": 100,
        "chunk_size": 700, "chunk_overlap": 120, "embedding_model": "fake",
        "api_key": "not-a-real-key", "model_name": "fake", "vectorstore": vectorstore,
    }
    app.run(timeout=15)
    app.selectbox[0].select("rag")
    app.chat_input[0].set_value("Explain refund policy").run(timeout=15)
    assert not app.exception
    assert app.code[0].value == document.page_content
    assert "[S1]" in app.session_state["messages"][-1]["content"]
