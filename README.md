# SyncMind — Smart Learning Dashboard

SyncMind is a full-stack, AI-assisted **learning insights** platform. It connects
to a user's **GitHub**, **YouTube**, and **Coursera** activity, distills it into
educational topics using a RAG-backed knowledge base, and recommends
**courses, repositories, videos, and jobs** tailored to the user's interests
and location.

> Built with React, FastAPI, MySQL, Sentence-Transformers,
> KeyBERT, SerpApi (Google Jobs), and a Manifest V3 Chrome extension.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Project Structure](#project-structure)
5. [Getting Started](#getting-started)
6. [Environment Variables](#environment-variables)
7. [How the Recommender Works](#how-the-recommender-works)
8. [API Reference](#api-reference)
9. [Chrome Extension](#chrome-extension)
10. [Database](#database)
11. [Troubleshooting](#troubleshooting)
12. [Credits](#credits)

---

## What It Does

SyncMind helps a user understand and grow their own learning footprint:

- **Sign in with Google** — primary auth, also captures locale used for jobs.
- **Connect GitHub via OAuth** — reads starred repos, recent activity, profile.
- **Connect YouTube via Google scope** — reads recent watch / liked-video signals.
- **Connect Coursera via the Chrome extension** — scrapes My Learning when the
  extension is installed; falls back to cross-platform inference when it isn't.
- **Get personalized recommendations** for each platform: repos, videos, courses.
- **See jobs that match your stack** — derived from your activity and your
  IP-based location, served by Google Jobs (SerpApi).
- **Dashboard** with progress rings, connected-platform cards, and recommendation
  cards (including a "Jobs For You" section).

---

## Architecture

```
                         ┌────────────────────────────────────────┐
                         │             React 18 SPA               │
                         │       (CRA, Tailwind, Framer Motion)   │
                         │   Landing · Dashboard · About pages    │
                         └───────────────┬────────────────────────┘
                                         │  REST + Session cookie
                                         ▼
        ┌──────────────────────────────────────────────────────────┐
        │                       FastAPI backend                    │
        │                                                          │
        │  Auth (Google + GitHub OAuth)   Recommenders             │
        │  Sessions (itsdangerous)        ─ recommend-yt           │
        │  RAG Keyword Filter (MiniLM)    ─ recommend-git          │
        │  KeyBERT keyword extraction     ─ recommend-coursera     │
        │  SerpApi (Google Jobs)          ─ get_jobs               │
        │  Idempotent migrations          ─ /profile/location      │
        └──────────────────────┬───────────────────────────────────┘
                               │  mysql-connector-python
                               ▼
                ┌──────────────────────────────┐
                │       MySQL 8 (Docker)       │
                │  users, github/youtube/      │
                │  coursera_recommendations,   │
                │  job_recommendations         │
                └──────────────────────────────┘

         ┌─────────────────────────────────────────────────┐
         │      Chrome Extension (Manifest V3, optional)   │
         │   content script on coursera.org                │
         │   ─ scrapes __NEXT_DATA__, DOM, URL slugs       │
         │   ─ sends EXTRACTED payload to the React app    │
         └─────────────────────────────────────────────────┘
```

The backend is the source of truth. The Chrome extension is **optional** — if
it's not installed the app gracefully derives Coursera recommendations from
the user's GitHub + YouTube signals.

---

## Tech Stack

**Frontend**
- React 18 (Create React App, not Next.js)
- React Router DOM 6
- Tailwind CSS, Framer Motion, Lucide React, Recharts

**Backend**
- FastAPI + Uvicorn
- `itsdangerous` SessionMiddleware
- `sentence-transformers` (`all-MiniLM-L6-v2`) — retrieval embeddings for the educational RAG filter
- `KeyBERT` — keyphrase extraction
- `Selenium` (headless Chrome) — Coursera fallback scraping when needed
- `mysql-connector-python` — DB driver
- `requests` — GitHub / YouTube / SerpApi clients

**Storage**
- MySQL 8 via Docker Compose (`./docker-compose.yml`)

**Extension**
- Manifest V3 Chrome extension (`frontend/extension/`)

---

## Project Structure

```
SyncMind/
├── README.md                       ← you are here
├── docker-compose.yml              ← MySQL service
├── backend/
│   ├── main.py                     ← FastAPI app, all endpoints
│   ├── auth.py                     ← Google + GitHub OAuth
│   ├── migrations.py               ← idempotent schema migrations (startup)
│   ├── model.py                    ← RAG educational keyword filter
│   ├── requirements.txt
│   ├── .env.example
│   ├── app/
│   │   ├── knowledge_base.py       ← compatibility wrapper → model.py
│   │   └── vectorizer.py
│   ├── utils/
│   │   └── data_loader.py          ← classify_sentence wrapper → RAG
│   └── db/
│       └── init/001_schema.sql     ← initial schema (fresh Docker volume)
└── frontend/
    ├── package.json                ← CRA scripts (npm start / build)
    ├── tailwind.config.js
    ├── src/
    │   ├── App.jsx                 ← router + global state
    │   ├── pages/
    │   │   ├── Landing.jsx         ← OAuth + platform connect flows
    │   │   ├── Dashboard.jsx       ← recommendations + jobs section
    │   │   └── About.jsx
    │   └── components/
    │       ├── RecommendationCard.jsx
    │       ├── ConnectedPlatformCard.jsx
    │       ├── PlatformCard.jsx
    │       └── ...
    └── extension/                  ← Chrome MV3 extension
        ├── manifest.json
        ├── background.js
        ├── coursera-content.js     ← __NEXT_DATA__ + DOM + slug scraper
        └── landing-bridge.js       ← page ↔ extension bridge
```

---

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** and **npm**
- **Docker** (for MySQL)
- A Google Cloud OAuth client (for Google + YouTube scope)
- A GitHub OAuth App
- A [SerpApi](https://serpapi.com/) key (for Jobs)
- A YouTube Data API v3 key

### 1. Clone

```bash
git clone https://github.com/kanishjn/SyncMind.git
cd SyncMind
```

### 2. Start MySQL

```bash
docker compose up -d mysql
```

The first-time boot will run `backend/db/init/001_schema.sql` automatically.
On subsequent boots, `backend/migrations.py` runs at FastAPI startup and
applies any missing columns/tables idempotently.

### 3. Backend

```bash
cd backend

# create .env from the template and fill in your secrets
cp .env.example .env       # (Windows: copy .env.example .env)

# virtualenv
python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows
# venv\Scripts\activate

pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Backend will print `Database schema migrations applied (idempotent).` on
successful startup.

### 4. Frontend

```bash
cd frontend
npm install
npm start
```

The app runs at `http://localhost:3000`. The backend session cookie is set on
`127.0.0.1:8000`, so keep the OAuth callback URLs aligned (see env section).

### 5. Chrome Extension (optional)

See [`frontend/extension/README.md`](frontend/extension/README.md). It can be
side-loaded via `chrome://extensions → Load unpacked` pointing to that folder.
Without it the Coursera connect flow still works via the backend's
cross-platform fallback.

---

## Environment Variables

All backend secrets live in `backend/.env`. Use `backend/.env.example` as the
template. Summary:

| Variable | Required | Purpose |
| --- | --- | --- |
| `YOUTUBE_API_KEY` | yes | YouTube Data API v3 |
| `GITHUB_TOKEN` | optional | Static fallback token for `/search/repositories` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | yes | Google OAuth |
| `GOOGLE_REDIRECT_URI` | yes | `http://127.0.0.1:8000/auth/google/callback` |
| `GIT_CLIENT_ID` / `GIT_CLIENT_SECRET` | yes | GitHub OAuth App |
| `GITHUB_REDIRECT_URI` | yes | **Must equal** the GitHub OAuth App callback exactly (use `127.0.0.1`, not `localhost`) |
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | yes | MySQL connection (defaults match `docker-compose.yml`) |
| `DATABASE_URL` | yes | SQLAlchemy-style URL (used by some helpers) |
| `SESSION_SECRET_KEY` | yes | Signs the session cookie |
| `SERPAPI_KEY` | yes | Google Jobs via SerpApi |
| `RAG_KB_PATH` / `EDUCATIONAL_KB_PATH` | optional | Path to the educational RAG knowledge base (`.json`, `.jsonl`, `.csv`, `.txt`, `.md`). Defaults to `backend/app/educational_kb.jsonl` when present |
| `RAG_SIMILARITY_THRESHOLD` | optional | Top retrieval score required for an educational keyword (default `0.45`) |
| `RAG_TOP_K` | optional | Number of KB evidence documents retrieved per keyword (default `3`) |
| `RAG_CACHE_PATH` | optional | Embedding cache path (default `backend/app/rag_embeddings.npz`) |
| `KB_THRESHOLD` | optional | Deprecated fallback for `RAG_SIMILARITY_THRESHOLD` |

> ⚠️ **Important**: GitHub is strict about the redirect URI — `localhost` and
> `127.0.0.1` are **not** interchangeable. Whichever you put in your GitHub
> OAuth App settings is what `GITHUB_REDIRECT_URI` must be too.

---

## How the Recommender Works

### Educational RAG Filter (replaces the old Random Forest)

The original prototype used TF-IDF + a Random Forest classifier to decide
whether a keyword was "educational." It was brittle, locked into a snapshot
of scikit-learn, and produced an `InconsistentVersionWarning` at startup.

It has been replaced with a **RAG-based keyword filter** in
`backend/model.py`:

- The knowledge base is loaded from `RAG_KB_PATH` / `EDUCATIONAL_KB_PATH`, or
  from `backend/app/educational_kb.jsonl` when that file exists.
- Supported KB formats are JSON, JSONL, CSV, TXT, and Markdown. JSON/CSV rows
  can use fields such as `title`, `topic`, `keywords`, `summary`,
  `description`, `content`, `body`, or `text`.
- KB entries should describe educational topics or domains; this is retrieved
  evidence, not a mixed positive/negative classifier training set.
- Each KB document is embedded once with **Sentence-Transformers
  `all-MiniLM-L6-v2`** and cached to `RAG_CACHE_PATH`.
- At runtime, each KeyBERT phrase retrieves its top KB evidence by cosine
  similarity. The phrase is accepted when the top retrieval score is at least
  `RAG_SIMILARITY_THRESHOLD` (default `0.45`).
- `utils/data_loader.classify_sentence` is still the stable wrapper for
  existing call sites, but it now delegates to the RAG filter.

Until a project-specific KB is provided, `backend/model.py` uses a small
built-in educational seed corpus so the app remains usable in development.

### Keyword extraction

`KeyBERT` (`extract_keywords`) pulls keyphrases out of raw text (titles,
descriptions, slugs). Phrases are classified **whole** — splitting
`"machine learning"` into `"machine"` + `"learning"` was destroying the
context KeyBERT extracted.

### Coursera recommendations

1. If the extension is installed and the user is signed in to Coursera, the
   content script returns titles + slugs from `__NEXT_DATA__`, the DOM
   (`MutationObserver`-watched), **and** URL slugs as a third evidence source.
2. If the extension is **not** present, `/recommend-coursera` is called with
   an empty history and the backend falls back to deriving keywords from the
   user's GitHub + YouTube recommendations (`recommendCOURSERA` cross-platform
   path).

### Job recommendations

`_derive_job_query_for_user` builds a job-search query that's specifically
shaped for Google Jobs:

1. Pulls keywords from the user's **GitHub + YouTube** recommendations
   (Coursera is excluded because "Python course" makes a poor job query).
2. Strips learning-oriented stopwords (`course`, `tutorial`, `lecture`, …).
3. Maps technical concepts to **role titles** via `_DOMAIN_ROLE_MAP`
   (e.g. `tensorflow → machine learning engineer`,
   `react → frontend engineer`).
4. Prefixes the dominant GitHub language if available
   (e.g. `Python machine learning engineer`).

Location comes from two sources, in order:

1. Client-side IP geolocation (`ipapi.co`) posted to `/profile/location`.
2. Google's `locale` field captured during OAuth (fallback if no IP data).

Results are normalized and cached in the `job_recommendations` table.

---

## API Reference

All endpoints are mounted on the FastAPI app (`backend/main.py`) unless noted.

### Auth (`backend/auth.py`)

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/auth/google/login` | Start Google OAuth |
| GET | `/auth/google/callback` | Google OAuth callback; sets session + persists `locale` |
| GET | `/auth/claim` | Bind a pending Google session to a frontend tab |
| GET | `/auth/github` | Start GitHub OAuth (scope URL-encoded) |
| GET | `/auth/github/callback` | GitHub OAuth callback; stores token in session |
| GET | `/auth/user` | Returns the current authenticated user |
| GET | `/auth/test-session` | Session debug helper |

### Core (`backend/main.py`)

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/fetch` | Persist a user (after Google OAuth) |
| GET | `/get_userid?email=` | Returns the internal user id |
| GET | `/token?email=` | Returns the GitHub access token for a user |
| POST | `/fetch_git` | Persist GitHub profile + recent activity |
| GET | `/get_github_data?email=` | Returns stored GitHub profile |
| GET | `/get_youtube_data?email=` | Returns stored YouTube profile |
| GET | `/auth/status` | Per-platform connection flags |

### Recommendations

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/recommend-yt` | Build + persist YouTube recommendations |
| POST | `/recommend-git?token=` | Build + persist GitHub recommendations (prefers user OAuth token) |
| POST | `/recommend-coursera` | Build + persist Coursera recommendations (cross-platform fallback when history is empty) |
| GET | `/get_github_recommendations?email=` | Read GitHub recs |
| GET | `/get_youtube_recommendations?email=` | Read YouTube recs |
| GET | `/get_coursera_recommendations?email=` | Read Coursera recs |

### Jobs

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/profile/location` | Persist IP-derived location for the signed-in user |
| GET | `/get_jobs?email=` | Build + cache jobs via SerpApi using interests + location |
| GET | `/get_job_recommendations?email=` | Read cached job recommendations |

### Debug

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/debug/session` | Dump the current session |
| GET | `/debug/session/check` | Quick session sanity check |

---

## Chrome Extension

The extension at `frontend/extension/` is a Manifest V3 add-on that helps the
Coursera connect flow by reading the user's My Learning page from inside the
browser.

Key details:

- **Manifest V3** requires `host_permissions` for both `coursera.org` and
  `localhost:3000` / `127.0.0.1:3000` so the background worker can use
  `chrome.tabs.*` to message the React app.
- The content script (`coursera-content.js`) combines **three** evidence
  sources to survive Coursera's dynamic rendering:
  1. Recursively walks the Next.js hydration payload (`__NEXT_DATA__`).
  2. DOM scraping under a `MutationObserver` (Coursera lazy-renders).
  3. Mines keywords from URL slugs (`/learn/machine-learning` →
     `machine learning`).
- `landing-bridge.js` announces presence to the React app via `postMessage`
  (`EXTENSION_PRESENT`) so the frontend can decide whether to wait for an
  `EXTRACTED` payload or skip straight to the fallback.

Load it manually via `chrome://extensions → Developer mode → Load unpacked →
frontend/extension`. Bump the version in `manifest.json` to force reload
during development.

---

## Database

Schema is defined in `backend/db/init/001_schema.sql` and applied
automatically the first time the MySQL volume is created. For existing
volumes, `backend/migrations.py` runs at FastAPI startup and adds any
missing columns / tables in an idempotent way (`INFORMATION_SCHEMA`
checks before `ALTER TABLE` / `CREATE TABLE`).

Tables:

- `users` — Google profile + `locale`, `country`, `region`, `city`,
  `country_code`, `location_updated_at`.
- `github_recommendations`, `youtube_recommendations`,
  `coursera_recommendations` — per-platform cached recs.
- `job_recommendations` — cached SerpApi job results with the query and
  location used to generate them.

To reset everything during development:

```bash
docker compose down -v   # removes the volume so 001_schema.sql re-runs
docker compose up -d mysql
```

---

## Troubleshooting

**`The redirect_uri is not associated with this application` (GitHub)**
The redirect URI in `backend/.env` must match the GitHub OAuth App
**exactly** — including `127.0.0.1` vs `localhost`.

**`InconsistentVersionWarning` from scikit-learn on startup**
This was the old Random Forest model. It is no longer loaded; the RAG filter
in `backend/model.py` replaces it. Any old `.pkl` classifier/vectorizer files
are obsolete.

**No Coursera keywords extracted**
Either install the extension and sign in to Coursera in that browser, or
just hit Connect anyway — the backend will derive Coursera recs from your
GitHub + YouTube signals.

**Empty / irrelevant jobs**
Ensure `SERPAPI_KEY` is set, connect GitHub + YouTube first (Coursera is
intentionally excluded from the job-query source pool), and that
`/profile/location` was called (the Dashboard does this automatically via
`ipapi.co`).

---

## Credits

Made with care by
[Jal](https://github.com/Jal-Bafana),
[Kanish](https://github.com/kanishjn), and
[Saurabh](https://github.com/sdsorigins).
