# Web app — Reddit Intelligence

Web UI for exploring the Reddit Intelligence database: run SQL, browse data, and use an AI helper to write SQL.

## AI SQL helper and semantic layer

The **AI SQL helper** should receive the **semantic layer** as context whenever it generates or refines SQL. That way the AI knows:

- Which schemas and tables exist (`meta.subreddits`, `clickup.posts`, `clickup.comments`, `clickup.users`, `clickup.engagement_snapshots`)
- Column names and meanings
- Relationships (e.g. `posts.user_id` → `users.user_id`, `comments.post_id` → `posts.post_id`)
- Example SQL patterns and DuckDB-specific notes

### How to wire it

1. **Import the context** from the provided module:
   - ESM: `import { getSemanticLayerContext } from './semantic-layer-context.js';`
   - Or use the constant: `import { SEMANTIC_LAYER_MARKDOWN } from './semantic-layer-context.js';`

2. **When calling the AI** (e.g. to generate or refine SQL):
   - Include the semantic layer in the prompt, e.g. as a system message or as the first user message:
     - “Use the following database schema and examples when writing SQL: …” + `getSemanticLayerContext()`
   - Then append the user’s natural-language request (e.g. “List top 10 posts by number of comments”).

3. **Canonical source:** The human-readable and versioned definition of the semantic layer is in the repo at [docs/semantic_layer.md](../docs/semantic_layer.md). The file [semantic-layer-context.js](./semantic-layer-context.js) in this folder exposes the same content for the web app. When you change the schema or examples, update both (or add a build step that copies `docs/semantic_layer.md` into the bundle).

## Displaying post and comment bodies

Reddit stores body content as HTML in `selftext_html` (posts) and `body_html` (comments). Prefer the plain-text fields `selftext` and `body` when non-empty. When only HTML is available, use the utility in [utils/html-to-text.js](utils/html-to-text.js): `htmlToPlainText(row.selftext_html)` or `htmlToPlainText(row.body_html)` to decode entities and strip tags for safe display.

## Backend (Gemini proxy)

The backend in [backend/](backend/) is a Flask app that calls Gemini 2.5 Flash for natural-language → SQL. It reads the semantic layer from `docs/semantic_layer.md` and exposes `POST /api/nl-to-sql`. Run from repo root: `python -m webapp.backend.app`. See [backend/README.md](backend/README.md).

## Hosting on GitHub Pages

The frontend is static (HTML, JS, CSS) so you can host it on **GitHub Pages**.

1. **Option A — Publish from the `docs/` folder**
   - Copy the frontend files into `docs/`: `index.html`, `app.js`, `styles.css`, `config.js`, and (so the schema link works) `docs/semantic_layer.md` is already there.
   - Copy `webapp/index.html`, `webapp/app.js`, `webapp/styles.css`, `webapp/config.js` into `docs/` (e.g. overwrite or merge; keep `docs/semantic_layer.md`).
   - In your repo: **Settings → Pages → Source**: Deploy from branch `main` (or `master`), folder **/docs**. Save. The site will be at `https://<username>.github.io/<repo>/`.
   - The frontend will call the API at the same origin by default. To use a backend hosted elsewhere (e.g. Vercel, Railway), edit `docs/config.js` and set `window.API_BASE = 'https://your-backend-url';`.

2. **Option B — Publish from branch `gh-pages`**
   - Create a branch `gh-pages`, put the contents of `webapp/` in the root (and optionally `docs/semantic_layer.md`), push. In **Settings → Pages**, choose branch `gh-pages`, folder **/ (root)**. Again, set `window.API_BASE` in `config.js` if the backend is on a different host.

3. **Backend**
   - The backend (Flask app in `webapp/backend/`) must be deployed separately so the frontend can call `/api/nl-to-sql` and `/api/run-sql`. Deploy it to Vercel, Railway, Render, or similar, and set `GEMINI_API_KEY` (and optionally `DUCKDB_PATH` for run-sql) in the host’s environment. Then set `window.API_BASE` in `config.js` to that backend URL.

## Running locally

From the repo root, start the backend (it serves the frontend and the API):

```bash
python -m webapp.backend.app
```

Open **http://127.0.0.1:5000/** in your browser. Ensure `data/reddit.duckdb` exists (or set `DUCKDB_PATH`) so “Run” works.

## Secrets

For the AI SQL helper, set `GEMINI_API_KEY` in your environment or in a `.env` file (or place in `secrets/gemini_api_key`). Never commit the key. The backend reads it and calls Gemini 2.5 Flash so the key never reaches the client.

## Planned features

- UI to study the database (tables, sample rows)
