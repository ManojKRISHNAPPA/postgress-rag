"""Lesson 4: publish immutable FAISS + JSON generations, never Python pickle."""

import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

import faiss
from filelock import FileLock
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from production.config import Settings


def serialized_documents(documents: list[Document]) -> list[dict]:
    return [{"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in documents]


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


class IndexRepository:
    def __init__(self, settings: Settings, namespace: str, embeddings: Embeddings):
        if len(namespace) != 64 or any(char not in "0123456789abcdef" for char in namespace):
            raise ValueError("Namespace must be a SHA-256 hex digest.")
        self.settings = settings
        self.embeddings = embeddings
        self.root = settings.cache_dir / namespace
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = FileLock(str(self.root / "writer.lock"), timeout=60)

    def refresh(self, documents: list[Document]) -> tuple[FAISS, bool]:
        if not documents or len(documents) > self.settings.max_chunks:
            raise ValueError("Corpus is empty or exceeds the configured chunk budget.")
        payload = serialized_documents(documents)
        signature = digest([self.settings.index_contract(), payload])
        with self.lock:
            pointer = self.root / "current.json"
            if pointer.exists():
                manifest = json.loads(pointer.read_text())
                if manifest.get("signature") == signature:
                    return self._load(manifest), False

            generation = uuid.uuid4().hex
            staging = self.root / f".building-{generation}"
            staging.mkdir(mode=0o700)
            try:
                # Batch embeddings to avoid huge provider requests. OpenAI's
                # client supplies bounded retries/timeouts in the service layer.
                batch_size = self.settings.embedding_batch
                first = documents[:batch_size]
                store = FAISS.from_documents(first, self.embeddings, normalize_L2=True,
                                             ids=[doc.metadata["chunk_id"] for doc in first])
                for offset in range(batch_size, len(documents), batch_size):
                    batch = documents[offset:offset + batch_size]
                    store.add_documents(batch, ids=[doc.metadata["chunk_id"] for doc in batch])
                faiss.write_index(store.index, str(staging / "vectors.faiss"))
                (staging / "documents.json").write_text(json.dumps(payload, ensure_ascii=True))
                manifest = {"generation": generation, "signature": signature,
                            "documents_hash": self._file_hash(staging / "documents.json"),
                            "vectors_hash": self._file_hash(staging / "vectors.faiss")}
                # Atomic directory/pointer renames: readers see old OR new,
                # never half of each. Existing snapshots remain for rollback.
                os.replace(staging, self.root / generation)
                temporary = self.root / f"pointer-{generation}.json"
                temporary.write_text(json.dumps(manifest))
                os.replace(temporary, pointer)
                return store, True
            finally:
                if staging.exists():
                    shutil.rmtree(staging)

    @staticmethod
    def _file_hash(path: Path) -> str:
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()

    def _load(self, manifest: dict) -> FAISS:
        generation = manifest["generation"]
        if len(generation) != 32 or any(char not in "0123456789abcdef" for char in generation):
            raise ValueError("Invalid index generation.")
        directory = self.root / generation
        for name, field in (("documents.json", "documents_hash"), ("vectors.faiss", "vectors_hash")):
            if self._file_hash(directory / name) != manifest[field]:
                raise ValueError("Index integrity check failed; restore a trusted snapshot.")
        documents = [Document(**item) for item in json.loads((directory / "documents.json").read_text())]
        ids = [doc.metadata["chunk_id"] for doc in documents]
        index = faiss.read_index(str(directory / "vectors.faiss"))
        if index.ntotal != len(documents) or len(set(ids)) != len(ids):
            raise ValueError("Index/document mapping is inconsistent.")
        return FAISS(self.embeddings, index, InMemoryDocstore(dict(zip(ids, documents))),
                     dict(enumerate(ids)), normalize_L2=True)