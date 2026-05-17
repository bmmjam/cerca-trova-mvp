"use client";

import { useEffect, useState } from "react";

/**
 * Cycle through a list of phrases every `intervalMs` while `active` is true.
 * Returns the current phrase. When inactive, returns null.
 *
 * The cycle re-starts from index 0 every time `active` flips to true, so the
 * user always sees the calming opening line first.
 */
export function useRotatingPhrase(
  phrases: readonly string[],
  active: boolean,
  intervalMs = 2500
): string | null {
  const [i, setI] = useState(0);

  useEffect(() => {
    if (!active) {
      setI(0);
      return;
    }
    setI(0);
    const t = setInterval(() => {
      setI((prev) => (prev + 1) % phrases.length);
    }, intervalMs);
    return () => clearInterval(t);
  }, [active, phrases, intervalMs]);

  if (!active) return null;
  return phrases[i] ?? phrases[0];
}

// --- shared phrase pools -----------------------------------------------

export const ASK_PHRASES = [
  "Перечитываю архив…",
  "Ищу подходящие фрагменты…",
  "Сверяю по таймкодам…",
  "Подбираю формулировку…",
  "Собираю ответ с цитатами…",
  "Финализирую…",
] as const;

export const IDEAS_PHRASES = [
  "Просматриваю архив на тему…",
  "Отбираю самые цепкие фрагменты…",
  "Прикидываю хуки для первых секунд…",
  "Сшиваю сценарии под Shorts…",
  "Подбираю обложки и таймкоды…",
  "Финальный проход — убираю повторы…",
] as const;

export const GAPS_PHRASES = [
  "Перечитываю все названия и описания…",
  "Группирую ролики по темам…",
  "Считаю, где густо, а где пусто…",
  "Ищу логичные пробелы в редполитике…",
  "Формулирую идеи будущих видео…",
] as const;

export const SEARCH_PHRASES = [
  "Ищу…",
  "Сопоставляю формулировки…",
  "Готово почти.",
] as const;
