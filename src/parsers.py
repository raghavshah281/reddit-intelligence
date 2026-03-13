"""Parse Reddit JSON into DB row structures for users, posts, and comments."""

from datetime import datetime, timezone
from typing import Any, Iterator

from .config import DELETED_USER_ID, DELETED_USERNAME


def _ts(utc_ts: Any) -> str | None:
    """Convert Reddit created_utc or edited to ISO timestamp for DuckDB."""
    if utc_ts is None or utc_ts is False:
        return None
    try:
        t = float(utc_ts)
        return datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def _int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _bool(val: Any) -> bool:
    return bool(val)


def _str(val: Any) -> str | None:
    if val is None:
        return None
    return str(val).strip() or None


def parse_listing_for_posts(listing_data: dict, cutoff_utc: float) -> list[dict]:
    """
    From a listing response (data = listing_data), extract post dicts
    where kind=='t3' and created_utc >= cutoff_utc.
    """
    posts = []
    data = listing_data.get("data") or {}
    children = data.get("children") or []
    for child in children:
        if child.get("kind") != "t3":
            continue
        post = child.get("data") or {}
        created = post.get("created_utc")
        if created is not None and float(created) < cutoff_utc:
            continue
        posts.append(post)
    return posts


def user_row_from_author(author: Any, author_fullname: Any, is_premium: Any = None, flair_text: Any = None) -> dict:
    """Build one users table row. Use DELETED_* when author_fullname is missing."""
    if author_fullname and str(author_fullname).strip():
        user_id = str(author_fullname).strip()
        username = _str(author) or "[unknown]"
    else:
        user_id = DELETED_USER_ID
        username = DELETED_USERNAME
    return {
        "user_id": user_id,
        "username": username,
        "is_premium": _bool(is_premium) if is_premium is not None else None,
        "flair_text": _str(flair_text),
        "first_seen_at": None,
        "last_seen_at": None,
    }


def parse_post_for_db(post_data: dict, subreddit_subscribers: int | None = None) -> dict:
    """Build one clickup.posts row from Reddit post data."""
    post_id = _str(post_data.get("id")) or ""
    author_fullname = post_data.get("author_fullname")
    author = post_data.get("author")
    if not author_fullname or not str(author_fullname).strip():
        user_id = DELETED_USER_ID
    else:
        user_id = str(author_fullname).strip()

    edited = post_data.get("edited")
    if edited is True or (isinstance(edited, (int, float)) and edited):
        edited_at = _ts(edited if isinstance(edited, (int, float)) else post_data.get("created_utc"))
    else:
        edited_at = None

    return {
        "post_id": post_id,
        "user_id": user_id,
        "title": _str(post_data.get("title")) or "",
        "selftext": _str(post_data.get("selftext")),
        "selftext_html": _str(post_data.get("selftext_html")),
        "permalink": _str(post_data.get("permalink")),
        "url": _str(post_data.get("url")),
        "domain": _str(post_data.get("domain")),
        "score": _int(post_data.get("score")),
        "ups": _int(post_data.get("ups")),
        "downs": _int(post_data.get("downs")),
        "upvote_ratio": _float(post_data.get("upvote_ratio")),
        "num_comments": _int(post_data.get("num_comments")),
        "num_crossposts": _int(post_data.get("num_crossposts")),
        "total_awards_received": _int(post_data.get("total_awards_received")),
        "created_utc": _ts(post_data.get("created_utc")),
        "edited_at": edited_at,
        "is_self": _bool(post_data.get("is_self")),
        "post_hint": _str(post_data.get("post_hint")),
        "is_video": _bool(post_data.get("is_video")),
        "over_18": _bool(post_data.get("over_18")),
        "spoiler": _bool(post_data.get("spoiler")),
        "locked": _bool(post_data.get("locked")),
        "archived": _bool(post_data.get("archived")),
        "stickied": _bool(post_data.get("stickied")),
        "subreddit_subscribers": _int(subreddit_subscribers) if subreddit_subscribers is not None else _int(post_data.get("subreddit_subscribers")),
    }


def _walk_comments(
    children: list,
    post_id: str,
    parent_reddit_id: str,
    parent_comment_id: str | None,
    depth: int,
    path: list[str],
) -> Iterator[tuple[dict, dict]]:
    """Yield (user_row, comment_row) for each comment. path = thread_path (list of comment ids from root)."""
    for child in children:
        if child.get("kind") != "t1":
            continue
        data = child.get("data") or {}
        comment_id = _str(data.get("id")) or ""
        if not comment_id:
            continue

        author_fullname = data.get("author_fullname")
        author = data.get("author")
        if not author_fullname or not str(author_fullname).strip():
            user_id = DELETED_USER_ID
        else:
            user_id = str(author_fullname).strip()

        user_row = user_row_from_author(
            author,
            author_fullname,
            data.get("author_premium"),
            data.get("author_flair_text"),
        )

        edited = data.get("edited")
        if edited is True or (isinstance(edited, (int, float)) and edited):
            edited_at = _ts(edited if isinstance(edited, (int, float)) else data.get("created_utc"))
        else:
            edited_at = None

        thread_path = list(path) + [comment_id]

        comment_row = {
            "comment_id": comment_id,
            "post_id": post_id,
            "user_id": user_id,
            "parent_reddit_id": _str(data.get("parent_id")) or parent_reddit_id,
            "parent_comment_id": parent_comment_id,
            "depth": depth,
            "thread_path": thread_path,
            "body": _str(data.get("body")),
            "body_html": _str(data.get("body_html")),
            "score": _int(data.get("score")),
            "ups": _int(data.get("ups")),
            "downs": _int(data.get("downs")),
            "total_awards_received": _int(data.get("total_awards_received")),
            "controversiality": _int(data.get("controversiality")),
            "created_utc": _ts(data.get("created_utc")),
            "edited_at": edited_at,
            "score_hidden": _bool(data.get("score_hidden")),
            "stickied": _bool(data.get("stickied")),
            "removed": _bool(data.get("removed")),
            "locked": _bool(data.get("locked")),
        }

        yield user_row, comment_row

        replies = data.get("replies") or ""
        if isinstance(replies, dict):
            reply_data = replies.get("data") or {}
            reply_children = reply_data.get("children") or []
            for u, c in _walk_comments(
                reply_children,
                post_id,
                f"t1_{comment_id}",
                comment_id,
                depth + 1,
                thread_path,
            ):
                yield u, c


def parse_comment_tree(comments_listing: dict, post_id: str) -> tuple[list[dict], list[dict]]:
    """
    Walk the comments listing (second element of thread JSON). Return (list of user rows, list of comment rows).
    Comment rows have thread_path as list of strings; parent_comment_id set for replies.
    """
    users = []
    comments = []
    seen_users = set()
    data = comments_listing.get("data") or {}
    children = data.get("children") or []
    for user_row, comment_row in _walk_comments(children, post_id, f"t3_{post_id}", None, 0, []):
        if user_row["user_id"] not in seen_users:
            seen_users.add(user_row["user_id"])
            users.append(user_row)
        comments.append(comment_row)
    return users, comments


def users_from_post(post_data: dict) -> list[dict]:
    """Extract one user row from post (for post author)."""
    author = post_data.get("author")
    author_fullname = post_data.get("author_fullname")
    if not author_fullname or not str(author_fullname).strip():
        return [user_row_from_author(None, None)]  # sentinel
    return [
        user_row_from_author(
            author,
            author_fullname,
            post_data.get("author_premium"),
            post_data.get("author_flair_text"),
        )
    ]
