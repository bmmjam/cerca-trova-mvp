# youtube_intel — frontend

Next.js 14 (App Router, TypeScript, Tailwind). Renders the four `yti`
operations — search / ask / ideas / gaps — as a single-page UI that calls
the FastAPI backend.

## Local development

```bash
# 1. Start the Python backend (from the project root)
cd ..
source .venv/bin/activate
uvicorn yti.server:app --reload --port 8000

# 2. In another terminal, start the frontend
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

`next.config.mjs` rewrites `/api/*` to the backend, so the frontend has no
hard-coded URLs.

## Deploying to Vercel

The frontend deploys as a standard Next.js project. The backend, however,
needs Python + SQLite + (optionally) `yt-dlp`, which doesn't fit Vercel's
serverless model cleanly. Run it elsewhere (Railway, Fly.io, Render) and
set the env var on the Vercel project:

```
NEXT_PUBLIC_API_URL=https://your-backend.example.com
```

`next.config.mjs` picks this up and proxies `/api/*` through.
