#!/usr/bin/env bash
# Run Reddit refresh (local browser) then upload DB to Google Drive.
# Used by launchd; sets GDRIVE_* here so plist needs no EnvironmentVariables (macOS Tahoe+).

set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

# Required for gdrive_db_sync (set here so launchd plist can omit EnvironmentVariables)
export GDRIVE_FILE_ID="${GDRIVE_FILE_ID:-1xG-inMHg4aVgUGgIdJOCmOc-OVC9nkNi}"
export GDRIVE_SA_PATH="${GDRIVE_SA_PATH:-$ROOT/secrets/gdrive-service-account.json}"

# Use venv if present
if [ -d "$ROOT/.venv" ]; then
  source "$ROOT/.venv/bin/activate"
fi

# Refresh r/clickup (headless browser; up to 500 posts from last 30 days; existing posts use listing only)
python scripts/run_refresh_clickup.py --db data/reddit.duckdb --max-posts 500 --max-age-days 30 --use-browser
# Upload to Drive
python scripts/gdrive_db_sync.py upload --file data/reddit.duckdb
