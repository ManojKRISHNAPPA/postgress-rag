"""Lesson 1: split narrative fields without mixing unrelated database rows."""

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

import tiktoken
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


@dataclass(frozen=True)
class ChunkSettings:
    # These are token counts, not characters. Budget for the embedding model.
    size: int = 400
    overlap: int = 60
    encoding: str = "cl100k_base"

    def __post_init__(self) -> None:
        if self.size < 32 or not 0 <= self.overlap < self.size:
            raise ValueError("Chunk size must be >= 32 and 0 <= overlap < size.")


def chunk_rows(rows: Iterable[Document], settings: ChunkSettings,
               max_chunks: int = 50_000) -> list[Document]:
    """Keep row metadata on every chunk and assign reproducible content IDs."""
    encoder = tiktoken.get_encoding(settings.encoding)
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=settings.encoding,
        chunk_size=settings.size,
        chunk_overlap=settings.overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[Document] = []
    for row in rows:
        if not row.page_content.strip():
            continue
        for ordinal, chunk in enumerate(splitter.split_documents([row])):
            if len(chunks) >= max_chunks:
                raise ValueError("Chunk budget exceeded; partition the dataset.")
            # Hash the source identity too: identical text in two rows is not
            # the same source. Never use row position as a database identity.
            identity = json.dumps(
                [row.metadata, ordinal, chunk.page_content],
                sort_keys=True, default=str, ensure_ascii=True,
            )
            chunk.metadata.update(
                chunk_id=hashlib.sha256(identity.encode()).hexdigest(),
                chunk_number=ordinal,
                token_count=len(encoder.encode(chunk.page_content)),
            )
            chunks.append(chunk)
    return chunks