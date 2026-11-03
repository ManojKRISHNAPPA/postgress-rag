"""Offline production checks: no PostgreSQL server or OpenAI credentials needed."""

import pytest
from langchain_core.documents import Document

from production.chunking import ChunkSettings, chunk_rows


def test_token_chunks_preserve_sources_and_have_stable_ids():
    row = Document(
        page_content="Customer support resolved a billing issue. " * 150,
        metadata={"source_id": "public.notes:42", "table": "notes"},
    )
    settings = ChunkSettings(size=64, overlap=12)
    chunks = chunk_rows([row], settings)
    assert len(chunks) > 1
    assert all(chunk.metadata["token_count"] <= 64 for chunk in chunks)
    assert all(chunk.metadata["source_id"] == "public.notes:42" for chunk in chunks)
    assert len({chunk.metadata["chunk_id"] for chunk in chunks}) == len(chunks)
    assert [chunk.metadata for chunk in chunks] == [
        chunk.metadata for chunk in chunk_rows([row], settings)
    ]


def test_chunk_settings_reject_invalid_overlap():
    with pytest.raises(ValueError):
        ChunkSettings(size=64, overlap=64)


def test_chunks_never_merge_rows():
    rows = [Document(page_content="Same text", metadata={"source_id": source})
            for source in ("row:1", "row:2")]
    chunks = chunk_rows(rows, ChunkSettings())
    assert len(chunks) == 2
    assert chunks[0].metadata["chunk_id"] != chunks[1].metadata["chunk_id"]


def test_index_round_trip_and_content_update(tmp_path):
    from langchain_core.embeddings import DeterministicFakeEmbedding
    from production.config import Settings, TableSpec
    from production.index import IndexRepository

    settings = Settings(schema="public", tables=(TableSpec("notes", ("id", "body")),),
                        cache_dir=tmp_path, embedding_batch=1)
    repository = IndexRepository(settings, "a" * 64, DeterministicFakeEmbedding(size=16))
    rows = [Document(page_content="Refund policy", metadata={"source_id": "notes:1"})]
    chunks = chunk_rows(rows, settings.chunks)
    first, rebuilt = repository.refresh(chunks)
    assert rebuilt and first.index.ntotal == 1
    loaded, rebuilt = repository.refresh(chunks)
    assert not rebuilt
    assert loaded.similarity_search("Refund policy", k=1)[0].page_content == "Refund policy"
    rows[0].page_content = "Refunds within thirty days"
    updated, rebuilt = repository.refresh(chunk_rows(rows, settings.chunks))
    assert rebuilt and updated.index.ntotal == 1
    assert not list(tmp_path.rglob("*.pkl"))


def test_index_detects_corruption(tmp_path):
    from langchain_core.embeddings import DeterministicFakeEmbedding
    from production.config import Settings, TableSpec
    from production.index import IndexRepository

    settings = Settings(schema="public", tables=(TableSpec("notes", ("id", "body")),),
                        cache_dir=tmp_path)
    repository = IndexRepository(settings, "b" * 64, DeterministicFakeEmbedding(size=8))
    chunks = chunk_rows([Document(page_content="Policy", metadata={"source_id": "1"})], settings.chunks)
    repository.refresh(chunks)
    next(tmp_path.rglob("documents.json")).write_text("[]")
    with pytest.raises(ValueError, match="integrity"):
        repository.refresh(chunks)


CATALOG = {"public": {"notes": {"id": "INT", "body": "TEXT"}}}


@pytest.mark.parametrize("query", [
    "DELETE FROM public.notes",
    "SELECT id FROM public.notes; DROP TABLE public.notes",
    "SELECT body INTO stolen FROM public.notes",
    "WITH x AS (DELETE FROM public.notes RETURNING id) SELECT * FROM x",
    "SELECT pg_sleep(10)",
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT public.count(id) FROM public.notes",
    "SELECT CAST(body AS public.custom_type) FROM public.notes",
    "SELECT * FROM private.notes",
    "SELECT password FROM public.notes",
    "SELECT * FROM notes",
    "SELECT * FROM public.notes FOR UPDATE",
    "SELECT * FROM public.notes LIMIT ALL",
])
def test_sql_guard_rejects_unsafe_or_unapproved_queries(query):
    from production.sql import guard_sql
    with pytest.raises(ValueError):
        guard_sql(query, CATALOG, 200)


def test_sql_outer_limit_and_cte_are_structural():
    import sqlglot
    from production.sql import guard_sql

    query = "WITH x AS (SELECT id FROM public.notes LIMIT 5) SELECT * FROM x LIMIT 9999"
    tree = sqlglot.parse_one(guard_sql(query, CATALOG, 200), read="postgres")
    assert tree.args["limit"].expression.this == "200"
    assert "LIMIT 5" in tree.sql()
    assert "COUNT(*)" in guard_sql("SELECT COUNT(*) FROM public.notes", CATALOG, 200)
    assert "body" in guard_sql("SELECT * FROM public.notes LIMIT 2", CATALOG, 200)


def test_rank_fusion_deduplicates():
    from production.retrieval import rank_fusion
    first = Document(page_content="First", metadata={"chunk_id": "1"})
    second = Document(page_content="Second", metadata={"chunk_id": "2"})
    assert rank_fusion([[first, first, second], [second]], 2) == [second, first]


def test_context_budget_and_citations():
    from production.config import Settings, TableSpec
    from production.retrieval import HybridRetriever
    settings = Settings(schema="public", tables=(TableSpec("notes", ("id", "body")),),
                        context_tokens=30)
    documents = chunk_rows([Document(page_content="Policy refund within 30 days",
                                     metadata={"source_id": "1"})], settings.chunks)
    retriever = HybridRetriever(None, documents, settings)
    context, sources = retriever.context(documents)
    assert "[S1]" in context
    assert sources[0]["citation"] == "S1"


def test_classroom_ui_loads_without_credentials():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "production/app.py").run(timeout=15)
    assert not app.exception
    assert app.title[0].value == "PostgreSQL RAG"
    assert not app.session_state.production_messages


def test_service_abstains_without_sources():
    from types import SimpleNamespace
    from production.service import RagService, UNKNOWN
    service = object.__new__(RagService)
    service.retriever = SimpleNamespace(retrieve=lambda _: [], context=lambda _: ("", []))
    service.settings = SimpleNamespace(multi_query=False)
    result = service.answer("Explain refund policy", mode="rag")
    assert result["answer"] == UNKNOWN


def test_sql_failure_does_not_fall_back_to_rag(monkeypatch):
    from types import SimpleNamespace
    from langchain_core.runnables import RunnableLambda
    import production.service as module
    service = object.__new__(module.RagService)
    service.engine = object()
    service.settings = SimpleNamespace()
    service.llm = RunnableLambda(lambda _: "DELETE FROM public.notes")
    monkeypatch.setattr(module, "schema_catalog", lambda *_: CATALOG)
    def deny(*_):
        raise ValueError("Denied")
    monkeypatch.setattr(module, "execute_guarded", deny)
    with pytest.raises(ValueError, match="Denied"):
        service.answer("Count notes", mode="sql")


def test_chunk_budget_is_enforced():
    row = Document(page_content="long narrative " * 500, metadata={"source_id": "1"})
    with pytest.raises(ValueError, match="Chunk budget"):
        chunk_rows([row], ChunkSettings(size=32, overlap=4), max_chunks=1)


def test_index_contract_separates_settings():
    from dataclasses import replace
    from sqlalchemy import create_engine
    from production.config import Settings, TableSpec
    from production.database import dataset_namespace
    settings = Settings(schema="public", tables=(TableSpec("notes", ("id", "body")),))
    engine = create_engine("postgresql+psycopg2://reader:secret@localhost/database")
    try:
        original = dataset_namespace(engine, settings)
        assert original != dataset_namespace(engine, replace(settings, embedding_model="other"))
        assert original != dataset_namespace(engine, replace(settings, chunks=ChunkSettings(size=256)))
        assert original != dataset_namespace(engine, replace(settings, schema="private"))
    finally:
        engine.dispose()