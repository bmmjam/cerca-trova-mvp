"""SQLite storage for video metadata + chunked transcripts."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
  video_id     TEXT PRIMARY KEY,
  title        TEXT,
  url          TEXT,
  uploader     TEXT,
  upload_date  TEXT,
  duration_s   INTEGER,
  description  TEXT,
  ingested_at  TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  video_id   TEXT NOT NULL,
  ts_start   REAL NOT NULL,
  ts_end     REAL NOT NULL,
  text       TEXT NOT NULL,
  embedding  BLOB,
  FOREIGN KEY(video_id) REFERENCES videos(video_id)
);

CREATE INDEX IF NOT EXISTS idx_chunks_video ON chunks(video_id);
"""


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_video(conn: sqlite3.Connection, video: dict) -> None:
    conn.execute(
        """
        INSERT INTO videos (video_id, title, url, uploader, upload_date,
                            duration_s, description, ingested_at)
        VALUES (:video_id, :title, :url, :uploader, :upload_date,
                :duration_s, :description, :ingested_at)
        ON CONFLICT(video_id) DO UPDATE SET
            title=excluded.title,
            url=excluded.url,
            uploader=excluded.uploader,
            upload_date=excluded.upload_date,
            duration_s=excluded.duration_s,
            description=excluded.description,
            ingested_at=excluded.ingested_at
        """,
        {**video, "ingested_at": datetime.now(timezone.utc).isoformat()},
    )


def replace_chunks(conn: sqlite3.Connection, video_id: str, chunks: Iterable[dict]) -> int:
    conn.execute("DELETE FROM chunks WHERE video_id = ?", (video_id,))
    count = 0
    for ch in chunks:
        conn.execute(
            """
            INSERT INTO chunks (video_id, ts_start, ts_end, text)
            VALUES (:video_id, :ts_start, :ts_end, :text)
            """,
            {"video_id": video_id, **ch},
        )
        count += 1
    return count


def all_chunks(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.chunk_id, c.video_id, c.ts_start, c.ts_end, c.text, c.embedding,
               v.title, v.url
        FROM chunks c
        JOIN videos v ON v.video_id = c.video_id
        ORDER BY c.chunk_id
        """
    ).fetchall()
    return [dict(r) for r in rows]


def all_videos(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM videos ORDER BY upload_date DESC").fetchall()
    return [dict(r) for r in rows]


def set_embedding(conn: sqlite3.Connection, chunk_id: int, vec: np.ndarray) -> None:
    blob = vec.astype(np.float32).tobytes()
    conn.execute("UPDATE chunks SET embedding = ? WHERE chunk_id = ?", (blob, chunk_id))


def decode_embedding(blob: bytes | None) -> np.ndarray | None:
    if blob is None:
        return None
    return np.frombuffer(blob, dtype=np.float32)


def chunks_without_embeddings(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT chunk_id, text FROM chunks WHERE embedding IS NULL"
    ).fetchall()
    return [dict(r) for r in rows]


def stats(conn: sqlite3.Connection) -> dict:
    n_videos = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    n_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    n_emb = conn.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NOT NULL").fetchone()[0]
    return {"videos": n_videos, "chunks": n_chunks, "chunks_with_embeddings": n_emb}
