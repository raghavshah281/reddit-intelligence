"""Configuration and constants for Reddit scraper."""

import os
from datetime import datetime, timezone, timedelta

# Reddit
REDDIT_BASE_URL = "https://www.reddit.com"
USER_AGENT = "Mozilla/5.0 (compatible; RedditIntelligence/1.0)"
RATE_LIMIT_SECONDS = 1.0
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5

# Reddit browser mode (headless Chromium)
BROWSER_DELAY_BETWEEN_REQUESTS_SECONDS = 2
BROWSER_INITIAL_PAGE_WAIT_SECONDS = 5

# Subreddit (initial)
SUBREDDIT_NAME = "clickup"
SCHEMA_NAME = "clickup"

# DB
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reddit.duckdb")

# Sentinel for [deleted] / missing author
DELETED_USER_ID = "t2_deleted"
DELETED_USERNAME = "[deleted]"

# AI SQL helper (web app backend). Set for Gemini 2.5 Flash; leave empty if not using AI features.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


# Refresh: stop tracking posts with no activity for N days (last activity = post or last comment/reply).
REFRESH_MAX_AGE_DAYS = 30


def get_cutoff_utc(days: int = 30) -> float:
    """Return Unix timestamp for (now - days). Use for filtering posts."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).timestamp()
