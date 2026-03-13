# Reddit Intelligence

A data pipeline for collecting, storing, and analyzing Reddit discussions from the **ClickUp subreddit**. Data is refreshed daily on your Mac and synced to Google Drive. A future web app will let you query the dataset with an AI-assisted SQL interface.

---

## Purpose

- **Ingest**: Pull posts and comments from the ClickUp subreddit using [Reddit's JSON API](https://www.reddit.com/dev/api/) (e.g. `https://www.reddit.com/r/clickup.json`).
- **Store**: Persist structured data in **DuckDB** for fast SQL analytics.
- **Refresh**: Run a **daily** refresh (local macOS only) to update:
  - Upvotes / downvotes and comment counts
  - New posts and comments
  - Only posts with activity in the last 30 days (last comment/reply)
- **Sync**: Upload the updated DuckDB file to Google Drive after each refresh.

---

## Repo Structure

```
reddit_intelligence/
├── .gitignore
├── README.md
├── data/           # DuckDB database, logs (git-ignored where large)
├── scripts/        # Ingestion, refresh, launchd, and ETL scripts
├── src/            # Core Python lib: API client, DB schema, models
├── webapp/         # Web UI (planned): query interface, AI SQL helper
└── docs/           # Design notes, runbooks
```

- **`data/`** – DuckDB file(s), refresh logs; `*.duckdb` and logs are git-ignored.
- **`scripts/`** – Fetch from Reddit, load into DuckDB, daily refresh script, launchd plist, Google Drive sync.
- **`src/`** – Reddit client, schema, parsers, DB helpers.
- **`webapp/`** – Placeholder for future query UI.

---

## Tech Stack

| Layer       | Choice                          |
|------------|----------------------------------|
| Data store | DuckDB                          |
| Ingestion  | Python + Reddit JSON API         |
| Refresh    | launchd (macOS, daily at midnight) |
| Sync       | Google Drive (service account)   |
| Browser    | Playwright (headless Chromium)  |

---

## Getting Started

1. **Clone** the repo and set up a Python virtual environment.
2. **Install deps**: `pip install -r requirements.txt` and `python -m playwright install chromium`.
3. **Secrets**: Put your Google Drive service account JSON at `secrets/gdrive-service-account.json` (folder is git-ignored). The refresh script uses it to upload the DB; you can override `GDRIVE_FILE_ID` and `GDRIVE_SA_PATH` via env if needed.
4. **Initial DB**: Create the schema and load data once (see Scraper below), or download an existing DB: `python scripts/gdrive_db_sync.py download --out data/reddit.duckdb`.
5. **Schedule**: Install the launchd job so refresh runs daily at midnight (see 24-hour refresh below).

### Scraper (last 30 days)

Create the DB and run the schema (see `scripts/schema/README.md`), then scrape r/clickup into DuckDB:

```bash
pip install -r requirements.txt
python -m playwright install chromium
python scripts/run_scrape_clickup_30d.py --db data/reddit.duckdb --days 30
```

Use `--dry-run` to fetch and parse without writing to the database.

### Database

- **Path:** `data/reddit.duckdb` (git-ignored).
- **Create/refresh:** Run the scraper once, then use the daily refresh script. The refresh script updates engagement and new posts; it skips posts with no activity (post or last comment/reply) in the last 30 days.
- **Google Drive:** The script `scripts/gdrive_db_sync.py` uploads the DB after refresh. Set `GDRIVE_FILE_ID` (Drive file ID of the DuckDB file). The refresh script sets defaults for `GDRIVE_FILE_ID` and `GDRIVE_SA_PATH` in `scripts/run_refresh_and_upload.sh`.

### 24-hour refresh (launchd, macOS)

Daily at **midnight**, the job runs the refresh then uploads the DB to Google Drive.

1. **One-time setup:**
   - `pip install -r requirements.txt` and `python -m playwright install chromium`
   - Place `secrets/gdrive-service-account.json` (and ensure `data/reddit.duckdb` exists or download it via `gdrive_db_sync.py download`)
2. **Install the launchd job:**
   ```bash
   cp scripts/com.reddit-intelligence.refresh.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.reddit-intelligence.refresh.plist
   ```
   On macOS 13+ (Ventura, Sonoma, Tahoe), if `launchctl bootstrap` fails with "Bootstrap failed: 5: Input/output error", use `launchctl load` above. The script sets `GDRIVE_FILE_ID` and `GDRIVE_SA_PATH` itself.
3. **Logs:** `data/refresh_stdout.log` and `data/refresh_stderr.log`
4. **Manual run:** `./scripts/run_refresh_and_upload.sh`
5. **Unload:** `launchctl unload ~/Library/LaunchAgents/com.reddit-intelligence.refresh.plist`

Refresh behavior: up to 500 posts per run, only posts created within the max-age window; existing posts are updated from listing data only (no full thread fetch) for speed; new posts get a full thread fetch. Browser delay between requests is 2 seconds.

---

## Future Enhancements

- **Web app**: Query UI and AI SQL helper (e.g. static or lightweight host).
- **Channels**: Expand beyond Reddit (e.g. Facebook, X, Product Hunt).
- **Analysis**: Themes, sentiment, prioritization of feedback.

---

## License

TBD.
