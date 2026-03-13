"""Reddit fetcher using a headless browser (Playwright) for human-like requests."""

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, List, Optional

from .config import (
    REDDIT_BASE_URL,
    BROWSER_DELAY_BETWEEN_REQUESTS_SECONDS,
    BROWSER_INITIAL_PAGE_WAIT_SECONDS,
    SUBREDDIT_NAME,
)

logger = logging.getLogger(__name__)


@contextmanager
def create_browser_fetcher(subreddit: str = SUBREDDIT_NAME):
    """
    Context manager that yields a fetcher with fetch_listing and fetch_post_and_comments.
    Uses headless Chromium with realistic viewport and locale; optionally loads
    the subreddit HTML first to set cookies, then fetches JSON via the same browser.
    """
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()

    try:
        # Optional: load subreddit HTML first so Reddit can set cookies
        try:
            page.goto(f"{REDDIT_BASE_URL}/r/{subreddit}/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(BROWSER_INITIAL_PAGE_WAIT_SECONDS)
        except Exception as e:
            logger.warning("Initial subreddit page load failed (continuing): %s", e)

        yield _BrowserFetcher(page)
    finally:
        context.close()
        browser.close()
        playwright.stop()


class _BrowserFetcher:
    """Fetches Reddit JSON via a Playwright page; same return shapes as reddit_client."""

    def __init__(self, page) -> None:
        self._page = page

    def fetch_listing(self, url: str, after: Optional[str] = None) -> Optional[dict]:
        """Fetch a listing (e.g. subreddit new). Optional pagination with after=t3_xxx."""
        if after:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}after={after}"
        time.sleep(BROWSER_DELAY_BETWEEN_REQUESTS_SECONDS)
        try:
            response = self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if not response or not response.ok:
                logger.warning("Listing request failed: %s", response.status if response else "no response")
                return None
            body = response.body()
            return json.loads(body.decode("utf-8"))
        except Exception as e:
            logger.warning("Listing fetch error: %s", e)
            return None

    def fetch_post_and_comments(self, subreddit: str, post_id: str) -> Optional[List[Any]]:
        """
        Fetch a single post and its full comment tree.
        Returns [post_listing, comments_listing] or None.
        """
        time.sleep(BROWSER_DELAY_BETWEEN_REQUESTS_SECONDS)
        url = f"{REDDIT_BASE_URL}/r/{subreddit}/comments/{post_id}/_/.json"
        try:
            response = self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if not response or not response.ok:
                logger.warning("Post/comments request failed: %s", response.status if response else "no response")
                return None
            body = response.body()
            data = json.loads(body.decode("utf-8"))
            if not isinstance(data, list) or len(data) < 2:
                return None
            return data
        except Exception as e:
            logger.warning("Post/comments fetch error: %s", e)
            return None
