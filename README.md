# Cerca Trova · Content Intelligence MVP

Превращает YouTube-канал бренда в искаемую и переиспользуемую базу знаний — поиск, ответы с цитатами и таймкодами, идеи коротких видео, карта тем.

Демо построено вокруг публичного канала [Cerca Trova](https://www.youtube.com/channel/UCU3fojV39XAXk4lunDDXn4w). Все данные — публичные субтитры YouTube. Это не официальный инструмент бренда.

## Что внутри одной картинкой

```
┌────────────────────────────────────────────────────────────────┐
│ Веб-интерфейс (Next.js · Vercel-native)                        │
│   · Поиск       — по любому слову или смыслу                   │
│   · Спросить    — ответ модели только по найденным цитатам     │
│   · Идеи Shorts — N идей под Shorts/Reels из архива            │
│   · Карта тем   — кластеры тем, что густо / что пусто          │
└────────────────────────────┬───────────────────────────────────┘
                             │ HTTP JSON
                             ▼
┌────────────────────────────────────────────────────────────────┐
│ API (FastAPI · Python 3.11+)                                   │
│   /api/search · /api/ask · /api/ideas · /api/gaps              │
└──────┬─────────────────────────────────┬───────────────────────┘
       │                                 │
       ▼                                 ▼
SQLite (videos · chunks · embeddings)    OpenRouter → Claude Sonnet 4.5
       ▲                                 (чат, RAG)
       │
       │ yt-dlp + парсер VTT + чанкинг
       │
   YouTube-канал бренда
```

Поиск — гибридный: BM25 + cosine по OpenAI-эмбеддингам, сшиты Reciprocal Rank Fusion. Чат — Claude Sonnet 4.5 через OpenRouter. Эмбеддинги — `text-embedding-3-small` через прямой OpenAI-ключ.

## Экономика

| Операция | Цена за один клик |
|---|---|
| Поиск (любой режим) | ~$0.0000002 — фактически бесплатно |
| Спросить (ответ с цитатами) | ~$0.01 |
| Идеи (5 шт.) | ~$0.03 |
| Карта тем | ~$0.03 |
| Эмбеддинги корпуса (разово) | ~$0.001 на ~400 фрагментов |

Активный продакшен (100 ask + 30 ideas + 5 gaps в день) ≈ **$2.5/день ≈ $75/мес**.

## Локально

```bash
# 1) бэкенд
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env             # впиши OPENROUTER_API_KEY + OPENAI_API_KEY
yti ingest "https://www.youtube.com/channel/<ID>/videos" --limit 50
yti embed
uvicorn yti.server:app --reload --port 8000

# 2) фронтенд (в другом терминале)
cd frontend
npm install
npm run dev                       # → http://localhost:3000
```

Фронт через `next.config.mjs` проксирует `/api/*` на `http://127.0.0.1:8000`.

## Деплой

Архитектура раскалывается ровно по линии хостинга.

### Фронт → Vercel

Репо — монорепо: Python-бэкенд в корне, Next.js-фронт в `frontend/`. Vercel-у нужно указать, что Next.js живёт в подкаталоге:

1. **Import Project** → выбрать репо
2. **Configure Project** → **Root Directory** → `frontend`
   (или после первого импорта: *Project Settings → General → Root Directory → Edit → `frontend`*)
3. Framework Preset должен сам определиться как **Next.js** после смены root
4. **Environment Variables** добавить:
   ```
   NEXT_PUBLIC_API_URL = https://<your-backend-host>
   ```
5. Deploy

### Бэкенд → Railway (рекомендуемо)

В репо лежат [`railway.json`](./railway.json) и [`Procfile`](./Procfile) — Railway подхватит автоматически.

1. <https://railway.app/new> → **Deploy from GitHub** → выбрать репо
2. Railway увидит `pyproject.toml` + `Procfile` → соберёт через Nixpacks → стартует `uvicorn yti.server:app`
3. **Variables** (вкладка проекта) — добавить:
   ```
   OPENROUTER_API_KEY = <твой ключ>
   OPENAI_API_KEY     = <твой ключ>
   YTI_PROVIDER       = openrouter
   YTI_CHAT_MODEL     = anthropic/claude-sonnet-4.5
   YTI_EMBED_MODEL    = text-embedding-3-small
   ```
4. **Settings → Networking → Generate Domain** → получишь URL вида `<имя>.up.railway.app`
5. Проверь: `curl https://<railway-url>/api/health` — должно вернуть `{"ok":true,...}`

#### Заливка архива на Railway

База `data/chunks.db` гитом исключена (публичный репо — не публикуем транскрипты). На свежем хосте нужно её собрать. Два варианта:

**А. Однократно через Railway shell:**
```bash
# в Railway dashboard: Service → Settings → Shell
yti ingest "https://www.youtube.com/channel/UCU3fojV39XAXk4lunDDXn4w/videos" --limit 100
yti embed
```
Минус: контейнер Railway эфемерный — при каждом redeploy база пропадёт.

**Б. Постоянный диск (правильно):**
1. Railway → Service → **Settings → Volumes → New Volume**
2. Mount path: `/app/data`
3. После создания тома — через shell выполнить `yti ingest && yti embed` (см. выше). База будет жить в томе и переживёт деплои.

### Подключение фронта к бэку

Когда Railway-URL есть:

1. Vercel → твой проект → **Settings → Environment Variables**
2. Добавить:
   ```
   NEXT_PUBLIC_API_URL = https://<твой>.up.railway.app
   ```
   *(без слеша в конце!)*
3. **Deployments → ⋯ → Redeploy** (env-vars `NEXT_PUBLIC_*` читаются на этапе билда, не рантайма)
4. Открыть Vercel-URL — шапка должна показать число видео и цитат.

## CLI

| Операция | Команда |
|---|---|
| Поиск | `yti search "длина рукава"` |
| Ответ с цитатами | `yti ask "..."` |
| Идеи Shorts | `yti ideas "..." --n 5` |
| Карта тем | `yti gaps` |
| Залить видео | `yti ingest "<url>"` (видео / канал / плейлист) |
| Посчитать эмбеддинги | `yti embed` |
| Статистика | `yti stats` |

Подробности по флагам — в [исходниках CLI](./src/yti/cli.py).

## Структура

```
.
├── README.md
├── pyproject.toml
├── .env.example
├── Procfile
├── railway.json
├── src/yti/
│   ├── cli.py             ← typer entry point
│   ├── server.py          ← FastAPI HTTP-обёртка
│   ├── ingest.py          ← yt-dlp + парсер VTT + чанкинг
│   ├── store.py           ← SQLite-схема
│   ├── search.py          ← BM25 + cosine + RRF-hybrid
│   ├── llm.py             ← провайдеры (OpenRouter / OpenAI / Anthropic)
│   └── prompts.py         ← шаблоны ask / ideas / gaps
└── frontend/              ← Next.js 14 (App Router, TS, Tailwind)
    ├── app/
    ├── components/
    └── lib/
```

## Ограничения (честно)

- **Морфология русского:** BM25 в одиночку матчит точные токены. Гибрид через семантику закрывает падежи и синонимы — поэтому в UI он и стоит по умолчанию.
- **Auto-subs:** YouTube не всегда выдаёт чистый текст. Для проды лучше Whisper.
- **Гэп-анализ** опирается на названия и описания, не на содержание чанков — намеренно для скорости. v2: семантическая кластеризация эмбеддингов.
- **Дедуп rolling-captions:** срезает повтор последнего ≥5-символьного суффикса предыдущей реплики. На стандартных авто-сабах работает хорошо.

## Лицензия и этика

Все данные приходят из публичных авто-субтитров YouTube. Базы `data/*.db` и raw-сабы исключены из git: транскрипты не переиздаём в публичном репозитории. Инструмент учебный, не аффилирован с брендом.
