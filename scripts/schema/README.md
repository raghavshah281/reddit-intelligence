# Schema DDL (DuckDB)

Run in order against your DuckDB database:

1. **01_subreddits.sql** — Creates `meta` schema and `meta.subreddits` (global registry).
2. **02_users_posts_comments.sql** — Creates `clickup` schema with `users`, `posts`, `comments`.
3. **03_snapshots.sql** — Creates `clickup.engagement_snapshots` for weekly engagement history.

After running, insert r/clickup into the registry, e.g.:

```sql
INSERT INTO meta.subreddits (subreddit_id, name, display_name, schema_name)
VALUES ('t5_2qizd', 'clickup', 'ClickUp', 'clickup');
```

(Use the real `subreddit_id` from Reddit when you have it.)

**Scraper:** The Python scraper creates/updates the schema automatically. Run `python scripts/run_scrape_clickup_30d.py --db data/reddit.duckdb` from the project root to scrape the last 30 days of r/clickup into DuckDB.
