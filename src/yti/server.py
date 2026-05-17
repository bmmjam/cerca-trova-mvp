"""FastAPI HTTP wrapper around the yti package.

Exposes the same operations as the CLI as JSON endpoints, so the Next.js
frontend can call them. The ChunkIndex is built once per request — DB is
small enough that this is fine; if it grows, we can cache by mtime.

Run locally:
    uvicorn yti.server:app --reload --port 8000
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import llm, prompts, search, store

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "chunks.db"

app = FastAPI(title="youtube_intel", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo-grade; tighten for prod
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- helpers ----------------------------------------------------------------

Mode = Literal["bm25", "semantic", "hybrid"]


def _run_search(query: str, k: int, mode: Mode) -> tuple[list[dict], Mode, str | None]:
    """Returns (hits, mode_actually_used, fallback_note)."""
    note: str | None = None
    embed_fn = None
    if mode in ("semantic", "hybrid"):
        embedder = llm.get_embedder()
        if embedder is None:
            note = "no OPENAI_API_KEY — fell back to bm25"
            mode = "bm25"
        else:
            embed_fn = embedder.embed

    with store.connect(DB_PATH) as conn:
        idx = search.ChunkIndex(conn)
    hits = idx.search(query, k=k, mode=mode, embed_fn=embed_fn)
    return hits, mode, note


def _serialize_hit(h: dict) -> dict:
    return {
        "chunk_id": h["chunk_id"],
        "video_id": h["video_id"],
        "title": h.get("title") or "",
        "url": h.get("url") or f"https://www.youtube.com/watch?v={h['video_id']}",
        "ts_start": h["ts_start"],
        "ts_end": h["ts_end"],
        "ts_label": search.fmt_timestamp(h["ts_start"]),
        "deep_link": search.with_timestamp_url(h),
        "text": h["text"],
        "score": h.get("score", 0.0),
        "via": h.get("via", ""),
    }


# --- request/response models ------------------------------------------------


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(8, ge=1, le=50)
    mode: Mode = "hybrid"


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    k: int = Field(8, ge=1, le=50)
    mode: Mode = "hybrid"


class IdeasRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    n: int = Field(5, ge=1, le=15)
    k: int = Field(12, ge=1, le=40)
    mode: Mode = "hybrid"


# --- endpoints --------------------------------------------------------------


@app.get("/api/health")
def health() -> dict:
    prov = llm.get_provider()
    emb = llm.get_embedder()
    return {
        "ok": True,
        "chat_provider": prov.name if prov else None,
        "chat_model": getattr(prov, "chat_model", None),
        "embedder": emb.name if emb else None,
        "embed_model": getattr(emb, "embed_model", None),
    }


@app.get("/api/stats")
def stats() -> dict:
    with store.connect(DB_PATH) as conn:
        s = store.stats(conn)
        s["videos_list"] = [
            {
                "video_id": v["video_id"],
                "title": v["title"],
                "url": v["url"],
                "upload_date": v["upload_date"],
                "duration_s": v["duration_s"],
            }
            for v in store.all_videos(conn)
        ]
    return s


@app.post("/api/search")
def api_search(req: SearchRequest) -> dict:
    hits, used_mode, note = _run_search(req.query, req.k, req.mode)
    return {
        "mode": used_mode,
        "note": note,
        "hits": [_serialize_hit(h) for h in hits],
    }


@app.post("/api/ask")
def api_ask(req: AskRequest) -> dict:
    prov = llm.get_provider()
    if prov is None:
        raise HTTPException(503, "No chat provider configured (set OPENROUTER_API_KEY)")
    hits, used_mode, note = _run_search(req.question, req.k, req.mode)
    if not hits:
        return {"answer": None, "hits": [], "mode": used_mode, "note": note or "0 hits"}
    answer = prov.chat(
        prompts.ASK_SYSTEM,
        prompts.ask_user_prompt(req.question, hits),
        max_tokens=900,
    )
    return {
        "answer": answer,
        "mode": used_mode,
        "note": note,
        "provider": prov.name,
        "model": getattr(prov, "chat_model", None),
        "hits": [_serialize_hit(h) for h in hits],
    }


@app.post("/api/ideas")
def api_ideas(req: IdeasRequest) -> dict:
    prov = llm.get_provider()
    if prov is None:
        raise HTTPException(503, "No chat provider configured (set OPENROUTER_API_KEY)")
    hits, used_mode, note = _run_search(req.topic, req.k, req.mode)
    if not hits:
        return {"ideas": None, "hits": [], "mode": used_mode, "note": note or "0 hits"}
    text = prov.chat(
        prompts.IDEAS_SYSTEM,
        prompts.ideas_user_prompt(req.topic, req.n, hits),
        max_tokens=1500,
    )
    return {
        "ideas": text,
        "mode": used_mode,
        "note": note,
        "provider": prov.name,
        "model": getattr(prov, "chat_model", None),
        "hits": [_serialize_hit(h) for h in hits],
    }


@app.get("/api/gaps")
def api_gaps() -> dict:
    prov = llm.get_provider()
    if prov is None:
        raise HTTPException(503, "No chat provider configured (set OPENROUTER_API_KEY)")
    with store.connect(DB_PATH) as conn:
        videos = store.all_videos(conn)
    if not videos:
        return {"map": None, "note": "no videos ingested"}
    text = prov.chat(
        prompts.GAPS_SYSTEM,
        prompts.gaps_user_prompt(videos),
        max_tokens=1700,
    )
    return {
        "map": text,
        "videos_count": len(videos),
        "provider": prov.name,
        "model": getattr(prov, "chat_model", None),
    }
