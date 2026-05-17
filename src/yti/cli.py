"""CLI for youtube_intel.

Commands:
  yti ingest <url-or-channel-url> [--limit N]   ingest videos
  yti embed                                       compute embeddings for all chunks
  yti search "query" [--k 8] [--mode bm25|semantic|hybrid]
  yti ask    "question" [--k 8] [--mode ...]
  yti ideas  "topic" [--n 5] [--k 12]
  yti gaps
  yti stats
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from . import ingest as ingest_mod
from . import llm, prompts, search, store

load_dotenv()

app = typer.Typer(help="YouTube content intelligence for a brand's archive.", no_args_is_help=True)
console = Console()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = PROJECT_ROOT / "data" / "chunks.db"
DEFAULT_RAW = PROJECT_ROOT / "data" / "raw"


def _resolve_paths(db: Optional[Path]) -> tuple[Path, Path]:
    db_path = db or DEFAULT_DB
    return db_path, DEFAULT_RAW


# ----------------------- ingest --------------------------------------------------


@app.command("ingest")
def cmd_ingest(
    urls: list[str] = typer.Argument(..., help="Video, channel, or playlist URLs"),
    limit: int = typer.Option(20, "--limit", help="Max videos when URL is a channel/playlist"),
    db: Optional[Path] = typer.Option(None, "--db", help="SQLite DB path"),
):
    db_path, raw_dir = _resolve_paths(db)
    expanded: list[str] = []
    with console.status("[cyan]Resolving URLs…[/cyan]"):
        for u in urls:
            expanded.extend(ingest_mod.expand_url(u, limit=limit))
    if not expanded:
        console.print("[red]No videos resolved from input URLs.[/red]")
        raise typer.Exit(1)

    console.print(f"Будет обработано видео: [bold]{len(expanded)}[/bold]")
    with store.connect(db_path) as conn:
        for i, u in enumerate(expanded, start=1):
            console.print(f"[dim]{i}/{len(expanded)}[/dim] {u}")
            r = ingest_mod.ingest_url(u, conn, raw_dir)
            if r["status"] == "ok":
                console.print(
                    f"  → [green]ok[/green] {r['title']!r} · "
                    f"chunks={r['chunks']} · lang={r['subtitle_lang']}"
                )
            else:
                console.print(f"  → [yellow]{r['status']}[/yellow] {r.get('reason','')}")

    _print_stats(db_path)


# ----------------------- embed ---------------------------------------------------


@app.command("embed")
def cmd_embed(
    db: Optional[Path] = typer.Option(None, "--db"),
    limit: int = typer.Option(0, "--limit", help="Embed at most N chunks (0 = all)"),
):
    db_path, _ = _resolve_paths(db)
    embedder = llm.get_embedder()
    if embedder is None:
        console.print("[red]OPENAI_API_KEY is not set — cannot compute embeddings.[/red]")
        raise typer.Exit(1)
    with store.connect(db_path) as conn:
        pending = store.chunks_without_embeddings(conn)
        if limit:
            pending = pending[:limit]
        if not pending:
            console.print("Все чанки уже эмбеддированы.")
            return
        console.print(f"Embedding chunks: [bold]{len(pending)}[/bold]")
        BATCH = 96
        for i in range(0, len(pending), BATCH):
            batch = pending[i : i + BATCH]
            vecs = embedder.embed([b["text"] for b in batch])
            for b, v in zip(batch, vecs):
                store.set_embedding(conn, b["chunk_id"], v)
            console.print(f"  done {min(i+BATCH, len(pending))}/{len(pending)}")
    console.print("[green]Embeddings updated.[/green]")


# ----------------------- search --------------------------------------------------


def _load_index(db_path: Path) -> search.ChunkIndex:
    with store.connect(db_path) as conn:
        return search.ChunkIndex(conn)


def _get_hits(query: str, k: int, mode: str, db_path: Path):
    idx = _load_index(db_path)
    embed_fn = None
    if mode in ("semantic", "hybrid"):
        embedder = llm.get_embedder()
        if embedder is None:
            console.print("[yellow]No OPENAI_API_KEY — falling back to BM25.[/yellow]")
            mode = "bm25"
        else:
            embed_fn = embedder.embed
    return idx.search(query, k=k, mode=mode, embed_fn=embed_fn), mode


def _print_hits(hits: list[dict]) -> None:
    if not hits:
        console.print("[yellow]Ничего не найдено.[/yellow]")
        return
    table = Table(show_lines=False, header_style="bold cyan")
    table.add_column("#", justify="right", width=3)
    table.add_column("score", justify="right", width=7)
    table.add_column("via", width=8)
    table.add_column("video", overflow="fold")
    table.add_column("at", width=8)
    table.add_column("snippet", overflow="fold")
    for i, h in enumerate(hits, start=1):
        snippet = h["text"]
        if len(snippet) > 200:
            snippet = snippet[:200] + "…"
        table.add_row(
            str(i),
            f"{h['score']:.3f}",
            h.get("via", ""),
            h["title"] or h["video_id"],
            search.fmt_timestamp(h["ts_start"]),
            snippet,
        )
    console.print(table)
    console.print("\n[dim]Ссылки с таймкодами:[/dim]")
    for i, h in enumerate(hits, start=1):
        console.print(f"  [{i}] {search.with_timestamp_url(h)}")


@app.command("search")
def cmd_search(
    query: str = typer.Argument(...),
    k: int = typer.Option(8, "--k"),
    mode: str = typer.Option("bm25", "--mode", help="bm25 | semantic | hybrid"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    db_path, _ = _resolve_paths(db)
    hits, used_mode = _get_hits(query, k, mode, db_path)
    console.print(f"[dim]mode={used_mode}  k={k}[/dim]")
    _print_hits(hits)


# ----------------------- ask -----------------------------------------------------


@app.command("ask")
def cmd_ask(
    question: str = typer.Argument(...),
    k: int = typer.Option(8, "--k"),
    mode: str = typer.Option("hybrid", "--mode"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    db_path, _ = _resolve_paths(db)
    prov = llm.get_provider()
    if prov is None:
        console.print("[red]No LLM key set (OPENAI_API_KEY or ANTHROPIC_API_KEY).[/red]")
        raise typer.Exit(1)
    hits, used_mode = _get_hits(question, k, mode, db_path)
    if not hits:
        console.print("[yellow]Найдено 0 фрагментов — нечего отвечать.[/yellow]")
        raise typer.Exit(0)
    console.print(f"[dim]mode={used_mode}  hits={len(hits)}  provider={prov.name}[/dim]\n")
    answer = prov.chat(
        prompts.ASK_SYSTEM,
        prompts.ask_user_prompt(question, hits),
        max_tokens=800,
    )
    console.print(Panel(Markdown(answer), title="Ответ", border_style="green"))


# ----------------------- ideas ---------------------------------------------------


@app.command("ideas")
def cmd_ideas(
    topic: str = typer.Argument(...),
    n: int = typer.Option(5, "--n", help="How many ideas"),
    k: int = typer.Option(12, "--k", help="How many source chunks to feed LLM"),
    mode: str = typer.Option("hybrid", "--mode"),
    db: Optional[Path] = typer.Option(None, "--db"),
):
    db_path, _ = _resolve_paths(db)
    prov = llm.get_provider()
    if prov is None:
        console.print("[red]No LLM key set (OPENAI_API_KEY or ANTHROPIC_API_KEY).[/red]")
        raise typer.Exit(1)
    hits, _ = _get_hits(topic, k, mode, db_path)
    if not hits:
        console.print("[yellow]По этой теме ничего нет в архиве.[/yellow]")
        raise typer.Exit(0)
    out = prov.chat(
        prompts.IDEAS_SYSTEM,
        prompts.ideas_user_prompt(topic, n, hits),
        max_tokens=1400,
    )
    console.print(Panel(Markdown(out), title=f"Идеи коротких видео ({n})", border_style="magenta"))


# ----------------------- gaps ----------------------------------------------------


@app.command("gaps")
def cmd_gaps(db: Optional[Path] = typer.Option(None, "--db")):
    db_path, _ = _resolve_paths(db)
    prov = llm.get_provider()
    if prov is None:
        console.print("[red]No LLM key set.[/red]")
        raise typer.Exit(1)
    with store.connect(db_path) as conn:
        videos = store.all_videos(conn)
    if not videos:
        console.print("[yellow]В архиве нет видео — сначала запустите ingest.[/yellow]")
        raise typer.Exit(0)
    out = prov.chat(prompts.GAPS_SYSTEM, prompts.gaps_user_prompt(videos), max_tokens=1600)
    console.print(Panel(Markdown(out), title="Карта тем и пробелы", border_style="cyan"))


# ----------------------- stats ---------------------------------------------------


def _print_stats(db_path: Path) -> None:
    with store.connect(db_path) as conn:
        s = store.stats(conn)
    console.print(
        f"\n[bold]DB:[/bold] {db_path}  "
        f"videos=[green]{s['videos']}[/green]  "
        f"chunks=[green]{s['chunks']}[/green]  "
        f"with_embeddings=[green]{s['chunks_with_embeddings']}[/green]"
    )


@app.command("stats")
def cmd_stats(db: Optional[Path] = typer.Option(None, "--db")):
    db_path, _ = _resolve_paths(db)
    _print_stats(db_path)


if __name__ == "__main__":  # pragma: no cover
    app()
