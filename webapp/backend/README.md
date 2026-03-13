# Web app backend

Flask backend that (1) serves the static frontend from `webapp/`, (2) converts natural language to SQL via **Gemini 2.5 Flash** (`POST /api/nl-to-sql`), and (3) runs read-only SQL against the DuckDB database (`POST /api/run-sql`). The API key never leaves the server.

## Setup

1. Install dependencies from repo root: `pip install -r requirements.txt`
2. Set **`GEMINI_API_KEY`** in your environment, in a `.env` file at the repo root, or in **`secrets/gemini_api_key`** (one line, the key only). Never commit the key.

## Run locally

From the repo root:

```bash
python -m webapp.backend.app
```

Or from this directory:

```bash
python app.py
```

Server listens on `http://0.0.0.0:5000`.

## Endpoints

- **`GET /`** — Serves the frontend (index.html).
- **`POST /api/nl-to-sql`** — Body: `{"question": "..."}`. Returns `{"sql": "SELECT ..."}` or `{"error": "..."}` (400/500).
- **`POST /api/run-sql`** — Body: `{"sql": "SELECT ..."}`. Read-only; only SELECT allowed. Returns `{"columns": [...], "rows": [...]}` or `{"error": "..."}`. Uses `data/reddit.duckdb` unless `DUCKDB_PATH` is set.
- **`GET /api/health`** — Returns `{"status": "ok"}` (no API key required).

## Deployment

For production (e.g. Vercel, Railway, Cloudflare), set `GEMINI_API_KEY` in the platform’s environment variables. The app loads `.env` from the repo root for local development only.
