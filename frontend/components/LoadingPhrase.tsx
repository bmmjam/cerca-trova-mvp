"use client";

import { useRotatingPhrase } from "@/lib/useRotatingPhrase";

/**
 * Inline rotating loader. Use inside a button or beside one to reassure
 * the user during a 5–30s LLM call.
 */
export function LoadingPhrase({
  active,
  phrases,
  className = "",
}: {
  active: boolean;
  phrases: readonly string[];
  className?: string;
}) {
  const phrase = useRotatingPhrase(phrases, active);
  if (!phrase) return null;
  return (
    <span
      key={phrase}
      className={`inline-flex items-center gap-2 fade-in ${className}`}
      style={{ animation: "fadeIn 0.4s ease-out" }}
    >
      <Spinner />
      <span>{phrase}</span>
      <style jsx>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(2px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
      `}</style>
    </span>
  );
}

function Spinner() {
  return (
    <span
      aria-hidden
      className="inline-block w-3 h-3 rounded-full border border-current border-t-transparent animate-spin"
      style={{ animationDuration: "0.9s" }}
    />
  );
}
