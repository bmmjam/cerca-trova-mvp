"use client";

import type { Hit } from "@/lib/api";

export function HitCard({ hit, index }: { hit: Hit; index: number }) {
  return (
    <div className="card p-5 transition-colors hover:border-cream-700/50">
      <div className="flex items-start justify-between gap-4 mb-2">
        <span className="font-serif text-brass text-lg leading-none pt-0.5">[{index}]</span>
        <a
          href={hit.deep_link}
          target="_blank"
          rel="noreferrer"
          className="font-mono text-xs text-brass hover:text-brass-hover whitespace-nowrap pt-1"
        >
          {hit.ts_label} ↗
        </a>
      </div>
      <div className="font-serif text-lg text-cream-50 mb-2 leading-snug line-clamp-2">
        {hit.title}
      </div>
      <div className="font-body text-[15px] text-cream-200/90 leading-relaxed">
        {hit.text}
      </div>
    </div>
  );
}
