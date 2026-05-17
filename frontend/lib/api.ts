// Thin client over the FastAPI backend. The Next.js rewrite proxies /api/* in dev;
// on Vercel set NEXT_PUBLIC_API_URL to the deployed backend.

export type SearchMode = "bm25" | "semantic" | "hybrid";

export interface Hit {
  chunk_id: number;
  video_id: string;
  title: string;
  url: string;
  ts_start: number;
  ts_end: number;
  ts_label: string;
  deep_link: string;
  text: string;
  score: number;
  via: string;
}

export interface SearchResponse {
  mode: SearchMode;
  note: string | null;
  hits: Hit[];
}

export interface AskResponse extends SearchResponse {
  answer: string | null;
  provider?: string;
  model?: string;
}

export interface IdeasResponse extends SearchResponse {
  ideas: string | null;
  provider?: string;
  model?: string;
}

export interface GapsResponse {
  map: string | null;
  videos_count?: number;
  note?: string;
  provider?: string;
  model?: string;
}

export interface VideoSummary {
  video_id: string;
  title: string;
  url: string;
  upload_date: string;
  duration_s: number;
}

export interface StatsResponse {
  videos: number;
  chunks: number;
  chunks_with_embeddings: number;
  videos_list: VideoSummary[];
}

export interface HealthResponse {
  ok: boolean;
  chat_provider: string | null;
  chat_model: string | null;
  embedder: string | null;
  embed_model: string | null;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => http<HealthResponse>("/api/health"),
  stats: () => http<StatsResponse>("/api/stats"),
  search: (body: { query: string; k: number; mode: SearchMode }) =>
    http<SearchResponse>("/api/search", { method: "POST", body: JSON.stringify(body) }),
  ask: (body: { question: string; k: number; mode: SearchMode }) =>
    http<AskResponse>("/api/ask", { method: "POST", body: JSON.stringify(body) }),
  ideas: (body: { topic: string; n: number; k: number; mode: SearchMode }) =>
    http<IdeasResponse>("/api/ideas", { method: "POST", body: JSON.stringify(body) }),
  gaps: () => http<GapsResponse>("/api/gaps"),
};
