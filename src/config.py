"""Configuration and constants for Reddit scraper."""

import os
from datetime import datetime, timezone, timedelta

# Reddit
REDDIT_BASE_URL = "https://www.reddit.com"
USER_AGENT = "Mozilla/5.0 (compatible; RedditIntelligence/1.0)"
RATE_LIMIT_SECONDS = 1.0
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5

# Subreddit (initial)
SUBREDDIT_NAME = "clickup"
SCHEMA_NAME = "clickup"

# DB
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reddit.duckdb")

# Sentinel for [deleted] / missing author
DELETED_USER_ID = "t2_deleted"
DELETED_USERNAME = "[deleted]"


def get_cutoff_utc(days: int = 30) -> float:
    """Return Unix timestamp for (now - days). Use for filtering posts."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
