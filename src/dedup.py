"""Stage 8: Deduplicate issue clusters across threads (semantic merge)."""

import hashlib
import logging
import uuid

from .pp_models import IssueCluster, PPIssue

logger = logging.getLogger(__name__)

# Similarity threshold: merge clusters with similarity >= this (0-1)
DEFAULT_MERGE_THRESHOLD = 0.85


def _cluster_to_text(c: IssueCluster) -> str:
    """Text used for semantic similarity: title + summary + topic."""
    return " ".join(
        filter(None, [
            c.issue_title,
            c.topic_label,
            c.problem_summary,
            c.summary_one_line,
            " ".join(c.example_quotes[:2]),
        ])
    ).strip()


def _simple_hash_similarity(a: str, b: str) -> float:
    """
    Very simple lexical similarity: Jaccard on word set, then exact match boost.
    No Gemini embeddings to avoid extra API cost; pipeline can swap in embedding-based later.
    """
    if not a or not b:
        return 0.0
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words and not b_words:
        return 0.0
    inter = len(a_words & b_words)
    union = len(a_words | b_words)
    if union == 0:
        return 0.0
    jaccard = inter / union
    # Boost if one contains the other (e.g. "promo code" in both)
    if a_words <= b_words or b_words <= a_words:
        jaccard = min(1.0, jaccard + 0.2)
    return jaccard


def _merge_two_clusters(a: IssueCluster, b: IssueCluster) -> IssueCluster:
    """Merge b into a (mutate a); return a."""
    a.message_ids = list(set(a.message_ids) | set(b.message_ids))
    a.messages = a.messages + [m for m in b.messages if m not in a.messages]
    a.total_participants = len(set(a.users_reporting) | set(b.users_reporting))
    a.users_reporting = list(set(a.users_reporting) | set(b.users_reporting))
    a.total_mentions += b.total_mentions
    a.engagement_score += b.engagement_score
    a.thread_count += 1
    a.source_links = list(dict.fromkeys(a.source_links + b.source_links))
    a.example_quotes = list(dict.fromkeys(a.example_quotes + b.example_quotes))[:10]
    if b.first_seen_utc and (not a.first_seen_utc or (b.first_seen_utc < a.first_seen_utc)):
        a.first_seen_utc = b.first_seen_utc
    if b.last_seen_utc and (not a.last_seen_utc or (b.last_seen_utc > a.last_seen_utc)):
        a.last_seen_utc = b.last_seen_utc
    order = ("low", "medium", "high", "critical")
    try:
        if b.frustration in order and a.frustration in order:
            if order.index(b.frustration) > order.index(a.frustration):
                a.frustration = b.frustration
    except (ValueError, AttributeError):
        pass
    a.competitor_mentions = list(set(a.competitor_mentions) | set(b.competitor_mentions))
    a.urgency_signals = a.urgency_signals or b.urgency_signals
    a.churn_risk_language = a.churn_risk_language or b.churn_risk_language
    a.responded_by_clickup = a.responded_by_clickup or b.responded_by_clickup
    return a


def deduplicate_clusters(
    clusters: list[IssueCluster],
    threshold: float = DEFAULT_MERGE_THRESHOLD,
) -> list[IssueCluster]:
    """
    Merge clusters that refer to the same P&P issue (by title/summary similarity).
    Uses simple lexical similarity; can be replaced with embedding similarity later.
    """
    if len(clusters) <= 1:
        return list(clusters)

    # Sort by priority (desc) so we keep higher-priority as canonical
    by_priority = sorted(clusters, key=lambda c: (c.priority_score, c.total_mentions), reverse=True)
    merged: list[IssueCluster] = []
    used = set()

    for i, ca in enumerate(by_priority):
        if i in used:
            continue
        current = ca
        for j, cb in enumerate(by_priority):
            if i >= j or j in used:
                continue
            sim = _simple_hash_similarity(_cluster_to_text(current), _cluster_to_text(cb))
            if sim >= threshold:
                current = _merge_two_clusters(
                    IssueCluster(
                        cluster_id=current.cluster_id,
                        post_id=current.post_id,
                        topic_label=current.topic_label,
                        message_ids=list(current.message_ids),
                        messages=list(current.messages),
                        is_pricing_packaging=current.is_pricing_packaging,
                        category=current.category,
                        sentiment=current.sentiment,
                        frustration=current.frustration,
                        topic_id=current.topic_id,
                        summary_one_line=current.summary_one_line,
                        issue_title=current.issue_title,
                        problem_summary=current.problem_summary,
                        user_frustration_summary=current.user_frustration_summary,
                        root_cause_hypothesis=current.root_cause_hypothesis,
                        affected_plan_or_feature=current.affected_plan_or_feature,
                        example_quotes=list(current.example_quotes),
                        source_links=list(current.source_links),
                        users_reporting=list(current.users_reporting),
                        first_seen_utc=current.first_seen_utc,
                        last_seen_utc=current.last_seen_utc,
                        urgency_signals=current.urgency_signals,
                        churn_risk_language=current.churn_risk_language,
                        competitor_mentions=list(current.competitor_mentions),
                        total_participants=current.total_participants,
                        total_mentions=current.total_mentions,
                        engagement_score=current.engagement_score,
                        thread_count=current.thread_count,
                        priority_score=current.priority_score,
                        responded_by_clickup=current.responded_by_clickup,
                    ),
                    cb,
                )
                used.add(j)
        merged.append(current)

    # Recompute priority for merged (participants/engagement changed)
    from .priority import compute_priority_score
    for c in merged:
        c.priority_score = compute_priority_score(c)
    merged.sort(key=lambda c: c.priority_score, reverse=True)
    logger.info("Dedup: %s clusters -> %s merged", len(clusters), len(merged))
    return merged


def clusters_to_issues(clusters: list[IssueCluster]) -> list[PPIssue]:
    """Convert IssueCluster list to canonical PPIssue list (Stage 9 output)."""
    issues = []
    for c in clusters:
        issue_id = _issue_id_from_cluster(c)
        first_date = _utc_to_date(c.first_seen_utc)
        last_date = _utc_to_date(c.last_seen_utc)
        issues.append(
            PPIssue(
                issue_id=issue_id,
                issue_title=c.issue_title or c.topic_label,
                category=c.category,
                summary=c.problem_summary or c.summary_one_line,
                sentiment=c.sentiment,
                frustration_level=c.frustration,
                priority_score=c.priority_score,
                unique_users=c.total_participants,
                total_mentions=c.total_mentions,
                engagement_score=c.engagement_score,
                thread_count=c.thread_count,
                first_seen_date=first_date,
                last_seen_date=last_date,
                example_quotes=c.example_quotes[:5],
                source_links=c.source_links,
                root_cause_hypothesis=c.root_cause_hypothesis,
                affected_plan_or_feature=c.affected_plan_or_feature,
                urgency_signals=c.urgency_signals,
                competitor_mentions=c.competitor_mentions,
                responded_by_clickup=c.responded_by_clickup,
            )
        )
    return issues


def _issue_id_from_cluster(c: IssueCluster) -> str:
    """Stable issue_id from topic_id + hash of title/summary."""
    base = (c.topic_id or c.issue_title or c.cluster_id).strip()
    if not base:
        base = str(uuid.uuid4())
    h = hashlib.sha256((c.issue_title + "|" + (c.problem_summary or "")).encode()).hexdigest()[:8]
    return f"pp_{base[:30]}_{h}".replace(" ", "_")


def _utc_to_date(utc_str: str | None) -> str | None:
    if not utc_str:
        return None
    s = str(utc_str).strip()
    if len(s) >= 10:
        return s[:10]
    return s
