"""Stages 2, 3, 4, 6: Gemini-based segmentation, P&P detection, summarization, sentiment."""

import json
import logging
import re
import uuid

from .config import get_gemini_api_key
from .pp_models import IssueCluster


def is_clickup_username(username: str | None) -> bool:
    """True if username starts or ends with 'clickup' (case-insensitive). Catches ClickUp, clickup, ClickUpTeam, etc."""
    if not username:
        return False
    u = str(username).strip().lower()
    return u.startswith("clickup") or u.endswith("clickup")

logger = logging.getLogger(__name__)

# P&P categories for classification (Stage 3)
PP_CATEGORIES = [
    "Billing Issues",
    "Discounts & Promotions",
    "Paywalls",
    "Plan Structure",
    "Usage Limits",
    "Feature Packaging",
    "Value Complaints",
    "Account/Subscription Management",
    "Unexpected Charges",
    "Other Relevant Signals",
]

SENTIMENT_VALUES = ("positive", "neutral", "negative")
FRUSTRATION_VALUES = ("low", "medium", "high", "critical")


def _get_model():
    import google.generativeai as genai

    key = get_gemini_api_key()
    if not key:
        raise ValueError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) must be set, or place key in secrets/gemini_api_key"
        )
    genai.configure(api_key=key)
    return genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config=genai.types.GenerationConfig(temperature=0.2),
    )


def _extract_json(text: str) -> dict | list:
    """Parse JSON from model response, stripping markdown code blocks if present."""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    return json.loads(text)


def flatten_thread_messages(root: dict) -> list[dict]:
    """Flatten thread root (post + nested replies) into ordered list of messages (depth-first)."""
    out: list[dict] = []

    def visit(node: dict) -> None:
        out.append({
            "id": node.get("id"),
            "author_username": node.get("author_username", ""),
            "body": node.get("body") or "",
            "created_utc": node.get("created_utc"),
            "permalink": node.get("permalink"),
            "depth": node.get("depth", 0),
        })
        for r in node.get("replies") or []:
            visit(r)

    visit(root)
    return out


def segment_thread(thread: dict, model=None) -> list[dict]:
    """
    Stage 2: Segment a single thread into clusters by P&P topic.
    thread: dict with "root" (nested messages) and "post_id", "permalink".
    Returns list of { "message_ids": [...], "topic_label": str }.
    """
    root = thread.get("root") or {}
    messages = flatten_thread_messages(root)
    if not messages:
        return []

    # Cap messages to avoid token overflow (e.g. 80)
    max_messages = 80
    if len(messages) > max_messages:
        messages = messages[:max_messages]
        logger.warning("Thread truncated to %s messages for segmentation", max_messages)

    lines = []
    for i, m in enumerate(messages):
        mid = m.get("id") or f"m{i}"
        author = (m.get("author_username") or "").replace("|", " ")
        body = (m.get("body") or "")[:500].replace("\n", " ")
        ts = m.get("created_utc") or ""
        lines.append(f"[{mid}] {author} ({ts}): {body}")

    prompt = f"""You are analyzing a Reddit thread about ClickUp (project management software).
Segment this thread into clusters. Each cluster is a set of message IDs that discuss the SAME Pricing or Packaging (P&P) issue.
- If a reply introduces a DIFFERENT P&P issue (e.g. billing vs. plan limits), put it in a new cluster.
- Ignore messages that are NOT about pricing, plans, billing, paywalls, discounts, costs, or packaging.
- Return ONLY valid JSON, no other text.

Thread (each line is one message with [id] author (timestamp): body):
{chr(10).join(lines)}

Return a JSON object with a single key "clusters", which is an array of objects. Each object has:
- "message_ids": array of message id strings (e.g. ["abc", "def"])
- "topic_label": short label for the P&P topic (e.g. "Promo code not working")

Example: {{ "clusters": [ {{ "message_ids": ["id1"], "topic_label": "Too expensive" }} ] }}
If no P&P-related discussion, return {{ "clusters": [] }}."""

    if model is None:
        model = _get_model()
    try:
        response = model.generate_content(prompt)
        text = (response.text or "").strip()
        data = _extract_json(text)
        clusters = data.get("clusters") if isinstance(data, dict) else []
        if not isinstance(clusters, list):
            return []
        return [c for c in clusters if isinstance(c, dict) and c.get("message_ids")]
    except Exception as e:
        logger.exception("Segment thread failed: %s", e)
        return []


def classify_pp(cluster_messages: list[dict], model=None) -> dict:
    """
    Stage 3: Classify whether cluster is P&P and get category, sentiment, frustration.
    cluster_messages: list of { "id", "body", "author_username", "created_utc", "permalink" }.
    Returns dict with is_pricing_packaging, category, sentiment, frustration, topic_id, summary.
    """
    text_blob = "\n\n".join(
        f"({m.get('author_username', '')}): {(m.get('body') or '')[:400]}"
        for m in cluster_messages[:20]
    )
    if not text_blob.strip():
        return {
            "is_pricing_packaging": False,
            "category": "",
            "sentiment": "neutral",
            "frustration": "low",
            "topic_id": "",
            "summary": "",
        }

    categories_str = ", ".join(PP_CATEGORIES)
    prompt = f"""You are classifying Reddit discussion about ClickUp for Pricing & Packaging (P&P) insights.
Determine if this conversation is about: billing, payments, discounts, promos, paywalls, plan tiers, usage limits, feature packaging, value/cost complaints, subscription management, unexpected charges, or similar.

Conversation:
{text_blob[:4000]}

Return a single JSON object with these exact keys:
- "is_pricing_packaging": boolean (true only if about pricing, plans, billing, or packaging)
- "category": one of: {categories_str}
- "sentiment": one of: positive, neutral, negative
- "frustration": one of: low, medium, high, critical
- "topic_id": short snake_case slug (e.g. promo_code_broken, plan_too_expensive)
- "summary": one-line summary

If is_pricing_packaging is false, set category to "" and topic_id to ""."""

    if model is None:
        model = _get_model()
    try:
        response = model.generate_content(prompt)
        data = _extract_json(response.text or "{}")
        if not isinstance(data, dict):
            return {
                "is_pricing_packaging": False,
                "category": "",
                "sentiment": "neutral",
                "frustration": "low",
                "topic_id": "",
                "summary": "",
            }
        return {
            "is_pricing_packaging": bool(data.get("is_pricing_packaging")),
            "category": str(data.get("category") or "").strip() or "Other Relevant Signals",
            "sentiment": data.get("sentiment") if data.get("sentiment") in SENTIMENT_VALUES else "neutral",
            "frustration": data.get("frustration") if data.get("frustration") in FRUSTRATION_VALUES else "low",
            "topic_id": str(data.get("topic_id") or "").strip(),
            "summary": str(data.get("summary") or "").strip(),
        }
    except Exception as e:
        logger.exception("Classify P&P failed: %s", e)
        return {
            "is_pricing_packaging": False,
            "category": "",
            "sentiment": "neutral",
            "frustration": "low",
            "topic_id": "",
            "summary": "",
        }


def summarize_cluster(
    cluster_messages: list[dict],
    topic_label: str,
    post_id: str,
    post_permalink: str | None,
    model=None,
) -> dict:
    """
    Stage 4 + 6: Summarize cluster into issue_title, problem_summary, frustration summary,
    root_cause_hypothesis, affected_plan_or_feature, example_quotes; and urgency/churn/competitor.
    """
    text_blob = "\n\n".join(
        f"({m.get('author_username', '')}): {(m.get('body') or '')[:400]}"
        for m in cluster_messages[:25]
    )
    if not text_blob.strip():
        return {
            "issue_title": topic_label or "Unknown",
            "problem_summary": "",
            "user_frustration_summary": "",
            "root_cause_hypothesis": "",
            "affected_plan_or_feature": "",
            "example_quotes": [],
            "urgency_signals": False,
            "churn_risk_language": False,
            "competitor_mentions": [],
        }

    prompt = f"""You are summarizing a Reddit discussion about ClickUp Pricing or Packaging issues.
Topic label: {topic_label}

Conversation:
{text_blob[:5000]}

Return a single JSON object with these keys:
- "issue_title": short title (e.g. "Promo code not applying at checkout")
- "problem_summary": 2-3 sentence summary of the problem
- "user_frustration_summary": how users express frustration
- "root_cause_hypothesis": possible cause if evident
- "affected_plan_or_feature": which plan or feature (e.g. Business, API limits)
- "example_quotes": array of 1-3 short direct quotes from users (exact or close)
- "urgency_signals": boolean (users saying urgent, ASAP, need fix now)
- "churn_risk_language": boolean (threatening to cancel, switch tool)
- "competitor_mentions": array of competitor names mentioned (e.g. ["Notion", "Asana"])"""

    if model is None:
        model = _get_model()
    try:
        response = model.generate_content(prompt)
        data = _extract_json(response.text or "{}")
        if not isinstance(data, dict):
            return {
                "issue_title": topic_label or "Unknown",
                "problem_summary": "",
                "user_frustration_summary": "",
                "root_cause_hypothesis": "",
                "affected_plan_or_feature": "",
                "example_quotes": [],
                "urgency_signals": False,
                "churn_risk_language": False,
                "competitor_mentions": [],
            }
        return {
            "issue_title": str(data.get("issue_title") or topic_label or "Unknown")[:200],
            "problem_summary": str(data.get("problem_summary") or "").strip(),
            "user_frustration_summary": str(data.get("user_frustration_summary") or "").strip(),
            "root_cause_hypothesis": str(data.get("root_cause_hypothesis") or "").strip(),
            "affected_plan_or_feature": str(data.get("affected_plan_or_feature") or "").strip(),
            "example_quotes": [str(q).strip() for q in (data.get("example_quotes") or []) if q][:5],
            "urgency_signals": bool(data.get("urgency_signals")),
            "churn_risk_language": bool(data.get("churn_risk_language")),
            "competitor_mentions": [str(x).strip() for x in (data.get("competitor_mentions") or []) if x],
        }
    except Exception as e:
        logger.exception("Summarize cluster failed: %s", e)
        return {
            "issue_title": topic_label or "Unknown",
            "problem_summary": "",
            "user_frustration_summary": "",
            "root_cause_hypothesis": "",
            "affected_plan_or_feature": "",
            "example_quotes": [],
            "urgency_signals": False,
            "churn_risk_language": False,
            "competitor_mentions": [],
        }


def run_stages_2_3_4_6_on_thread(
    thread: dict,
    post_id: str,
    post_permalink: str | None,
) -> list[IssueCluster]:
    """
    Run segmentation (2), then for each segment run P&P classification (3);
    keep only P&P clusters, then summarization (4+6). Returns list of IssueCluster.
    """
    segments = segment_thread(thread)
    if not segments:
        return []

    # Build id -> message from flattened list
    root = thread.get("root") or {}
    flat = flatten_thread_messages(root)
    id_to_msg = {m.get("id"): m for m in flat if m.get("id")}

    clusters: list[IssueCluster] = []
    model = _get_model()

    for seg in segments:
        message_ids = [x for x in (seg.get("message_ids") or []) if x]
        if not message_ids:
            continue
        topic_label = str(seg.get("topic_label") or "Unknown").strip()
        messages = [id_to_msg[mid] for mid in message_ids if id_to_msg.get(mid)]
        if not messages:
            continue

        # Stage 3: P&P classification
        class_result = classify_pp(messages, model=model)
        if not class_result.get("is_pricing_packaging"):
            continue

        # Stage 4 + 6: Summarization
        sum_result = summarize_cluster(
            messages,
            topic_label,
            post_id,
            post_permalink,
            model=model,
        )

        # Build source links
        source_links = []
        for m in messages:
            pl = m.get("permalink")
            if pl:
                source_links.append(pl)
        if post_permalink and post_permalink not in source_links:
            source_links.insert(0, post_permalink)

        users_reporting = list({m.get("author_username") or "" for m in messages if m.get("author_username")})
        created_utcs = [m.get("created_utc") for m in messages if m.get("created_utc")]
        first_seen = min(created_utcs) if created_utcs else None
        last_seen = max(created_utcs) if created_utcs else None
        responded_by_clickup = any(is_clickup_username(m.get("author_username")) for m in messages)

        cluster = IssueCluster(
            cluster_id=f"c_{uuid.uuid4().hex[:12]}",
            post_id=post_id,
            topic_label=topic_label,
            message_ids=message_ids,
            messages=messages,
            is_pricing_packaging=True,
            category=class_result.get("category", ""),
            sentiment=class_result.get("sentiment", "neutral"),
            frustration=class_result.get("frustration", "low"),
            topic_id=class_result.get("topic_id", ""),
            summary_one_line=class_result.get("summary", ""),
            issue_title=sum_result.get("issue_title", topic_label),
            problem_summary=sum_result.get("problem_summary", ""),
            user_frustration_summary=sum_result.get("user_frustration_summary", ""),
            root_cause_hypothesis=sum_result.get("root_cause_hypothesis", ""),
            affected_plan_or_feature=sum_result.get("affected_plan_or_feature", ""),
            example_quotes=sum_result.get("example_quotes", []),
            source_links=source_links,
            users_reporting=users_reporting,
            first_seen_utc=first_seen,
            last_seen_utc=last_seen,
            urgency_signals=sum_result.get("urgency_signals", False),
            churn_risk_language=sum_result.get("churn_risk_language", False),
            competitor_mentions=sum_result.get("competitor_mentions", []),
            responded_by_clickup=responded_by_clickup,
        )
        clusters.append(cluster)

    return clusters
