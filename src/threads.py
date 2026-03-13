"""Stage 1: Reconstruct Reddit conversation trees from DuckDB."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    DEFAULT_DB_PATH,
    PROJECT_ROOT,
    REDDIT_BASE_URL,
    SCHEMA_NAME,
    get_cutoff_utc,
)
from .db import get_connection
from .pp_models import ReconstructedThread, ThreadMessage

logger = logging.getLogger(__name__)


def _comment_permalink(post_permalink: str | None, comment_id: str) -> str:
    """Build Reddit permalink for a comment (post permalink + comment_id)."""
    if not post_permalink or not comment_id:
        return ""
    base = REDDIT_BASE_URL.rstrip("/")
    path = post_permalink if post_permalink.startswith("/") else "/" + post_permalink
    path = path.rstrip("/")
    return f"{base}{path}/{comment_id}/"


def _row_to_message(
    *,
    id_: str,
    author_id: str,
    author_username: str,
    created_utc: str | None,
    body: str | None,
    score: int | None,
    ups: int | None,
    downs: int | None,
    upvote_ratio: float | None,
    permalink: str | None,
    depth: int,
) -> ThreadMessage:
    return ThreadMessage(
        id=id_,
        author_id=author_id or "",
        author_username=author_username or "[deleted]",
        created_utc=created_utc,
        body=(body or "").strip() or None,
        score=score,
        ups=ups,
        downs=downs,
        upvote_ratio=upvote_ratio,
        permalink=permalink or None,
        depth=depth,
        replies=[],
    )


def _build_tree(
    post_row: dict,
    post_author: str,
    comment_rows: list[dict],
    comment_authors: dict[str, str],
) -> ReconstructedThread:
    """Build a single thread: root post + comment tree."""
    post_id = post_row["post_id"]
    permalink = post_row.get("permalink")
    full_permalink = f"{REDDIT_BASE_URL.rstrip('/')}{permalink}" if permalink and str(permalink).startswith("/") else (permalink or "")

    root = _row_to_message(
        id_=post_id,
        author_id=post_row.get("user_id") or "",
        author_username=post_author,
        created_utc=str(post_row["created_utc"]) if post_row.get("created_utc") else None,
        body=post_row.get("selftext") or None,
        score=post_row.get("score"),
        ups=post_row.get("ups"),
        downs=post_row.get("downs"),
        upvote_ratio=post_row.get("upvote_ratio"),
        permalink=full_permalink,
        depth=0,
    )

    # Map comment_id -> ThreadMessage
    by_id: dict[str, ThreadMessage] = {post_id: root}
    for c in comment_rows:
        cid = c.get("comment_id")
        if not cid:
            continue
        post_pl = permalink
        msg = _row_to_message(
            id_=cid,
            author_id=c.get("user_id") or "",
            author_username=comment_authors.get(cid, "[deleted]"),
            created_utc=str(c["created_utc"]) if c.get("created_utc") else None,
            body=c.get("body"),
            score=c.get("score"),
            ups=c.get("ups"),
            downs=c.get("downs"),
            upvote_ratio=None,
            permalink=_comment_permalink(post_pl, cid) if post_pl else None,
            depth=c.get("depth", 0),
        )
        by_id[cid] = msg

    # Attach each comment to its parent
    for c in comment_rows:
        cid = c.get("comment_id")
        parent_id = c.get("parent_comment_id")
        if not cid or cid not in by_id:
            continue
        node = by_id[cid]
        parent = by_id.get(parent_id) if parent_id else root
        if parent:
            parent.replies.append(node)

    # Sort replies by created_utc at each level for stable order
    def sort_replies(m: ThreadMessage) -> None:
        m.replies.sort(key=lambda r: r.created_utc or "")
        for r in m.replies:
            sort_replies(r)

    sort_replies(root)

    return ReconstructedThread(
        post_id=post_id,
        root=root,
        title=(post_row.get("title") or "").strip(),
        permalink=full_permalink or None,
    )


def load_threads_from_db(
    db_path: str | None = None,
    max_age_days: int | None = 30,
    limit_posts: int | None = None,
) -> list[ReconstructedThread]:
    """
    Load all posts (optionally filtered by recent activity) and their comments;
    build a ReconstructedThread per post.
    """
    conn = get_connection(db_path)
    schema = SCHEMA_NAME

    # Optional time filter: posts with created_utc in last max_age_days
    params: list = []
    if max_age_days is not None:
        cutoff_ts = datetime.fromtimestamp(get_cutoff_utc(max_age_days), tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        cutoff_clause = "AND p.created_utc >= ?"
        params.append(cutoff_ts)
    else:
        cutoff_clause = ""

    limit_clause = f"LIMIT {int(limit_posts)}" if limit_posts else ""
    posts_sql = f"""
        SELECT p.post_id, p.user_id, p.title, p.selftext, p.permalink,
               p.score, p.ups, p.downs, p.upvote_ratio, p.num_comments, p.created_utc
        FROM {schema}.posts p
        WHERE 1=1 {cutoff_clause}
        ORDER BY p.created_utc DESC
        {limit_clause}
    """
    posts = conn.execute(posts_sql, params).fetchall()
    columns_post = [d[0] for d in conn.description]
    post_rows = [dict(zip(columns_post, row)) for row in posts]

    threads: list[ReconstructedThread] = []
    for pr in post_rows:
        post_id = pr["post_id"]
        post_author_row = conn.execute(
            f"SELECT username FROM {schema}.users WHERE user_id = ?",
            [pr["user_id"]],
        ).fetchone()
        post_author = post_author_row[0] if post_author_row else "[deleted]"

        comments_sql = f"""
            SELECT c.comment_id, c.post_id, c.user_id, c.parent_comment_id, c.depth,
                   c.body, c.score, c.ups, c.downs, c.created_utc
            FROM {schema}.comments c
            WHERE c.post_id = ?
            ORDER BY c.depth, c.created_utc
        """
        comment_rows_raw = conn.execute(comments_sql, [post_id]).fetchall()
        columns_c = [d[0] for d in conn.description]
        comment_rows = [dict(zip(columns_c, r)) for r in comment_rows_raw]

        user_ids = {r["user_id"] for r in comment_rows}
        comment_authors: dict[str, str] = {}
        if user_ids:
            placeholders = ",".join("?" for _ in user_ids)
            users = conn.execute(
                f"SELECT user_id, username FROM {schema}.users WHERE user_id IN ({placeholders})",
                list(user_ids),
            ).fetchall()
            for uid, uname in users:
                comment_authors[str(uid)] = uname or "[deleted]"

        thread = _build_tree(pr, post_author, comment_rows, comment_authors)
        threads.append(thread)

    conn.close()
    logger.info("Reconstructed %s threads from DB", len(threads))
    return threads


def thread_to_serializable(thread: ReconstructedThread) -> dict:
    """Convert a ReconstructedThread to a JSON-serializable dict."""

    def msg_to_dict(m: ThreadMessage) -> dict:
        return {
            "id": m.id,
            "author_id": m.author_id,
            "author_username": m.author_username,
            "created_utc": m.created_utc,
            "body": m.body,
            "score": m.score,
            "ups": m.ups,
            "downs": m.downs,
            "upvote_ratio": m.upvote_ratio,
            "permalink": m.permalink,
            "depth": m.depth,
            "replies": [msg_to_dict(r) for r in m.replies],
        }

    return {
        "post_id": thread.post_id,
        "title": thread.title,
        "permalink": thread.permalink,
        "root": msg_to_dict(thread.root),
    }


def save_threads_json(threads: list[ReconstructedThread], out_path: str | Path) -> None:
    """Write reconstructed threads to a JSON file."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [thread_to_serializable(t) for t in threads]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Wrote %s threads to %s", len(data), path)


def load_threads_json(path: str | Path) -> list[dict]:
    """Load threads from JSON (for pipeline stages that read intermediate output)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
