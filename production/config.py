"""Lesson 2: configuration is a data contract, not a collection of UI globals."""

from dataclasses import asdict, dataclass, field
from pathlib import Path

from production.chunking import ChunkSettings


@dataclass(frozen=True)
class TableSpec:
    # Explicit columns prevent passwords, tokens, or other private fields from
    # accidentally leaving PostgreSQL for an embedding provider.
    name: str
    columns: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.name or not self.columns or len(set(self.columns)) != len(self.columns):
            raise ValueError("Each table needs a name and unique allowed columns.")


@dataclass(frozen=True)
class Settings:
    schema: str
    tables: tuple[TableSpec, ...]
    chunks: ChunkSettings = field(default_factory=ChunkSettings)
    cache_dir: Path = Path(".cache/production")
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"
    max_rows_per_table: int = 10_000
    max_total_rows: int = 50_000
    max_row_characters: int = 100_000
    max_chunks: int = 50_000
    embedding_batch: int = 128
    retrieval_k: int = 6
    candidate_k: int = 24
    context_tokens: int = 4_000
    statement_timeout_ms: int = 10_000
    sql_limit: int = 200
    multi_query: bool = False

    def __post_init__(self) -> None:
        if not self.schema or not self.tables:
            raise ValueError("Configure a schema and at least one allowed table.")
        if len({table.name for table in self.tables}) != len(self.tables):
            raise ValueError("Table names must be unique.")
        values = (self.max_rows_per_table, self.max_total_rows, self.max_row_characters,
              self.max_chunks, self.embedding_batch,
                  self.retrieval_k, self.candidate_k, self.context_tokens,
                  self.statement_timeout_ms, self.sql_limit)
        if any(value <= 0 for value in values) or self.candidate_k < self.retrieval_k:
            raise ValueError("Budgets must be positive; candidate_k must be >= retrieval_k.")

    def index_contract(self) -> dict:
        # Retrieval/model settings do not change vectors; chunking and allowed
        # columns do. Version this when serialization or ingestion changes.
        return {"version": 1, "schema": self.schema,
                "tables": [asdict(table) for table in self.tables],
                "chunks": asdict(self.chunks), "embedding_model": self.embedding_model,
                "max_rows_per_table": self.max_rows_per_table,
                "max_total_rows": self.max_total_rows,
                "max_row_characters": self.max_row_characters}