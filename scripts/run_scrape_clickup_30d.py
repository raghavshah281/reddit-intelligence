#!/usr/bin/env python3
"""
Scrape r/clickup for the last N days and upsert into DuckDB.
Usage: python scripts/run_scrape_clickup_30d.py [--db data/reddit.duckdb] [--days 30] [--dry-run]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (
    DEFAULT_DB_PATH,
    REDDIT_BASE_URL,
    get_cutoff_utc,
    SCHEMA_NAME,
    SUBREDDIT_NAME,
)
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
    parse_listing_for_posts,
    parse_post_for_db,
    users_from_post,
)
from src.reddit_client import fetch_listing, fetch_post_and_comments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape r/clickup (last N days) into DuckDB")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to DuckDB file")
    parser.add_argument("--days", type=int, default=30, help="Number of days to scrape")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse only; no DB writes")
    args = parser.parse_args()

    cutoff = get_cutoff_utc(args.days)
    logger.info("Cutoff: last %s days (created_utc >= %s)", args.days, cutoff)

    # Collect all posts in range (paginate /new)
    listing_url = f"{REDDIT_BASE_URL}/r/{SUBREDDIT_NAME}/new.json?limit=100"
    posts_in_range: list = []
    after = None
    while True:
        data = fetch_listing(listing_url, after=after)
        if not data or "data" not in data:
            break
        posts = parse_listing_for_posts(data, cutoff)
        if not posts:
            # No posts in range on this page (all older than cutoff) -> stop
            break
        posts_in_range.extend(posts)
        after = (data.get("data") or {}).get("after")
        if not after:
            break

    logger.info("Fetched %s posts in range (last %s days)", len(posts_in_range), args.days)

    if args.dry_run:
        logger.info("Dry run: skipping DB writes")
        return 0

    conn = get_connection(args.db)
    ensure_schema(conn)
    ensure_sentinel_user(conn)

    subreddit_subscribers = None
    total_users = 0
    total_posts = 0
    total_comments = 0

    for i, post_data in enumerate(posts_in_range):
        post_id = (post_data.get("id") or "").strip()
        if not post_id:
            continue
        if subreddit_subscribers is None:
            subreddit_subscribers = post_data.get("subreddit_subscribers")

        # Fetch full post + comment tree
        thread = fetch_post_and_comments(SUBREDDIT_NAME, post_id)
        if not thread or len(thread) < 2:
            logger.warning("No thread data for post %s", post_id)
            # Still upsert post from listing data
            post_row = parse_post_for_db(post_data, subreddit_subscribers)
            user_rows = users_from_post(post_data)
            upsert_users(conn, user_rows)
            upsert_posts(conn, [post_row])
            total_posts += 1
            total_users += len(user_rows)
            continue

        post_listing, comments_listing = thread[0], thread[1]
        # Post can be in first listing's first child
        post_in_thread = None
        children0 = (post_listing.get("data") or {}).get("children") or []
        for c in children0:
            if c.get("kind") == "t3":
                post_in_thread = c.get("data") or post_data
                break
        if not post_in_thread:
            post_in_thread = post_data

        post_row = parse_post_for_db(post_in_thread, subreddit_subscribers)
        user_rows = users_from_post(post_in_thread)
        comment_users, comment_rows = parse_comment_tree(comments_listing, post_id)
        # Dedupe users: post author + comment authors
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
            logger.info("Progress: %s/%s posts", i + 1, len(posts_in_range))

    # Update sync time (upsert meta.subreddits row for clickup)
    update_subreddit_sync_time(conn, SCHEMA_NAME, "t5_clickup")

    conn.close()
    logger.info("Done. Users: %s, Posts: %s, Comments: %s", total_users, total_posts, total_comments)
    return 0


if __name__ == "__main__":
    sys.exit(main())
