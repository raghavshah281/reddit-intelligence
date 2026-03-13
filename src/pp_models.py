"""Data models for P&P (Pricing & Packaging) workflow: threads, clusters, issues."""

from dataclasses import dataclass, field
from typing import Any

# --- Thread reconstruction (Stage 1) ---


@dataclass
class ThreadMessage:
    """Single node in a thread: post or comment."""
    id: str  # post_id or comment_id
    author_id: str
    author_username: str
    created_utc: str | None
    body: str | None  # selftext for post, body for comment
    score: int | None
    ups: int | None
    downs: int | None
    upvote_ratio: float | None  # post only
    permalink: str | None  # full Reddit URL for this message
    depth: int  # 0 = post, 1+ = comment depth
    replies: list["ThreadMessage"] = field(default_factory=list)


@dataclass
class ReconstructedThread:
    """One thread: root post + comment tree."""
    post_id: str
    root: ThreadMessage  # the post + nested replies
    title: str
    permalink: str | None


# --- Segmentation & P&P (Stages 2–4, 6) ---


@dataclass
class MessageRef:
    """Reference to a message within a thread (for clusters)."""
    id: str
    body: str | None
    author_username: str
    created_utc: str | None
    permalink: str | None


@dataclass
class IssueCluster:
    """One P&P issue cluster (before dedup). May span one thread."""
    cluster_id: str
    post_id: str
    topic_label: str
    message_ids: list[str]
    messages: list[dict[str, Any]]  # full message refs for summarization
    # From Stage 3
    is_pricing_packaging: bool = True
    category: str = ""
    sentiment: str = "neutral"
    frustration: str = "low"
    topic_id: str = ""
    summary_one_line: str = ""
    # From Stage 4
    issue_title: str = ""
    problem_summary: str = ""
    user_frustration_summary: str = ""
    root_cause_hypothesis: str = ""
    affected_plan_or_feature: str = ""
    example_quotes: list[str] = field(default_factory=list)
    source_links: list[str] = field(default_factory=list)
    users_reporting: list[str] = field(default_factory=list)
    first_seen_utc: str | None = None
    last_seen_utc: str | None = None
    # From Stage 6
    urgency_signals: bool = False
    churn_risk_language: bool = False
    competitor_mentions: list[str] = field(default_factory=list)
    # From Stage 5 (filled later)
    total_participants: int = 0
    total_mentions: int = 0
    engagement_score: float = 0.0
    thread_count: int = 1
    # From Stage 7 (filled later)
    priority_score: float = 0.0
    # True if any message in the cluster is from a user whose username starts/ends with "clickup" (any case)
    responded_by_clickup: bool = False


# --- Output (Stage 9): canonical issue for dashboard & ClickUp ---


@dataclass
class PPIssue:
    """Canonical issue after dedup. Written to JSON and consumed by dashboard + ClickUp."""
    issue_id: str
    issue_title: str
    category: str
    summary: str
    sentiment: str
    frustration_level: str
    priority_score: float
    unique_users: int
    total_mentions: int
    engagement_score: float
    thread_count: int
    first_seen_date: str | None
    last_seen_date: str | None
    example_quotes: list[str]
    source_links: list[str]
    root_cause_hypothesis: str = ""
    affected_plan_or_feature: str = ""
    urgency_signals: bool = False
    competitor_mentions: list[str] = field(default_factory=list)
    responded_by_clickup: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "issue_title": self.issue_title,
            "category": self.category,
            "summary": self.summary,
            "sentiment": self.sentiment,
            "frustration_level": self.frustration_level,
            "priority_score": round(self.priority_score, 1),
            "unique_users": self.unique_users,
            "total_mentions": self.total_mentions,
            "engagement_score": round(self.engagement_score, 1),
            "thread_count": self.thread_count,
            "first_seen_date": self.first_seen_date,
            "last_seen_date": self.last_seen_date,
            "example_quotes": self.example_quotes,
            "source_links": self.source_links,
            "root_cause_hypothesis": self.root_cause_hypothesis,
            "affected_plan_or_feature": self.affected_plan_or_feature,
            "urgency_signals": self.urgency_signals,
            "competitor_mentions": self.competitor_mentions,
            "responded_by_clickup": self.responded_by_clickup,
        }
