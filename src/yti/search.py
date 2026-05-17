"""Search over stored chunks.

Two modes:
  - bm25  : pure keyword, no API key required (default).
  - semantic: cosine over OpenAI embeddings stored as BLOBs in the DB.
  - hybrid : reciprocal-rank-fusion of bm25 + semantic.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Literal

import numpy as np
from rank_bm25 import BM25Okapi

from . import store

Mode = Literal["bm25", "semantic", "hybrid"]


_TOKEN_RE = re.compile(r"[\w\-]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class ChunkIndex:
    """Builds an in-memory search index over all chunks in the DB."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.chunks: list[dict] = store.all_chunks(conn)
        self._bm25: BM25Okapi | None = None
        self._emb_matrix: np.ndarray | None = None
        self._emb_dim: int | None = None
        if self.chunks:
            corpus = [tokenize(c["text"]) for c in self.chunks]
            self._bm25 = BM25Okapi(corpus)
            self._build_embedding_matrix()

    def _build_embedding_matrix(self) -> None:
        with_emb = [store.decode_embedding(c["embedding"]) for c in self.chunks]
        if all(v is None for v in with_emb):
            return
        dim = next((v.shape[0] for v in with_emb if v is not None), 0)
        if not dim:
            return
        mat = np.zeros((len(self.chunks), dim), dtype=np.float32)
        mask = np.zeros(len(self.chunks), dtype=bool)
        for i, v in enumerate(with_emb):
            if v is not None and v.shape[0] == dim:
                mat[i] = v
                mask[i] = True
        # L2-normalize rows that have an embedding
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        mat = mat / norms
        self._emb_matrix = mat
        self._emb_mask = mask
        self._emb_dim = dim

    # --- search ----------------------------------------------------------

    def search(
        self,
        query: str,
        k: int = 8,
        mode: Mode = "bm25",
        embed_fn=None,
    ) -> list[dict]:
        if not self.chunks:
            return []
        if mode == "bm25":
            return self._bm25_top(query, k)
        if mode == "semantic":
            return self._semantic_top(query, k, embed_fn)
        if mode == "hybrid":
            return self._hybrid_top(query, k, embed_fn)
        raise ValueError(f"unknown mode: {mode}")

    def _bm25_top(self, query: str, k: int) -> list[dict]:
        assert self._bm25 is not None
        scores = self._bm25.get_scores(tokenize(query))
        idx = np.argsort(scores)[::-1][:k]
        out = []
        for i in idx:
            if scores[i] <= 0:
                continue
            out.append({**self.chunks[i], "score": float(scores[i]), "via": "bm25"})
        return out

    def _semantic_top(self, query: str, k: int, embed_fn) -> list[dict]:
        if self._emb_matrix is None or embed_fn is None:
            return []
        q = embed_fn([query])[0].astype(np.float32)
        n = np.linalg.norm(q)
        if n == 0:
            return []
        q = q / n
        sims = self._emb_matrix @ q
        # zero out rows without embeddings
        sims = np.where(self._emb_mask, sims, -1.0)
        idx = np.argsort(sims)[::-1][:k]
        out = []
        for i in idx:
            if sims[i] <= 0:
                continue
            out.append({**self.chunks[i], "score": float(sims[i]), "via": "semantic"})
        return out

    def _hybrid_top(self, query: str, k: int, embed_fn) -> list[dict]:
        # Reciprocal Rank Fusion over the two ranked lists
        bm = self._bm25_top(query, k * 3)
        sem = self._semantic_top(query, k * 3, embed_fn)
        scores: dict[int, float] = {}
        kept: dict[int, dict] = {}
        K_RRF = 60
        for rank, hit in enumerate(bm):
            scores[hit["chunk_id"]] = scores.get(hit["chunk_id"], 0.0) + 1.0 / (K_RRF + rank)
            kept[hit["chunk_id"]] = hit
        for rank, hit in enumerate(sem):
            scores[hit["chunk_id"]] = scores.get(hit["chunk_id"], 0.0) + 1.0 / (K_RRF + rank)
            kept.setdefault(hit["chunk_id"], hit)
        ranked = sorted(kept.values(), key=lambda h: -scores[h["chunk_id"]])
        for h in ranked:
            h["score"] = scores[h["chunk_id"]]
            h["via"] = "hybrid"
        return ranked[:k]


def fmt_timestamp(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, ss = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{ss:02d}"
    return f"{m}:{ss:02d}"


def with_timestamp_url(hit: dict) -> str:
    base = hit["url"] or f"https://www.youtube.com/watch?v={hit['video_id']}"
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}t={int(hit['ts_start'])}s"
