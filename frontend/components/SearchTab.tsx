"use client";

import { useState } from "react";
import { api, type SearchResponse } from "@/lib/api";
import { HitCard } from "./HitCard";
import { LoadingPhrase } from "./LoadingPhrase";
import { SEARCH_PHRASES } from "@/lib/useRotatingPhrase";

const EXAMPLES = ["длина рукава", "посадка пиджака", "ткани", "галстук"];

export function SearchTab() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(q: string = query) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.search({ query: q, k: 8, mode: "hybrid" });
      setData(r);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="card p-6 space-y-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run();
          }}
          className="flex flex-col sm:flex-row gap-3"
        >
          <input
            className="input text-lg flex-1"
            placeholder="Что искать в архиве — напр. «длина рукава»"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <button className="btn-primary sm:w-auto" disabled={loading || !query.trim()}>
            {loading ? (
              <LoadingPhrase active phrases={SEARCH_PHRASES} />
            ) : (
              <>Искать</>
            )}
          </button>
        </form>
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="eyebrow">примеры</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => {
                setQuery(ex);
                run(ex);
              }}
              className="chip hover:border-brass hover:text-brass-hover"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="card border-red-900/60 bg-red-950/30 p-4">
          <span className="eyebrow text-red-300">Ошибка</span>
          <div className="mt-1 text-sm font-body text-cream-200">{error}</div>
        </div>
      )}

      {data && (
        <div className="space-y-4">
          <div className="font-body text-cream-400 text-sm">
            {data.hits.length === 0
              ? "Ничего не нашлось."
              : `Найдено ${data.hits.length}`}
          </div>
          {data.hits.length > 0 &&
            data.hits.map((h, i) => <HitCard key={h.chunk_id} hit={h} index={i + 1} />)}
        </div>
      )}
    </div>
  );
}
