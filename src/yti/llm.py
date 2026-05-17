"""LLM and embedding provider abstraction.

Routing policy (per the project owner's instruction):

  * Embeddings    → OpenAI direct (only OpenAI key is used for OpenAI calls).
  * Chat / RAG    → Claude via OpenRouter (preferred), with direct Anthropic and
                    direct OpenAI as fallbacks if their keys are present.

Environment variables:

  OPENAI_API_KEY        — used ONLY for embeddings (text-embedding-3-small by default)
  OPENROUTER_API_KEY    — used for chat (Claude on OpenRouter)
  OPENROUTER_BASE_URL   — defaults to https://openrouter.ai/api/v1
  ANTHROPIC_API_KEY     — optional fallback for chat if no OpenRouter key

  YTI_PROVIDER          — force a chat provider: openrouter | anthropic | openai
  YTI_CHAT_MODEL        — chat model id for whichever provider is active
  YTI_EMBED_MODEL       — OpenAI embedding model (default text-embedding-3-small)
"""
from __future__ import annotations

import os
from typing import Protocol

import numpy as np


class LLMProvider(Protocol):
    name: str

    def chat(self, system: str, user: str, max_tokens: int = 800) -> str: ...

    def embed(self, texts: list[str]) -> np.ndarray:
        """Return float32 array of shape (len(texts), dim). Optional capability."""
        ...


class OpenAIProvider:
    """Direct OpenAI client. Used for embeddings; can also chat if needed."""

    name = "openai"

    def __init__(
        self,
        api_key: str,
        chat_model: str = "gpt-4o-mini",
        embed_model: str = "text-embedding-3-small",
        base_url: str | None = None,
    ) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        self.chat_model = chat_model
        self.embed_model = embed_model

    def chat(self, system: str, user: str, max_tokens: int = 800) -> str:
        resp = self.client.chat.completions.create(
            model=self.chat_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.4,
        )
        return resp.choices[0].message.content or ""

    def embed(self, texts: list[str]) -> np.ndarray:
        out: list[list[float]] = []
        BATCH = 96
        for i in range(0, len(texts), BATCH):
            batch = texts[i : i + BATCH]
            resp = self.client.embeddings.create(model=self.embed_model, input=batch)
            out.extend([d.embedding for d in resp.data])
        return np.array(out, dtype=np.float32)


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter is OpenAI-compatible; we reuse the OpenAI client with a different base URL.

    We deliberately do NOT expose embeddings here — OpenRouter does proxy some embedding
    models but the project policy is to route embeddings only through the direct OpenAI key.
    """

    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        chat_model: str = "anthropic/claude-sonnet-4.5",
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        super().__init__(api_key=api_key, chat_model=chat_model, base_url=base_url)

    def embed(self, texts: list[str]) -> np.ndarray:  # pragma: no cover
        raise RuntimeError(
            "OpenRouter provider intentionally does not embed. "
            "Embeddings go through the direct OpenAI key (set OPENAI_API_KEY)."
        )


class AnthropicProvider:
    """Direct Anthropic. Kept as a fallback if no OpenRouter key is set."""

    name = "anthropic"

    def __init__(self, api_key: str, chat_model: str = "claude-sonnet-4-6") -> None:
        from anthropic import Anthropic

        self.client = Anthropic(api_key=api_key)
        self.chat_model = chat_model

    def chat(self, system: str, user: str, max_tokens: int = 800) -> str:
        msg = self.client.messages.create(
            model=self.chat_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts: list[str] = []
        for block in msg.content:
            if getattr(block, "type", None) == "text":
                parts.append(block.text)
        return "".join(parts)

    def embed(self, texts: list[str]) -> np.ndarray:
        raise RuntimeError(
            "Anthropic provider does not expose embeddings. "
            "Set OPENAI_API_KEY for embeddings."
        )


# --- factories ------------------------------------------------------------

def _openrouter() -> OpenRouterProvider | None:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return None
    base = os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    model = os.getenv("YTI_CHAT_MODEL") or os.getenv("YTI_OPENROUTER_MODEL") or "anthropic/claude-sonnet-4.5"
    return OpenRouterProvider(api_key=key, chat_model=model, base_url=base)


def _anthropic_direct() -> AnthropicProvider | None:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    return AnthropicProvider(
        api_key=key,
        chat_model=os.getenv("YTI_ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    )


def _openai_chat() -> OpenAIProvider | None:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    return OpenAIProvider(
        api_key=key,
        chat_model=os.getenv("YTI_CHAT_MODEL", "gpt-4o-mini"),
        embed_model=os.getenv("YTI_EMBED_MODEL", "text-embedding-3-small"),
    )


def get_provider() -> LLMProvider | None:
    """Pick the chat provider. Default: OpenRouter (Claude) → Anthropic → OpenAI."""
    pref = (os.getenv("YTI_PROVIDER") or "").strip().lower()
    factories = {
        "openrouter": _openrouter,
        "anthropic": _anthropic_direct,
        "openai": _openai_chat,
    }
    if pref in factories:
        p = factories[pref]()
        if p is not None:
            return p
    for name in ("openrouter", "anthropic", "openai"):
        p = factories[name]()
        if p is not None:
            return p
    return None


def get_embedder() -> OpenAIProvider | None:
    """Return a provider that can do embeddings (OpenAI only, by project policy)."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    return OpenAIProvider(
        api_key=key,
        embed_model=os.getenv("YTI_EMBED_MODEL", "text-embedding-3-small"),
    )
