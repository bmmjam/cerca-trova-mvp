"""Fetch YouTube metadata + auto-subs via yt-dlp, parse VTT, chunk by time/length."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable

import yt_dlp

from . import store


# --- VTT parsing -------------------------------------------------------------

TS_RE = re.compile(r"(\d+):(\d{2}):(\d{2})[.,](\d{3})")
CUE_HEADER_RE = re.compile(
    r"^(\d+:\d{2}:\d{2}[.,]\d{3})\s+-->\s+(\d+:\d{2}:\d{2}[.,]\d{3})"
)
TAG_RE = re.compile(r"<[^>]+>")


def _ts_to_seconds(ts: str) -> float:
    m = TS_RE.match(ts)
    if not m:
        return 0.0
    h, mm, ss, ms = m.groups()
    return int(h) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000.0


def parse_vtt(text: str) -> list[dict]:
    """Return cues: [{ts_start, ts_end, text}, ...] with HTML/karaoke tags stripped."""
    cues: list[dict] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = CUE_HEADER_RE.match(line)
        if not m:
            i += 1
            continue
        start = _ts_to_seconds(m.group(1))
        end = _ts_to_seconds(m.group(2))
        i += 1
        buf: list[str] = []
        while i < len(lines) and lines[i].strip():
            buf.append(TAG_RE.sub("", lines[i]).strip())
            i += 1
        cue_text = " ".join(s for s in buf if s).strip()
        if cue_text:
            cues.append({"ts_start": start, "ts_end": end, "text": cue_text})
        i += 1
    return _dedupe_cues(cues)


def _trim_rolling_overlap(prev: str, cur: str) -> str:
    """Find longest suffix of `prev` that's also a prefix of `cur`, drop it from `cur`.

    Auto-generated YouTube subtitles roll line-by-line: each new cue repeats the
    tail of the previous one. Removing that overlap collapses ~2× duplication.
    """
    max_k = min(len(prev), len(cur))
    for k in range(max_k, 4, -1):  # require at least 5-char overlap to count
        if prev.endswith(cur[:k]):
            return cur[k:].lstrip(" ,.;:!? ")
    return cur


def _dedupe_cues(cues: list[dict]) -> list[dict]:
    """Collapse rolling-caption duplication into a clean linear transcript."""
    out: list[dict] = []
    prev_text = ""
    for c in cues:
        t = c["text"]
        if t == prev_text:
            continue
        trimmed = _trim_rolling_overlap(prev_text, t) if prev_text else t
        trimmed = trimmed.strip()
        if not trimmed:
            prev_text = t
            continue
        out.append({"ts_start": c["ts_start"], "ts_end": c["ts_end"], "text": trimmed})
        prev_text = t
    return out


# --- Chunking ----------------------------------------------------------------

def chunk_cues(
    cues: list[dict],
    target_chars: int = 700,
    max_chars: int = 1100,
    max_duration_s: float = 75.0,
) -> list[dict]:
    """Merge consecutive cues into chunks aiming at target_chars / max_duration_s."""
    chunks: list[dict] = []
    if not cues:
        return chunks
    cur_text: list[str] = []
    cur_start = cues[0]["ts_start"]
    cur_end = cues[0]["ts_end"]

    def flush() -> None:
        text = " ".join(cur_text).strip()
        if text:
            chunks.append({"ts_start": cur_start, "ts_end": cur_end, "text": text})

    for c in cues:
        candidate = (" ".join(cur_text) + " " + c["text"]).strip()
        too_long = len(candidate) > max_chars
        too_far = (c["ts_end"] - cur_start) > max_duration_s
        if cur_text and (too_long or too_far):
            flush()
            cur_text = [c["text"]]
            cur_start = c["ts_start"]
            cur_end = c["ts_end"]
            continue
        cur_text.append(c["text"])
        cur_end = c["ts_end"]
        if len(" ".join(cur_text)) >= target_chars:
            flush()
            cur_text = []
            if cues.index(c) + 1 < len(cues):
                cur_start = cues[cues.index(c) + 1]["ts_start"]
                cur_end = cues[cues.index(c) + 1]["ts_end"]
    if cur_text:
        flush()
    return chunks


# --- yt-dlp wrapper ----------------------------------------------------------

def fetch_video(url: str, raw_dir: Path, langs: list[str]) -> dict | None:
    """Download metadata + subtitles for a single video URL. Returns info dict or None."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": langs,
        "subtitlesformat": "vtt",
        "outtmpl": {"default": str(raw_dir / "%(id)s.%(ext)s")},
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return info


def expand_url(url: str, limit: int | None = None) -> list[str]:
    """Resolve channel/playlist URL into a flat list of video URLs."""
    opts = {
        "extract_flat": True,
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
        "playlistend": limit,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        return []
    if "entries" not in info:
        return [url]
    urls: list[str] = []
    for e in info["entries"]:
        if not e:
            continue
        # nested (channel of playlists)
        if "entries" in e:
            for e2 in e["entries"] or []:
                if e2 and e2.get("url"):
                    urls.append(_normalize_video_url(e2["url"]))
        elif e.get("url"):
            urls.append(_normalize_video_url(e["url"]))
        elif e.get("id"):
            urls.append(f"https://www.youtube.com/watch?v={e['id']}")
    return urls[:limit] if limit else urls


def _normalize_video_url(url_or_id: str) -> str:
    if url_or_id.startswith("http"):
        return url_or_id
    return f"https://www.youtube.com/watch?v={url_or_id}"


def _find_subtitle_file(info: dict, raw_dir: Path) -> Path | None:
    """Pick the best available VTT file for this video — prefer manual ru, then auto ru, then en."""
    vid = info.get("id")
    if not vid:
        return None
    preferred_langs = ["ru", "ru-orig", "ru-RU", "en", "en-US", "en-orig"]
    # yt-dlp writes files as {id}.{lang}.vtt
    candidates: list[Path] = []
    for p in raw_dir.glob(f"{vid}.*.vtt"):
        candidates.append(p)
    if not candidates:
        return None
    for lang in preferred_langs:
        for p in candidates:
            if f".{lang}." in p.name:
                return p
    return candidates[0]


def ingest_url(
    url: str,
    conn: sqlite3.Connection,
    raw_dir: Path,
    langs: list[str] | None = None,
) -> dict:
    """Ingest one video URL into the DB. Returns a small report dict."""
    langs = langs or ["ru", "ru-orig", "en"]
    info = fetch_video(url, raw_dir, langs)
    if not info or info.get("_type") == "playlist":
        return {"url": url, "status": "skipped", "reason": "no info / playlist"}

    vid = info["id"]
    sub_path = _find_subtitle_file(info, raw_dir)
    if not sub_path or not sub_path.exists():
        return {"url": url, "status": "skipped", "reason": "no subtitles available"}

    cues = parse_vtt(sub_path.read_text(encoding="utf-8", errors="ignore"))
    chunks = chunk_cues(cues)

    store.upsert_video(
        conn,
        {
            "video_id": vid,
            "title": info.get("title") or "",
            "url": info.get("webpage_url") or url,
            "uploader": info.get("uploader") or "",
            "upload_date": info.get("upload_date") or "",
            "duration_s": int(info.get("duration") or 0),
            "description": (info.get("description") or "")[:4000],
        },
    )
    n = store.replace_chunks(conn, vid, chunks)
    return {
        "url": url,
        "video_id": vid,
        "title": info.get("title"),
        "chunks": n,
        "subtitle_lang": sub_path.name.split(".")[-2],
        "status": "ok",
    }


def ingest_many(
    urls: Iterable[str],
    conn: sqlite3.Connection,
    raw_dir: Path,
    langs: list[str] | None = None,
) -> list[dict]:
    reports: list[dict] = []
    for u in urls:
        try:
            reports.append(ingest_url(u, conn, raw_dir, langs))
        except Exception as e:  # noqa: BLE001
            reports.append({"url": u, "status": "error", "reason": str(e)})
    return reports
