"""Stage 11: Send P&P insights summary to ClickUp staging chat channel."""

import logging
from pathlib import Path

import requests

from .config import PROJECT_ROOT, get_clickup_api_key
from .pp_models import PPIssue

logger = logging.getLogger(__name__)

CLICKUP_STAGING_URL = (
    "https://api.clickup-stg.com/api/v3/workspaces/333/chat/channels/ad-3019485/messages"
)


def _load_api_key() -> str:
    key = get_clickup_api_key()
    if not key:
        path = PROJECT_ROOT / "secrets" / "clickup_api"
        if path.exists():
            key = path.read_text(encoding="utf-8").strip()
    return key or ""


def build_summary_markdown(issues: list[PPIssue], dashboard_url: str) -> str:
    """Build one summary message (markdown) for ClickUp with dashboard link and top issues."""
    lines = [
        "## Reddit P&P Insights Update",
        "",
        f"**Dashboard:** {dashboard_url}",
        "",
        f"**Total issues:** {len(issues)}",
        "",
        "### Top issues by priority",
        "",
    ]
    for i, issue in enumerate(issues[:5], 1):
        lines.append(f"{i}. **{issue.issue_title}** — {issue.category} (score: {issue.priority_score})")
        lines.append(f"   - {issue.summary[:150]}..." if len(issue.summary) > 150 else f"   - {issue.summary}")
        lines.append("")
    return "\n".join(lines)


def send_to_clickup(
    issues: list[PPIssue],
    dashboard_url: str,
    api_key: str | None = None,
) -> bool:
    """
    POST a single summary message to ClickUp staging channel.
    Body: type "message", content = markdown with dashboard link and top issues.
    Returns True on 201, False otherwise.
    """
    key = (api_key or _load_api_key()).strip()
    if not key:
        logger.warning("ClickUp API key not set; skipping send")
        return False

    content = build_summary_markdown(issues, dashboard_url)
    payload = {
        "type": "message",
        "content": content,
    }
    headers = {
        "Authorization": key,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(CLICKUP_STAGING_URL, json=payload, headers=headers, timeout=30)
        if resp.status_code == 201:
            logger.info("ClickUp message sent successfully")
            return True
        logger.warning("ClickUp API returned %s: %s", resp.status_code, resp.text[:500])
        return False
    except requests.RequestException as e:
        logger.exception("ClickUp request failed: %s", e)
        return False
