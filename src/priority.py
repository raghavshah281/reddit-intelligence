"""Stage 7: Priority score (0-100) from users, engagement, sentiment, frustration, recency."""

from datetime import datetime, timezone

from .pp_models import IssueCluster

# Weights (sum = 1.0)
W_USER = 0.35
W_ENGAGEMENT = 0.20
W_SENTIMENT = 0.20
W_FRUSTRATION = 0.15
W_RECENCY = 0.10

# Normalization caps
MAX_USERS_FOR_NORM = 20
MAX_ENGAGEMENT_FOR_NORM = 200
RECENCY_DAYS_DECAY = 90


def _user_component(unique_users: int) -> float:
    return min(1.0, unique_users / MAX_USERS_FOR_NORM)


def _engagement_component(engagement_score: float) -> float:
    return min(1.0, engagement_score / MAX_ENGAGEMENT_FOR_NORM)


def _sentiment_weight(sentiment: str) -> float:
    s = (sentiment or "").lower()
    if s == "negative":
        return 1.0
    if s == "neutral":
        return 0.5
    return 0.0


def _frustration_weight(frustration: str) -> float:
    f = (frustration or "").lower()
    if f == "critical":
        return 1.0
    if f == "high":
        return 0.75
    if f == "medium":
        return 0.5
    return 0.25


def _recency_component(last_seen_utc: str | None) -> float:
    if not last_seen_utc:
        return 0.5
    try:
        s = str(last_seen_utc).strip()
        if " " in s:
            dt = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        elif "T" in s:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00")[:23])
        else:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        days_ago = (now - dt).days
        return max(0.0, 1.0 - (days_ago / RECENCY_DAYS_DECAY))
    except Exception:
        return 0.5


def compute_priority_score(cluster: IssueCluster) -> float:
    """
    Compute priority score 0-100 for an IssueCluster.
    Uses: unique_users (0.35), engagement (0.20), sentiment (0.20), frustration (0.15), recency (0.10).
    """
    users = cluster.total_participants
    eng = cluster.engagement_score
    sent = cluster.sentiment
    frust = cluster.frustration
    last_seen = cluster.last_seen_utc

    u = _user_component(users)
    e = _engagement_component(eng)
    s = _sentiment_weight(sent)
    f = _frustration_weight(frust)
    r = _recency_component(last_seen)

    raw = (u * W_USER) + (e * W_ENGAGEMENT) + (s * W_SENTIMENT) + (f * W_FRUSTRATION) + (r * W_RECENCY)
    return round(min(100.0, max(0.0, raw * 100.0)), 1)


def compute_priority_scores(clusters: list[IssueCluster]) -> None:
    """Set priority_score on each cluster in place."""
    for c in clusters:
        c.priority_score = compute_priority_score(c)
