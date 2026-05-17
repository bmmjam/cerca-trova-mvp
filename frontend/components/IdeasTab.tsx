"use client";

import { useState } from "react";
import { api, type IdeasResponse } from "@/lib/api";
import { HitCard } from "./HitCard";
import { Markdown } from "./Markdown";
import { LoadingPhrase } from "./LoadingPhrase";
import { IDEAS_PHRASES } from "@/lib/useRotatingPhrase";

const EXAMPLES = ["посадка пиджака", "белые рубашки", "костюмы на свадьбу"];

const COUNT_OPTIONS = [3, 5, 7, 10];

export function IdeasTab() {
  const [topic, setTopic] = useState("");
  const [n, setN] = useState(5);
  const [data, setData] = useState<IdeasResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(t: string = topic) {
    if (!t.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.ideas({ topic: t, n, k: 12, mode: "hybrid" });
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
          className="space-y-3"
        >
          <input
            className="input text-lg"
            placeholder="Тема для коротких видео — напр. «посадка пиджака»"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
          <div className="flex items-center gap-3">
            <span className="eyebrow">сколько идей</span>
            <div className="flex gap-1.5">
              {COUNT_OPTIONS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setN(c)}
                  className={`rounded-sm border px-3 py-1.5 font-serif text-base leading-none transition-colors ${
                    n === c
                      ? "border-brass bg-brass text-forest-950"
                      : "border-forest-600/60 text-cream-200 hover:border-cream-700"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
          <button className="btn-primary w-full" disabled={loading || !topic.trim()}>
            {loading ? (
              <LoadingPhrase active phrases={IDEAS_PHRASES} />
            ) : (
              <>Сгенерировать {n} идей</>
            )}
          </button>
        </form>
        <div className="space-y-2 pt-1">
          <span className="eyebrow">примеры</span>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => {
                  setTopic(ex);
                  run(ex);
                }}
                className="chip hover:border-brass hover:text-brass-hover"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="card border-red-900/60 bg-red-950/30 p-4">
          <span className="eyebrow text-red-300">Ошибка</span>
          <div className="mt-1 text-sm font-body text-cream-200">{error}</div>
        </div>
      )}

      {data?.ideas && (
        <div className="card-warm p-7">
          <div className="flex items-center justify-between mb-4">
            <span className="eyebrow text-brass">Идеи коротких видео</span>
            <span className="eyebrow">из {data.hits.length} фрагментов</span>
          </div>
          <Markdown>{data.ideas}</Markdown>
        </div>
      )}

      {data && data.hits.length > 0 && (
        <details className="card p-5">
          <summary className="cursor-pointer eyebrow text-cream-300 hover:text-cream-100">
            Исходные фрагменты ({data.hits.length})
          </summary>
          <div className="space-y-3 mt-4">
            {data.hits.map((h, i) => (
              <HitCard key={h.chunk_id} hit={h} index={i + 1} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
