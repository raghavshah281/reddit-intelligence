"""Stage 5: Engagement metrics from DuckDB per cluster/thread."""

import logging

from .db import get_connection
from .pp_models import IssueCluster

logger = logging.getLogger(__name__)

SCHEMA = "clickup"


def compute_engagement_for_cluster(
    conn,
    cluster: IssueCluster,
) -> None:
    """
    Compute total_participants, total_mentions, engagement_score, first/last seen
    from DuckDB for this cluster. Mutates cluster in place.
    """
    post_id = cluster.post_id
    message_ids = cluster.message_ids
    if not message_ids:
        cluster.total_mentions = 0
        cluster.total_participants = 0
        cluster.engagement_score = 0.0
        return

    placeholders = ",".join("?" for _ in message_ids)
    # Comment scores and distinct users
    row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS cnt,
            COALESCE(SUM(score), 0) AS total_score,
            COUNT(DISTINCT user_id) AS distinct_users
        FROM {SCHEMA}.comments
        WHERE post_id = ? AND comment_id IN ({placeholders})
        """,
        [post_id] + list(message_ids),
    ).fetchone()

    if row:
        cnt, total_score, distinct_users = row
        cluster.total_mentions = int(cnt or 0)
        cluster.total_participants = int(distinct_users or 0)
        comment_score = int(total_score or 0)
    else:
        cluster.total_mentions = len(message_ids)
        cluster.total_participants = len(set(m.get("author_username") for m in cluster.messages))
        comment_score = 0

    # Post score for this thread
    post_row = conn.execute(
        f"SELECT score, num_comments FROM {SCHEMA}.posts WHERE post_id = ?",
        [post_id],
    ).fetchone()
    post_score = int(post_row[0] or 0) if post_row else 0

    # Engagement score: post score + sum of comment scores (simple)
    cluster.engagement_score = float(post_score + comment_score)

    # First/last from DB if we have comment timestamps
    time_row = conn.execute(
        f"""
        SELECT MIN(created_utc), MAX(created_utc)
        FROM {SCHEMA}.comments
        WHERE post_id = ? AND comment_id IN ({placeholders})
        """,
        [post_id] + list(message_ids),
    ).fetchone()
    if time_row and time_row[0] and time_row[1]:
        cluster.first_seen_utc = str(time_row[0])
        cluster.last_seen_utc = str(time_row[1])


def compute_engagement_for_clusters(
    conn,
    clusters: list[IssueCluster],
) -> None:
    """Compute engagement for all clusters. Mutates each cluster in place."""
    for c in clusters:
        compute_engagement_for_cluster(conn, c)
