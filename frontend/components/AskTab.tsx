"use client";

import { useState } from "react";
import { api, type AskResponse } from "@/lib/api";
import { HitCard } from "./HitCard";
import { Markdown } from "./Markdown";
import { LoadingPhrase } from "./LoadingPhrase";
import { ASK_PHRASES } from "@/lib/useRotatingPhrase";

const EXAMPLES = [
  "что бренд говорит про разницу костюмов 50 000 и 500 000?",
  "как подобрать ткань под фигуру?",
  "когда уместен галстук, а когда нет?",
];

export function AskTab() {
  const [question, setQuestion] = useState("");
  const [data, setData] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(q: string = question) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.ask({ question: q, k: 8, mode: "hybrid" });
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
          <textarea
            rows={2}
            className="input text-lg"
            placeholder="Спросите бренд: «…?» — ответ — строго по найденным фрагментам, со ссылками на таймкоды."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
          />
          <button className="btn-primary w-full" disabled={loading || !question.trim()}>
            {loading ? (
              <LoadingPhrase active phrases={ASK_PHRASES} />
            ) : (
              <>Ответить</>
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
                  setQuestion(ex);
                  run(ex);
                }}
                className="chip hover:border-brass hover:text-brass-hover text-left max-w-full"
              >
                <span className="truncate normal-case tracking-normal font-body text-[11px] text-cream-200">
                  {ex}
                </span>
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

      {data && data.answer && (
        <div className="card-warm p-7">
          <div className="flex items-center justify-between mb-4">
            <span className="eyebrow text-brass">Ответ</span>
            <span className="eyebrow">{data.hits.length} цитат</span>
          </div>
          <Markdown>{data.answer}</Markdown>
        </div>
      )}

      {data && !data.answer && (
        <div className="card p-5 quiet">По этому вопросу ничего не нашлось.</div>
      )}

      {data && data.hits.length > 0 && (
        <details className="card p-5" open>
          <summary className="cursor-pointer eyebrow text-cream-300 hover:text-cream-100">
            Цитаты ({data.hits.length})
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
