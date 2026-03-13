/**
 * Semantic layer for the AI SQL helper.
 * Pass this as context (system or user message) when generating or refining SQL
 * so the AI knows table names, columns, relationships, and example patterns.
 *
 * Usage (example):
 *   const context = getSemanticLayerContext();
 *   // Send context to AI along with user query: "List top 10 posts by comments"
 */

const SEMANTIC_LAYER_MARKDOWN = `# Semantic layer — Reddit Intelligence database

This document describes the database structure for the AI SQL helper. Use it as system or user context when generating SQL. Tables are in DuckDB; each subreddit has its own schema.

---

## 1. Schema discovery

- **One schema per subreddit.** Each tracked subreddit has a dedicated DuckDB schema (e.g. \`clickup\` for r/clickup). All content and users for that subreddit live in that schema.
- **Registry:** The list of schemas is in \`meta.subreddits\`. Column \`schema_name\` is the DuckDB schema name (e.g. \`clickup\`). Columns \`name\` and \`display_name\` identify the subreddit.
- **Querying a subreddit:** Always use the schema-qualified table name. For r/clickup use \`clickup.posts\`, \`clickup.comments\`, \`clickup.users\`. For another subreddit, use its \`schema_name\` from \`meta.subreddits\` (e.g. \`other_sub.posts\`).

To list available schemas:

\`\`\`sql
SELECT schema_name, name, display_name FROM meta.subreddits;
\`\`\`

---

## 2. Table descriptions

### meta.subreddits

Registry of tracked subreddits. One row per subreddit. Contains \`subreddit_id\`, \`name\`, \`display_name\`, \`schema_name\` (the DuckDB schema), \`subscribers\`, \`last_synced_at\`. Use this to discover which schemas exist and how to address them.

### users (per-schema, e.g. clickup.users)

Reddit users who have posted or commented in this subreddit. One row per user. Join to posts and comments via \`user_id\`. Contains \`username\`, optional \`flair_text\`, \`is_premium\`, and first/last seen timestamps.

### posts (per-schema, e.g. clickup.posts)

All posts in this subreddit. Primary content table. Each row has engagement (score, ups, downs, upvote_ratio, num_comments, total_awards_received), timestamps (created_utc, edited_at), and content (title, selftext, url, permalink). Join comments on \`post_id\`; join users on \`user_id\`.

### comments (per-schema, e.g. clickup.comments)

All comments and replies. Top-level comments have \`parent_comment_id\` NULL and \`depth\` 0; replies have \`parent_comment_id\` set to the parent comment's \`comment_id\` and \`depth\` ≥ 1. \`thread_path\` is an array of IDs from root to this comment (for tree queries). Join to posts on \`post_id\`, to users on \`user_id\`, and to parent comment on \`parent_comment_id\` when non-NULL.

### engagement_snapshots (per-schema, e.g. clickup.engagement_snapshots)

Weekly (or periodic) snapshots of post engagement. One row per post per snapshot time. Columns: \`post_id\`, \`snapshot_at\`, \`score\`, \`num_comments\`, \`upvote_ratio\`. Use for "score over time" or week-over-week comparison.

---

## 3. Column glossary

### meta.subreddits

| Column           | Meaning |
|------------------|--------|
| subreddit_id     | Reddit's internal id (e.g. t5_xxxxx). Primary key. |
| name             | Normalized subreddit name (e.g. clickup). |
| display_name     | Display name (e.g. ClickUp). |
| schema_name      | DuckDB schema name to use (e.g. clickup). |
| subscribers      | Last known subscriber count. |
| last_synced_at   | When we last refreshed this subreddit's data. |

### users

| Column        | Meaning |
|---------------|--------|
| user_id       | Reddit author_fullname (e.g. t2_xxxxx). Primary key. |
| username      | Reddit username. |
| is_premium    | Reddit premium user. |
| flair_text    | User flair in this subreddit. |
| first_seen_at | First time we saw this user in this subreddit. |
| last_seen_at  | Last time we saw this user. |

### posts

| Column                   | Meaning |
|--------------------------|--------|
| post_id                  | Reddit post id (short). Primary key. |
| user_id                  | Author; foreign key to users. |
| title                    | Post title. |
| selftext                 | Post body (plain text). |
| permalink, url, domain   | Links and domain. |
| score                    | Net vote score. |
| ups, downs               | Upvotes / downvotes (when available). |
| upvote_ratio             | Upvote ratio (0–1). |
| num_comments             | Comment count. |
| total_awards_received    | Total awards. |
| created_utc              | Creation time (UTC). |
| edited_at                | Last edit time or NULL. |
| is_self, post_hint       | Text post vs link/image/video. |
| locked, archived         | Comments locked; thread archived. |
| stickied                 | Pinned in subreddit. |
| subreddit_subscribers    | Subscriber count at fetch time. |
| inserted_at, updated_at | ETL timestamps. |

### comments

| Column             | Meaning |
|--------------------|--------|
| comment_id         | Reddit comment id. Primary key. |
| post_id            | Post this comment belongs to. Foreign key to posts. |
| user_id            | Author. Foreign key to users. |
| parent_reddit_id   | Reddit parent_id (t3_xxx or t1_xxx). |
| parent_comment_id  | Parent comment's comment_id; NULL for top-level. |
| depth              | Nesting level: 0 = direct reply to post. |
| thread_path        | Array of IDs from post to this comment (for tree queries). |
| body               | Comment text. |
| score              | Net vote score. |
| created_utc        | Creation time (UTC). |
| edited_at          | Last edit or NULL. |
| stickied, removed  | Pinned in thread; removed. |
| inserted_at, updated_at | ETL timestamps. |

### engagement_snapshots

| Column       | Meaning |
|--------------|--------|
| snapshot_id  | Primary key (e.g. uuid or post_id + snapshot_at). |
| post_id      | Foreign key to posts. |
| snapshot_at  | When this snapshot was taken. |
| score        | Post score at snapshot time. |
| num_comments | Comment count at snapshot time. |
| upvote_ratio | Upvote ratio at snapshot time. |

---

## 4. Relationships

- **users ← posts:** \`posts.user_id\` → \`users.user_id\`
- **users ← comments:** \`comments.user_id\` → \`users.user_id\`
- **posts ← comments:** \`comments.post_id\` → \`posts.post_id\`
- **comments ← comments:** \`comments.parent_comment_id\` → \`comments.comment_id\` (nullable; only for replies)
- **posts ← engagement_snapshots:** \`engagement_snapshots.post_id\` → \`posts.post_id\`

\`meta.subreddits\` is standalone; it only lists schema names. It does not have foreign keys into per-subreddit tables.

---

## 5. Example SQL patterns

Posts with comment count (top 10 by comments):

\`\`\`sql
SELECT post_id, title, score, num_comments
FROM clickup.posts
ORDER BY num_comments DESC
LIMIT 10;
\`\`\`

Top-level comments only for a post:

\`\`\`sql
SELECT *
FROM clickup.comments
WHERE depth = 0 AND post_id = 'abc123';
\`\`\`

Replies to a specific comment:

\`\`\`sql
SELECT *
FROM clickup.comments
WHERE parent_comment_id = 'xyz789';
\`\`\`

Posts by author (by username):

\`\`\`sql
SELECT p.*
FROM clickup.posts p
JOIN clickup.users u ON p.user_id = u.user_id
WHERE u.username = 'some_redditor';
\`\`\`

Comment count per post:

\`\`\`sql
SELECT post_id, COUNT(*) AS comment_count
FROM clickup.comments
GROUP BY post_id;
\`\`\`

Engagement over time for a post (using snapshots):

\`\`\`sql
SELECT snapshot_at, score, num_comments, upvote_ratio
FROM clickup.engagement_snapshots
WHERE post_id = 'abc123'
ORDER BY snapshot_at;
\`\`\`

Most active commenters (by comment count):

\`\`\`sql
SELECT u.username, COUNT(*) AS comment_count
FROM clickup.comments c
JOIN clickup.users u ON c.user_id = u.user_id
GROUP BY u.user_id, u.username
ORDER BY comment_count DESC
LIMIT 20;
\`\`\`

---

## 6. DuckDB-specific notes

- **Schema-qualified names:** When multiple subreddit schemas exist, always qualify table names (e.g. \`clickup.posts\`, not \`posts\`) to avoid ambiguity.
- **thread_path:** Stored as a list type (e.g. \`VARCHAR[]\`). Use list functions or \`UNNEST(thread_path)\` for "comments under a given node" or depth filters. Example: filter comments whose thread_path contains a given comment_id.
- **Timestamps:** Stored as TIMESTAMP; use standard SQL date/time functions for filtering and grouping.
`;

/**
 * Returns the full semantic layer markdown for the AI SQL helper.
 * Use this as context when calling the AI to generate or refine SQL.
 *
 * @returns {string} Markdown describing tables, columns, relationships, and example SQL.
 */
function getSemanticLayerContext() {
  return SEMANTIC_LAYER_MARKDOWN;
}

// Export for ES modules (e.g. Vite, bundlers)
export { getSemanticLayerContext, SEMANTIC_LAYER_MARKDOWN };

// Export for CommonJS / Node
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { getSemanticLayerContext, SEMANTIC_LAYER_MARKDOWN };
}
