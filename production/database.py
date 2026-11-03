"""Lesson 3: acquire deterministic, explicitly approved rows in one snapshot."""

import hashlib
import json
from contextlib import contextmanager
from typing import Iterator

from langchain_core.documents import Document
from sqlalchemy import MetaData, Table, create_engine, select, text
from sqlalchemy.engine import Connection, Engine, URL

from production.config import Settings


def make_engine(host: str, port: int, database: str, user: str, password: str,
                sslmode: str = "verify-full", sslrootcert: str = "") -> Engine:
    # URL.create encodes BOTH username and password correctly. Do not print it.
    query = {"sslmode": sslmode}
    if sslrootcert:
        query["sslrootcert"] = sslrootcert
    url = URL.create("postgresql+psycopg2", username=user, password=password,
                     host=host, port=port, database=database, query=query)
    return create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2,
                         connect_args={"connect_timeout": 10})


@contextmanager
def read_transaction(engine: Engine, timeout_ms: int) -> Iterator[Connection]:
    if engine.dialect.name != "postgresql":
        raise ValueError("This pipeline requires PostgreSQL.")
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            # Read-only transactions are defense in depth, NOT a substitute
            # for a dedicated role with column-level SELECT privileges.
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SELECT set_config('statement_timeout', :value, true)"),
                         {"value": str(timeout_ms)})
            yield conn


def load_rows(engine: Engine, settings: Settings) -> list[Document]:
    documents: list[Document] = []
    with read_transaction(engine, settings.statement_timeout_ms) as conn:
        for spec in settings.tables:
            table = Table(spec.name, MetaData(), schema=settings.schema, autoload_with=conn)
            missing = set(spec.columns) - set(table.columns.keys())
            primary_key = list(table.primary_key.columns)
            if missing or not primary_key:
                raise ValueError(f"{spec.name}: unknown columns or missing primary key.")
            if not {column.name for column in primary_key}.issubset(spec.columns):
                raise ValueError(f"{spec.name}: include primary-key columns in the allowlist.")
            statement = select(*(table.c[name] for name in spec.columns)).order_by(*primary_key)
            result = conn.execution_options(stream_results=True).execute(
                statement.limit(settings.max_rows_per_table + 1)
            )
            for ordinal, row in enumerate(result.mappings()):
                # Refuse incomplete corpora rather than silently answering from
                # a random sample. Larger datasets need a partitioned/CDC job.
                if ordinal >= settings.max_rows_per_table:
                    raise ValueError(f"{spec.name}: row budget exceeded; partition the dataset.")
                key = json.dumps([row[column.name] for column in primary_key], default=str)
                source_id = f"{settings.schema}.{spec.name}:{key}"
                content = "\n".join(f"{name}: {row[name]}" for name in spec.columns)
                if len(content) > settings.max_row_characters or len(documents) >= settings.max_total_rows:
                    raise ValueError("Total row or per-row text budget exceeded.")
                documents.append(Document(page_content=content, metadata={
                    "source_id": source_id, "schema": settings.schema, "table": spec.name,
                    "row_key": key,
                }))
    return documents


def dataset_namespace(engine: Engine, settings: Settings) -> str:
    # No credentials on disk. Include role and database endpoint to isolate
    # datasets; separate cache roots are still required for separate tenants.
    url = engine.url
    identity = [url.host, url.port, url.database, url.username, settings.index_contract()]
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()