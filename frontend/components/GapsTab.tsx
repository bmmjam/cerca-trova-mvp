"use client";

import { useState } from "react";
import { api, type GapsResponse } from "@/lib/api";
import { Markdown } from "./Markdown";
import { LoadingPhrase } from "./LoadingPhrase";
import { GAPS_PHRASES } from "@/lib/useRotatingPhrase";

export function GapsTab() {
  const [data, setData] = useState<GapsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const r = await api.gaps();
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
        <p className="font-body text-cream-200 text-[15px] leading-relaxed">
          Группируем все ролики канала по темам и подсказываем, где густо, а где пусто —
          и какие 5–7 видео логично снять, чтобы закрыть пробелы.
        </p>
        <button className="btn-primary" onClick={run} disabled={loading}>
          {loading ? (
            <LoadingPhrase active phrases={GAPS_PHRASES} />
          ) : data ? (
            <>Перегенерировать</>
          ) : (
            <>Построить карту тем</>
          )}
        </button>
      </div>

      {error && (
        <div className="card border-red-900/60 bg-red-950/30 p-4">
          <span className="eyebrow text-red-300">Ошибка</span>
          <div className="mt-1 text-sm font-body text-cream-200">{error}</div>
        </div>
      )}

      {data?.map && (
        <div className="card-warm p-7">
          <div className="flex items-center justify-between mb-4">
            <span className="eyebrow text-brass">Карта тем и пробелы</span>
            <span className="eyebrow">{data.videos_count} видео</span>
          </div>
          <Markdown>{data.map}</Markdown>
        </div>
      )}

      {data && !data.map && (
        <div className="card p-5 quiet">{data.note || "Нет данных для анализа."}</div>
      )}
    </div>
  );
}
