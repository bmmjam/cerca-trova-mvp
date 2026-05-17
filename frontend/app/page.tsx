"use client";

import { useState } from "react";
import { StatsHeader } from "@/components/StatsHeader";
import { SearchTab } from "@/components/SearchTab";
import { AskTab } from "@/components/AskTab";
import { IdeasTab } from "@/components/IdeasTab";
import { GapsTab } from "@/components/GapsTab";

type Tab = "search" | "ask" | "ideas" | "gaps";

const TABS: { id: Tab; label: string; sub: string }[] = [
  { id: "search", label: "Поиск", sub: "по любому слову или смыслу" },
  { id: "ask", label: "Спросить", sub: "ответ с цитатами и таймкодами" },
  { id: "ideas", label: "Идеи Shorts", sub: "идеи под Shorts и Reels" },
  { id: "gaps", label: "Карта тем", sub: "что густо, что пусто" },
];

export default function Home() {
  const [tab, setTab] = useState<Tab>("search");

  return (
    <main className="min-h-screen">
      {/* --- top nav strip, like the brand site --------------------------- */}
      <div className="border-b border-forest-800/80 bg-forest-950/60 backdrop-blur-sm">
        <div className="mx-auto max-w-5xl px-6 py-4 flex items-center justify-between">
          <a
            href="https://cerca-trova.ru"
            target="_blank"
            rel="noreferrer"
            className="font-serif text-cream-50 text-[15px] tracking-[0.35em] hover:text-brass transition-colors"
          >
            CERCA · TROVA
          </a>
          <div className="font-sans text-[10px] uppercase tracking-widest text-cream-500">
            Content · Intelligence
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-5xl px-6 py-10 sm:py-14">
        {/* --- hero ------------------------------------------------------- */}
        <header className="mb-10 sm:mb-12">
          <div className="space-y-3 mb-7">
            <div className="eyebrow text-brass">Архив бренда · поиск и редполитика</div>
            <h1 className="font-serif text-cream-50 text-4xl sm:text-5xl leading-[1.05] tracking-tight">
              Каждое слово, сказанное на камеру,
              <span className="block italic text-cream-200">— теперь искабельно.</span>
            </h1>
            <p className="font-body text-cream-300 text-lg max-w-2xl leading-relaxed">
              Поиск по транскриптам, цитирование с таймкодами, идеи коротких видео и карта
              тем — поверх YouTube-канала{" "}
              <a
                href="https://www.youtube.com/channel/UCU3fojV39XAXk4lunDDXn4w"
                className="text-brass hover:text-brass-hover underline underline-offset-4 decoration-brass/40"
                target="_blank"
                rel="noreferrer"
              >
                Cerca Trova
              </a>
              .
            </p>
          </div>
          <StatsHeader />
        </header>

        {/* --- tab nav ---------------------------------------------------- */}
        <nav className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          {TABS.map((t) => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`group text-left rounded-sm border px-4 py-3.5 transition-all ${
                  active
                    ? "border-brass bg-forest-800/80 shadow-soft"
                    : "border-forest-700/60 bg-forest-900/40 hover:border-cream-700/40 hover:bg-forest-800/40"
                }`}
              >
                <div
                  className={`font-serif text-lg leading-tight transition-colors ${
                    active ? "text-cream-50" : "text-cream-200 group-hover:text-cream-50"
                  }`}
                >
                  {t.label}
                </div>
                <div
                  className={`mt-1 font-sans text-[10px] uppercase tracking-widest transition-colors ${
                    active ? "text-brass" : "text-cream-500"
                  }`}
                >
                  {t.sub}
                </div>
              </button>
            );
          })}
        </nav>

        {/* --- tab body --------------------------------------------------- */}
        <section>
          {tab === "search" && <SearchTab />}
          {tab === "ask" && <AskTab />}
          {tab === "ideas" && <IdeasTab />}
          {tab === "gaps" && <GapsTab />}
        </section>

        {/* --- footer ----------------------------------------------------- */}
        <footer className="mt-16 pt-8 border-t border-forest-800/60">
          <div className="ornament mb-5">
            <span className="font-serif text-xl italic">CT</span>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-cream-500 font-sans">
            <div className="uppercase tracking-widest">
              Контент-интеллект архива
            </div>
            <div className="uppercase tracking-widest italic font-serif text-cream-400 text-sm tracking-normal">
              proof-of-work
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
