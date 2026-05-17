"""FastAPI HTTP wrapper around the yti package.

Exposes the same operations as the CLI as JSON endpoints, so the Next.js
frontend can call them. The ChunkIndex is built once per request — DB is
small enough that this is fine; if it grows, we can cache by mtime.

Run locally:
    uvicorn yti.server:app --reload --port 8000
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import ingest as ingest_mod
from . import llm, prompts, search, store

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "chunks.db"
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# In-process status of the latest admin-triggered ingest job.
# Replaces a real queue; fine for one-shot demo seeding.
_INGEST_STATE: dict = {"running": False, "started_at": None, "log": []}
_INGEST_LOCK = threading.Lock()

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


# --- admin (one-shot ingest over HTTP) -------------------------------------
#
# Lets you seed/refresh the DB on a hosted backend (Railway/Render/Fly)
# without needing an interactive shell. Protected by YTI_ADMIN_TOKEN env var.

class IngestRequest(BaseModel):
    url: str = Field(..., min_length=1, description="Video / channel / playlist URL")
    limit: int = Field(50, ge=1, le=500)
    embed: bool = Field(True, description="Run yti embed after ingest")


def _require_admin(token: str | None) -> None:
    expected = os.getenv("YTI_ADMIN_TOKEN")
    if not expected:
        raise HTTPException(503, "Admin disabled: YTI_ADMIN_TOKEN not set on the server")
    if not token or token != expected:
        raise HTTPException(401, "Bad or missing X-Admin-Token")


def _do_ingest(url: str, limit: int, with_embed: bool) -> None:
    """Runs in a background thread. Pushes line-by-line progress into _INGEST_STATE['log']."""
    def log(msg: str) -> None:
        with _INGEST_LOCK:
            _INGEST_STATE["log"].append(f"{time.strftime('%H:%M:%S')} · {msg}")
            if len(_INGEST_STATE["log"]) > 200:
                _INGEST_STATE["log"] = _INGEST_STATE["log"][-200:]

    try:
        log(f"resolving URLs from {url} (limit={limit})")
        urls = ingest_mod.expand_url(url, limit=limit)
        if not urls:
            log("no videos resolved — aborting")
            return
        log(f"will ingest {len(urls)} videos")
        with store.connect(DB_PATH) as conn:
            for i, u in enumerate(urls, start=1):
                try:
                    r = ingest_mod.ingest_url(u, conn, RAW_DIR)
                    if r["status"] == "ok":
                        log(f"  [{i}/{len(urls)}] ok · {r['title'][:60]!r} · chunks={r['chunks']}")
                    else:
                        log(f"  [{i}/{len(urls)}] {r['status']} · {r.get('reason','')}")
                except Exception as e:
                    log(f"  [{i}/{len(urls)}] error · {e}")
        log("ingest done")

        if with_embed:
            embedder = llm.get_embedder()
            if embedder is None:
                log("skip embed — OPENAI_API_KEY not set")
            else:
                with store.connect(DB_PATH) as conn:
                    pending = store.chunks_without_embeddings(conn)
                log(f"embedding {len(pending)} new chunks")
                BATCH = 96
                for i in range(0, len(pending), BATCH):
                    batch = pending[i : i + BATCH]
                    vecs = embedder.embed([b["text"] for b in batch])
                    with store.connect(DB_PATH) as conn:
                        for b, v in zip(batch, vecs):
                            store.set_embedding(conn, b["chunk_id"], v)
                    log(f"  embedded {min(i+BATCH, len(pending))}/{len(pending)}")
                log("embeddings done")
    except Exception as e:
        log(f"FATAL · {e}")
    finally:
        with _INGEST_LOCK:
            _INGEST_STATE["running"] = False


@app.post("/api/admin/ingest")
def admin_ingest(
    req: IngestRequest,
    x_admin_token: str | None = Header(default=None),
) -> dict:
    _require_admin(x_admin_token)
    with _INGEST_LOCK:
        if _INGEST_STATE["running"]:
            raise HTTPException(409, "Another ingest is already running — wait for it to finish")
        _INGEST_STATE["running"] = True
        _INGEST_STATE["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _INGEST_STATE["log"] = []

    thread = threading.Thread(
        target=_do_ingest,
        args=(req.url, req.limit, req.embed),
        daemon=True,
    )
    thread.start()
    return {
        "status": "started",
        "url": req.url,
        "limit": req.limit,
        "embed": req.embed,
        "poll": "/api/admin/ingest/status",
    }


@app.get("/api/admin/ingest/status")
def admin_ingest_status(x_admin_token: str | None = Header(default=None)) -> dict:
    _require_admin(x_admin_token)
    with _INGEST_LOCK:
        snapshot = {
            "running": _INGEST_STATE["running"],
            "started_at": _INGEST_STATE["started_at"],
            "log_tail": list(_INGEST_STATE["log"][-30:]),
        }
    with store.connect(DB_PATH) as conn:
        snapshot["stats"] = store.stats(conn)
    return snapshot


@app.post("/api/admin/upload-db")
async def admin_upload_db(
    file: UploadFile = File(...),
    x_admin_token: str | None = Header(default=None),
) -> dict:
    """Accept a SQLite DB upload from an operator's local machine.

    Workaround for the YouTube-blocks-datacenter-IPs problem: ingest runs fine
    on a residential connection; you ship the resulting `data/chunks.db` to
    the hosted backend with one curl --form upload.
    """
    _require_admin(x_admin_token)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DB_PATH.with_suffix(".tmp.upload")
    total = 0
    with open(tmp, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            total += len(chunk)
            f.write(chunk)
    # Basic sanity: SQLite files start with "SQLite format 3\0".
    with open(tmp, "rb") as f:
        magic = f.read(16)
    if magic != b"SQLite format 3\x00":
        tmp.unlink(missing_ok=True)
        raise HTTPException(400, "uploaded file is not a SQLite database")
    tmp.replace(DB_PATH)
    with store.connect(DB_PATH) as conn:
        stats = store.stats(conn)
    return {"status": "uploaded", "bytes": total, "stats": stats}
