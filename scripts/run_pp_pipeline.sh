#!/usr/bin/env bash
# Run P&P pipeline: reconstruct threads, detect P&P, summarize, push to ClickUp.
# Used by launchd at 12:15 AM daily (after Reddit refresh).

set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

if [ -d "$ROOT/.venv" ]; then
  source "$ROOT/.venv/bin/activate"
fi

python scripts/run_pp_pipeline.py --db data/reddit.duckdb
