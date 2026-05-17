"use client";

import { useEffect, useState } from "react";
import { api, type StatsResponse } from "@/lib/api";

function formatHours(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.round((totalSeconds % 3600) / 60);
  if (h === 0) return `${m} мин`;
  if (m === 0) return `${h} ч`;
  return `${h} ч ${m} мин`;
}

export function StatsHeader() {
  const [stats, setStats] = useState<StatsResponse | null>(null);

  useEffect(() => {
    api.stats().then(setStats).catch(() => setStats(null));
  }, []);

  if (!stats) {
    return <div className="py-4 border-y border-forest-700/60 h-[68px]" />;
  }

  const totalSeconds = stats.videos_list.reduce((acc, v) => acc + (v.duration_s || 0), 0);

  return (
    <div className="grid grid-cols-3 gap-x-6 gap-y-3 py-4 border-y border-forest-700/60">
      <div className="space-y-1">
        <div className="eyebrow">Видео в архиве</div>
        <div className="font-serif text-2xl text-cream-50 leading-none">{stats.videos}</div>
      </div>
      <div className="space-y-1">
        <div className="eyebrow">Цитат</div>
        <div className="font-serif text-2xl text-cream-50 leading-none">{stats.chunks}</div>
      </div>
      <div className="space-y-1">
        <div className="eyebrow">Часов записи</div>
        <div className="font-serif text-2xl text-cream-50 leading-none">
          {formatHours(totalSeconds)}
        </div>
      </div>
    </div>
  );
}
