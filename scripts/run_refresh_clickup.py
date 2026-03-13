#!/usr/bin/env python3
"""
Refresh r/clickup: discover new posts and update existing posts' engagement and comment trees.
Runs on a schedule (e.g. every 24h via cron or GitHub Actions).
Usage: python scripts/run_refresh_clickup.py [--db data/reddit.duckdb] [--max-posts 100] [--use-browser]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DEFAULT_DB_PATH, REDDIT_BASE_URL, SCHEMA_NAME, SUBREDDIT_NAME
from src.db import (
    ensure_schema,
    ensure_sentinel_user,
    get_connection,
    update_subreddit_sync_time,
    upsert_comments,
    upsert_posts,
    upsert_users,
)
from src.parsers import (
    parse_comment_tree,
    parse_post_for_db,
    users_from_post,
)
from src.reddit_client import fetch_listing as fetch_listing_requests
from src.reddit_client import fetch_post_and_comments as fetch_post_and_comments_requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def _run_refresh(conn, listing_url: str, max_posts: int, fetch_listing_fn, fetch_post_and_comments_fn) -> int:
    """Run the refresh loop using the provided fetch functions. Returns 0 on success."""
    existing_ids = set(
        row[0] for row in conn.execute(f"SELECT post_id FROM {SCHEMA_NAME}.posts").fetchall()
    )
    logger.info("Loaded %s existing post IDs from DB", len(existing_ids))

    posts_to_process: list = []
    after = None
    listing_fetch_failed = False

    while len(posts_to_process) < max_posts:
        data = fetch_listing_fn(listing_url, after=after)
        if not data or "data" not in data:
            if not posts_to_process:
                listing_fetch_failed = True
            break
        children = (data.get("data") or {}).get("children") or []
        for child in children:
            if child.get("kind") != "t3":
                continue
            post = child.get("data") or {}
            post_id = (post.get("id") or "").strip()
            if post_id:
                posts_to_process.append(post)
                if len(posts_to_process) >= max_posts:
                    break
        if len(posts_to_process) >= max_posts:
            break
        after = (data.get("data") or {}).get("after")
        if not after:
            break

    if listing_fetch_failed:
        logger.error("Reddit listing fetch failed (e.g. 403 Blocked). No updates obtained; workflow must fail.")
        return 1

    logger.info("Fetched %s posts from listing (max %s)", len(posts_to_process), max_posts)

    subreddit_subscribers = None
    total_users = 0
    total_posts = 0
    total_comments = 0
    new_posts = 0
    refreshed_posts = 0

    for i, post_data in enumerate(posts_to_process):
        post_id = (post_data.get("id") or "").strip()
        if not post_id:
            continue
        is_new = post_id not in existing_ids
        if is_new:
            new_posts += 1
            logger.info("New post: %s", post_id)
        else:
            refreshed_posts += 1

        if subreddit_subscribers is None:
            subreddit_subscribers = post_data.get("subreddit_subscribers")

        thread = fetch_post_and_comments_fn(SUBREDDIT_NAME, post_id)
        if not thread or len(thread) < 2:
            logger.warning("No thread data for post %s", post_id)
            post_row = parse_post_for_db(post_data, subreddit_subscribers)
            user_rows = users_from_post(post_data)
            upsert_users(conn, user_rows)
            upsert_posts(conn, [post_row])
            total_posts += 1
            total_users += len(user_rows)
            continue

        post_listing, comments_listing = thread[0], thread[1]
        post_in_thread = None
        for c in (post_listing.get("data") or {}).get("children") or []:
            if c.get("kind") == "t3":
                post_in_thread = c.get("data") or post_data
                break
        if not post_in_thread:
            post_in_thread = post_data

        post_row = parse_post_for_db(post_in_thread, subreddit_subscribers)
        user_rows = users_from_post(post_in_thread)
        comment_users, comment_rows = parse_comment_tree(comments_listing, post_id)
        seen = {u["user_id"] for u in user_rows}
        for u in comment_users:
            if u["user_id"] not in seen:
                seen.add(u["user_id"])
                user_rows.append(u)

        upsert_users(conn, user_rows)
        upsert_posts(conn, [post_row])
        upsert_comments(conn, comment_rows)

        total_users += len(user_rows)
        total_posts += 1
        total_comments += len(comment_rows)

        if (i + 1) % 10 == 0:
            logger.info("Progress: %s/%s posts", i + 1, len(posts_to_process))

    update_subreddit_sync_time(conn, SCHEMA_NAME, "t5_clickup")

    logger.info(
        "Done. New: %s, Refreshed: %s. Users: %s, Posts: %s, Comments: %s",
        new_posts, refreshed_posts, total_users, total_posts, total_comments,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh r/clickup: new posts + update engagement and comments")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to DuckDB file")
    parser.add_argument("--max-posts", type=int, default=100, help="Max number of posts to refresh (from /new)")
    parser.add_argument(
        "--use-browser",
        action="store_true",
        help="Use headless browser for Reddit (recommended in CI); else use requests",
    )
    args = parser.parse_args()

    use_browser = args.use_browser or os.environ.get("REDDIT_USE_BROWSER", "").strip().lower() in ("1", "true", "yes")

    conn = get_connection(args.db)
    ensure_schema(conn)
    ensure_sentinel_user(conn)

    listing_url = f"{REDDIT_BASE_URL}/r/{SUBREDDIT_NAME}/new.json?limit=100"

    if use_browser:
        from src.reddit_browser import create_browser_fetcher

        with create_browser_fetcher(SUBREDDIT_NAME) as fetcher:
            code = _run_refresh(
                conn,
                listing_url,
                args.max_posts,
                fetcher.fetch_listing,
                fetcher.fetch_post_and_comments,
            )
    else:
        code = _run_refresh(
            conn,
            listing_url,
            args.max_posts,
            fetch_listing_requests,
            fetch_post_and_comments_requests,
        )

    conn.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
