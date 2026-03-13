#!/usr/bin/env python3
"""
Stage 12: P&P workflow orchestrator.
Run: python scripts/run_pp_pipeline.py [--db path] [--max-age-days N] [--limit-posts N] [--no-clickup]
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add repo root so we can import src
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import PROJECT_ROOT
from src.dedup import clusters_to_issues, deduplicate_clusters
from src.engagement import compute_engagement_for_clusters
from src.gemini_pp import run_stages_2_3_4_6_on_thread
from src.priority import compute_priority_scores
from src.threads import load_threads_from_db, save_threads_json, thread_to_serializable
from src.db import get_connection
from src.clickup_client import send_to_clickup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pp_pipeline")


def main() -> int:
    parser = argparse.ArgumentParser(description="P&P Reddit → ClickUp pipeline")
    parser.add_argument("--db", default=None, help="DuckDB path (default: data/reddit.duckdb)")
    parser.add_argument("--max-age-days", type=int, default=30, help="Only posts from last N days")
    parser.add_argument("--limit-posts", type=int, default=None, help="Max posts to process (default: all)")
    parser.add_argument("--no-clickup", action="store_true", help="Skip sending to ClickUp")
    parser.add_argument("--dashboard-url", default="", help="URL of GitHub-hosted dashboard (for ClickUp message)")
    args = parser.parse_args()

    db_path = args.db or str(REPO_ROOT / "data" / "reddit.duckdb")
    data_dir = REPO_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    threads_path = data_dir / "reconstructed_threads.json"
    insights_path = data_dir / "pp_insights.json"
    dashboard_dir = REPO_ROOT / "webapp" / "pp-dashboard"
    dashboard_json = dashboard_dir / "insights.json"

    # Stage 1: Reconstruct threads
    logger.info("Stage 1: Reconstructing threads from DB")
    threads = load_threads_from_db(
        db_path=db_path,
        max_age_days=args.max_age_days,
        limit_posts=args.limit_posts,
    )
    if not threads:
        logger.warning("No threads to process; exiting")
        insights_path.write_text("[]", encoding="utf-8")
        if dashboard_dir.exists():
            dashboard_json.write_text("[]", encoding="utf-8")
        return 0

    save_threads_json(threads, threads_path)
    thread_dicts = [thread_to_serializable(t) for t in threads]

    # Stages 2, 3, 4, 6: Segment + P&P classify + summarize (per thread)
    logger.info("Stages 2–4, 6: Segmenting and classifying P&P")
    all_clusters = []
    for td in thread_dicts:
        post_id = td.get("post_id", "")
        permalink = td.get("permalink")
        try:
            clusters = run_stages_2_3_4_6_on_thread(td, post_id, permalink)
            all_clusters.extend(clusters)
        except Exception as e:
            logger.exception("Thread %s failed: %s", post_id, e)
            continue

    if not all_clusters:
        logger.warning("No P&P clusters detected; writing empty insights")
        issues_data = []
    else:
        # Stage 5: Engagement from DuckDB
        logger.info("Stage 5: Computing engagement")
        conn = get_connection(db_path)
        try:
            compute_engagement_for_clusters(conn, all_clusters)
        finally:
            conn.close()

        # Stage 7: Priority score
        logger.info("Stage 7: Computing priority scores")
        compute_priority_scores(all_clusters)

        # Stage 8: Deduplicate
        logger.info("Stage 8: Deduplicating clusters")
        merged = deduplicate_clusters(all_clusters)

        # Stage 9: To PPIssue and write JSON
        logger.info("Stage 9: Writing insights")
        issues = clusters_to_issues(merged)
        issues.sort(key=lambda x: x.priority_score, reverse=True)
        issues_data = [i.to_dict() for i in issues]

    insights_path.write_text(
        json.dumps(issues_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    dashboard_json.write_text(
        json.dumps(issues_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Stage 11: ClickUp
    if not args.no_clickup and issues_data:
        dashboard_url = args.dashboard_url or "https://YOUR_GITHUB_PAGES_URL/pp-dashboard/"
        logger.info("Stage 11: Sending summary to ClickUp")
        from src.pp_models import PPIssue
        issues_objs = [
            PPIssue(
                issue_id=o["issue_id"],
                issue_title=o["issue_title"],
                category=o["category"],
                summary=o["summary"],
                sentiment=o["sentiment"],
                frustration_level=o["frustration_level"],
                priority_score=o["priority_score"],
                unique_users=o["unique_users"],
                total_mentions=o["total_mentions"],
                engagement_score=o["engagement_score"],
                thread_count=o["thread_count"],
                first_seen_date=o.get("first_seen_date"),
                last_seen_date=o.get("last_seen_date"),
                example_quotes=o.get("example_quotes", []),
                source_links=o.get("source_links", []),
                root_cause_hypothesis=o.get("root_cause_hypothesis", ""),
                affected_plan_or_feature=o.get("affected_plan_or_feature", ""),
                urgency_signals=o.get("urgency_signals", False),
                competitor_mentions=o.get("competitor_mentions", []),
                responded_by_clickup=o.get("responded_by_clickup", False),
            )
            for o in issues_data
        ]
        send_to_clickup(issues_objs, dashboard_url)
    else:
        if args.no_clickup:
            logger.info("Skipping ClickUp (--no-clickup)")
        else:
            logger.info("No issues to send to ClickUp")

    logger.info("Pipeline complete. Insights: %s", insights_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
