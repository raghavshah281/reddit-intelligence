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

## Planned features

- UI to study the database (tables, sample rows)
- Ad-hoc SQL execution (read-only)
- AI helper that uses the semantic layer to generate and refine SQL
