"""Lesson 6: combine semantic similarity with exact-word evidence."""

import re

import tiktoken
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from production.config import Settings


def terms(value: str) -> list[str]:
    return re.findall(r"\w+", value.lower())


def rank_fusion(rankings: list[list[Document]], count: int) -> list[Document]:
    # Reciprocal rank fusion does not compare incompatible BM25 and FAISS
    # scores. A result appearing near the top of both lists gets promoted.
    scores: dict[str, float] = {}
    documents: dict[str, Document] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for position, document in enumerate(ranking, start=1):
            identity = document.metadata["chunk_id"]
            if identity in seen:
                continue
            seen.add(identity)
            documents[identity] = document
            scores[identity] = scores.get(identity, 0.0) + 1.0 / (60 + position)
    return [documents[identity] for identity in
            sorted(scores, key=lambda identity: (-scores[identity], identity))[:count]]


class HybridRetriever:
    def __init__(self, store, documents: list[Document], settings: Settings):
        self.store = store
        self.documents = documents
        self.settings = settings
        self.lexical = BM25Okapi([terms(doc.page_content) or ["empty"] for doc in documents])

    def retrieve(self, queries: list[str]) -> list[Document]:
        rankings: list[list[Document]] = []
        for query in queries[:3]:
            # MMR balances relevance against redundant overlapping chunks.
            rankings.append(self.store.max_marginal_relevance_search(
                query, k=self.settings.retrieval_k, fetch_k=self.settings.candidate_k,
                lambda_mult=0.65,
            ))
            scores = self.lexical.get_scores(terms(query))
            positions = sorted(range(len(scores)), key=lambda index: -scores[index])
            rankings.append([self.documents[index] for index in positions
                             if scores[index] > 0][:self.settings.candidate_k])
        return rank_fusion(rankings, self.settings.retrieval_k)

    def context(self, documents: list[Document]) -> tuple[str, list[dict]]:
        encoder = tiktoken.get_encoding(self.settings.chunks.encoding)
        blocks: list[str] = []
        sources: list[dict] = []
        remaining = self.settings.context_tokens
        for document in documents:
            label = f"S{len(sources) + 1}"
            block = f"[{label}]\n{document.page_content}"
            token_count = len(encoder.encode(block + "\n\n"))
            if token_count > remaining:
                continue
            remaining -= token_count
            blocks.append(block)
            sources.append({"citation": label, **document.metadata,
                            "excerpt": document.page_content})
        return "\n\n".join(blocks), sources