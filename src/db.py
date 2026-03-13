"""DuckDB connection, schema init, and upserts for clickup schema."""

import logging
import os
from pathlib import Path

import duckdb

from .config import DEFAULT_DB_PATH, DELETED_USER_ID, DELETED_USERNAME, SCHEMA_NAME

logger = logging.getLogger(__name__)

# Project root: parent of src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = PROJECT_ROOT / "scripts" / "schema"


def get_connection(db_path: str | None = None):
    """Open DuckDB connection. Create DB file and directory if needed."""
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    return duckdb.connect(path)


def ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Run schema DDL files if they exist (01, 02, 03). Idempotent."""
    for name in ("01_subreddits.sql", "02_users_posts_comments.sql", "03_snapshots.sql"):
        p = SCHEMA_DIR / name
        if not p.exists():
            continue
        sql = p.read_text()
        try:
            conn.execute(sql)
            logger.info("Executed schema script: %s", name)
        except Exception as e:
            logger.warning("Schema script %s: %s", name, e)


def ensure_sentinel_user(conn: duckdb.DuckDBPyConnection) -> None:
    """Insert [deleted] user if not present."""
    conn.execute(
        """
        INSERT INTO clickup.users (user_id, username)
        VALUES (?, ?)
        ON CONFLICT (user_id) DO NOTHING
        """,
        [DELETED_USER_ID, DELETED_USERNAME],
    )


def upsert_users(conn: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    """Upsert user rows into clickup.users. Uses ON CONFLICT DO UPDATE."""
    if not rows:
        return
    for r in rows:
        conn.execute(
            """
            INSERT INTO clickup.users (user_id, username, is_premium, flair_text, first_seen_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?::TIMESTAMP, ?::TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                username = excluded.username,
                is_premium = excluded.is_premium,
                flair_text = excluded.flair_text,
                last_seen_at = now()
            """,
            [
                r.get("user_id"),
                r.get("username") or "",
                r.get("is_premium"),
                r.get("flair_text"),
                r.get("first_seen_at"),
                r.get("last_seen_at"),
            ],
        )
    logger.debug("Upserted %s users", len(rows))


# Engagement columns for posts: only these are updated when row exists (avoids FK delete+insert).
POST_ENGAGEMENT_COLUMNS = (
    "score", "ups", "downs", "upvote_ratio", "num_comments", "subreddit_subscribers"
)


def upsert_posts(conn: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    """Upsert post rows. New posts: full INSERT. Existing: only update engagement columns if changed (no full row replace, avoids FK violation)."""
    if not rows:
        return
    for r in rows:
        post_id = r.get("post_id")
        existing = conn.execute(
            "SELECT 1 FROM clickup.posts WHERE post_id = ?", [post_id]
        ).fetchone()
        if existing:
            # Fetch current engagement values to compare
            cur = conn.execute(
                "SELECT score, ups, downs, upvote_ratio, num_comments, subreddit_subscribers FROM clickup.posts WHERE post_id = ?",
                [post_id],
            ).fetchone()
            if cur is None:
                continue
            (cur_score, cur_ups, cur_downs, cur_ratio, cur_num_comments, cur_subs) = cur
            new_score = r.get("score")
            new_ups = r.get("ups")
            new_downs = r.get("downs")
            new_ratio = r.get("upvote_ratio")
            new_num_comments = r.get("num_comments")
            new_subs = r.get("subreddit_subscribers")
            if (
                new_score != cur_score
                or new_ups != cur_ups
                or new_downs != cur_downs
                or new_ratio != cur_ratio
                or new_num_comments != cur_num_comments
                or new_subs != cur_subs
            ):
                conn.execute(
                    """
                    UPDATE clickup.posts SET
                        score = ?, ups = ?, downs = ?, upvote_ratio = ?, num_comments = ?, subreddit_subscribers = ?, updated_at = now()
                    WHERE post_id = ?
                    """,
                    [new_score, new_ups, new_downs, new_ratio, new_num_comments, new_subs, post_id],
                )
            # else: leave row as-is
        else:
            conn.execute(
                """
                INSERT INTO clickup.posts (post_id, user_id, title, selftext, selftext_html, permalink, url, domain,
                    score, ups, downs, upvote_ratio, num_comments, num_crossposts, total_awards_received,
                    created_utc, edited_at, is_self, post_hint, is_video, over_18, spoiler, locked, archived, stickied,
                    subreddit_subscribers, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?,
                    ?::TIMESTAMP, ?::TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, now())
                """,
                [
                    post_id,
                    r.get("user_id"),
                    r.get("title"),
                    r.get("selftext"),
                    r.get("selftext_html"),
                    r.get("permalink"),
                    r.get("url"),
                    r.get("domain"),
                    r.get("score"),
                    r.get("ups"),
                    r.get("downs"),
                    r.get("upvote_ratio"),
                    r.get("num_comments"),
                    r.get("num_crossposts"),
                    r.get("total_awards_received"),
                    r.get("created_utc"),
                    r.get("edited_at"),
                    r.get("is_self"),
                    r.get("post_hint"),
                    r.get("is_video"),
                    r.get("over_18"),
                    r.get("spoiler"),
                    r.get("locked"),
                    r.get("archived"),
                    r.get("stickied"),
                    r.get("subreddit_subscribers"),
                ],
            )
    logger.debug("Upserted %s posts", len(rows))


# Mutable columns for comments: only these are updated when row exists (avoids FK delete+insert).
COMMENT_MUTABLE_COLUMNS = (
    "body", "body_html", "score", "ups", "downs", "total_awards_received",
    "controversiality", "edited_at", "score_hidden", "stickied", "removed", "locked",
)


def _comment_values_match(cur: tuple, r: dict) -> bool:
    """Compare current DB row with incoming row for mutable comment fields."""
    (
        cur_body, cur_body_html, cur_score, cur_ups, cur_downs,
        cur_awards, cur_controv, cur_edited, cur_hidden, cur_stickied, cur_removed, cur_locked,
    ) = cur
    return (
        (cur_body == r.get("body"))
        and (cur_body_html == r.get("body_html"))
        and (cur_score == r.get("score"))
        and (cur_ups == r.get("ups"))
        and (cur_downs == r.get("downs"))
        and (cur_awards == r.get("total_awards_received"))
        and (cur_controv == r.get("controversiality"))
        and (cur_edited == r.get("edited_at"))
        and (cur_hidden == r.get("score_hidden"))
        and (cur_stickied == r.get("stickied"))
        and (cur_removed == r.get("removed"))
        and (cur_locked == r.get("locked"))
    )


def upsert_comments(conn: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    """Upsert comment rows. New comments: full INSERT. Existing: only update mutable columns if changed (no full row replace, avoids FK violation)."""
    if not rows:
        return
    for r in rows:
        comment_id = r.get("comment_id")
        existing = conn.execute(
            "SELECT 1 FROM clickup.comments WHERE comment_id = ?", [comment_id]
        ).fetchone()
        if existing:
            cur = conn.execute(
                """SELECT body, body_html, score, ups, downs, total_awards_received, controversiality,
                           edited_at, score_hidden, stickied, removed, locked FROM clickup.comments WHERE comment_id = ?""",
                [comment_id],
            ).fetchone()
            if cur is not None and _comment_values_match(cur, r):
                continue  # leave as-is
            if cur is not None:
                conn.execute(
                    """
                    UPDATE clickup.comments SET
                        body = ?, body_html = ?, score = ?, ups = ?, downs = ?,
                        total_awards_received = ?, controversiality = ?, edited_at = ?::TIMESTAMP,
                        score_hidden = ?, stickied = ?, removed = ?, locked = ?, updated_at = now()
                    WHERE comment_id = ?
                    """,
                    [
                        r.get("body"),
                        r.get("body_html"),
                        r.get("score"),
                        r.get("ups"),
                        r.get("downs"),
                        r.get("total_awards_received"),
                        r.get("controversiality"),
                        r.get("edited_at"),
                        r.get("score_hidden"),
                        r.get("stickied"),
                        r.get("removed"),
                        r.get("locked"),
                        comment_id,
                    ],
                )
        else:
            thread_path = r.get("thread_path") or []
            if thread_path:
                list_placeholders = ", ".join("?" for _ in thread_path)
                list_sql = f"LIST_VALUE({list_placeholders})"
            else:
                list_sql = "NULL"
            conn.execute(
                f"""
                INSERT INTO clickup.comments (
                    comment_id, post_id, user_id, parent_reddit_id, parent_comment_id, depth, thread_path,
                    body, body_html, score, ups, downs, total_awards_received, controversiality,
                    created_utc, edited_at, score_hidden, stickied, removed, locked, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, {list_sql}, ?, ?, ?, ?, ?, ?, ?, ?::TIMESTAMP, ?::TIMESTAMP, ?, ?, ?, ?, now())
                """,
                [
                    comment_id,
                    r.get("post_id"),
                    r.get("user_id"),
                    r.get("parent_reddit_id"),
                    r.get("parent_comment_id"),
                    r.get("depth"),
                    *thread_path,
                    r.get("body"),
                    r.get("body_html"),
                    r.get("score"),
                    r.get("ups"),
                    r.get("downs"),
                    r.get("total_awards_received"),
                    r.get("controversiality"),
                    r.get("created_utc"),
                    r.get("edited_at"),
                    r.get("score_hidden"),
                    r.get("stickied"),
                    r.get("removed"),
                    r.get("locked"),
                ],
            )
    logger.debug("Upserted %s comments", len(rows))


def update_subreddit_sync_time(conn: duckdb.DuckDBPyConnection, schema_name: str, subreddit_id: str | None = None) -> None:
    """Set meta.subreddits.last_synced_at for the given schema. Upsert row if subreddit_id provided."""
    if subreddit_id:
        conn.execute(
            """
            INSERT INTO meta.subreddits (subreddit_id, name, display_name, schema_name, last_synced_at, updated_at)
            VALUES (?, ?, ?, ?, now(), now())
            ON CONFLICT (subreddit_id) DO UPDATE SET last_synced_at = now(), updated_at = now()
            """,
            [subreddit_id, schema_name, schema_name.capitalize(), schema_name],
        )
    else:
        conn.execute(
            "UPDATE meta.subreddits SET last_synced_at = now(), updated_at = now() WHERE schema_name = ?",
            [schema_name],
        )
