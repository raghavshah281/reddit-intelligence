"""Reddit JSON API client with rate limiting and retries."""

import logging
import time
from typing import Any, Optional

import requests

from .config import (
    REDDIT_BASE_URL,
    USER_AGENT,
    RATE_LIMIT_SECONDS,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
)

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": USER_AGENT}


def _request(url: str) -> Optional[dict]:
    """GET URL with retries and backoff. Returns JSON dict or None on failure."""
    last_error = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 429:
                logger.warning("Rate limited (429); backing off %s s", RETRY_BACKOFF_SECONDS)
                time.sleep(RETRY_BACKOFF_SECONDS)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            last_error = e
            logger.warning("Request failed (attempt %s): %s", attempt + 1, e)
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_SECONDS)
    logger.error("All retries failed for %s: %s", url, last_error)
    return None


def fetch_listing(url: str, after: Optional[str] = None) -> Optional[dict]:
    """Fetch a listing (e.g. subreddit new). Optional pagination with after=t3_xxx."""
    if after:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}after={after}"
    time.sleep(RATE_LIMIT_SECONDS)
    return _request(url)


def fetch_post_and_comments(subreddit: str, post_id: str) -> Optional[list]:
    """
    Fetch a single post and its full comment tree.
    Returns [post_listing, comments_listing] or None. Post is in [0].data.children[0].data.
    """
    url = f"{REDDIT_BASE_URL}/r/{subreddit}/comments/{post_id}/_/.json"
    time.sleep(RATE_LIMIT_SECONDS)
    data = _request(url)
    if not isinstance(data, list) or len(data) < 2:
        return None
    return data
