# Reddit Intelligence

A data pipeline and web app for collecting, storing, and analyzing Reddit discussions from the **ClickUp subreddit**. Data is refreshed weekly and made queryable via a GitHub-hosted web app with an AI-assisted SQL interface.

---

## Purpose

- **Ingest**: Pull posts and comments from the ClickUp subreddit using [Reddit’s JSON API](https://www.reddit.com/dev/api/) (e.g. `https://www.reddit.com/r/clickup.json`).
- **Store**: Persist structured data in an open-source analytical database (**DuckDB** or similar) for fast SQL analytics.
- **Refresh**: Run a **weekly** refresh job to update:
  - Upvotes / downvotes  
  - Comment counts and thread engagement  
  - New posts and comments  
- **Explore**: A **web app** (hosted via GitHub, e.g. GitHub Pages or similar) that:
  - Browses and studies the dataset  
  - Runs **ad-hoc SQL queries**  
  - Provides an **AI helper** for writing and refining SQL  

---

## Repo Structure

```
reddit_intelligence/
├── .gitignore
├── README.md
├── data/           # DuckDB database, raw/processed data (git-ignored where large)
├── scripts/        # Ingestion, refresh, and one-off ETL scripts
├── src/            # Core Python lib: API client, DB schema, models
├── webapp/         # Web UI: query interface, AI SQL helper, GitHub-hosted
└── docs/           # Design notes, runbooks, future specs
```

- **`data/`** – DuckDB file(s), optional raw JSON, and processed tables; large files excluded via `.gitignore`.
- **`scripts/`** – Scripts to fetch from Reddit, load into DuckDB, and run the weekly refresh.
- **`src/`** – Shared code: Reddit client, schema definitions, and data models.
- **`webapp/`** – Frontend and (if needed) minimal backend for the query UI and AI SQL assistant.
- **`docs/`** – Documentation and future enhancement specs.

---

## Tech Stack (Planned)

| Layer        | Choice |
|-------------|--------|
| Data store  | DuckDB (or similar open-source analytical DB) |
| Ingestion   | Python + Reddit JSON API |
| Refresh     | Cron / GitHub Actions (weekly) |
| Web app     | Static or lightweight stack, hostable on GitHub (e.g. Pages) |
| SQL helper  | AI integration in the web app for generating/editing SQL |

---

## Future Enhancements

### 1. Centralized Feedback Collection

- **Channels**: Expand beyond Reddit to other channels (e.g. Facebook, X, Product Hunt).
- **Tools**: Use social listening tools (e.g. Brandwatch, Sprout Social) or manual tracking.
- **Storage**: Centralize all feedback in one place (e.g. ClickUp, Google Sheets, or a dedicated DB).

### 2. Qualitative Analysis

- **Themes**: Surface recurring themes and patterns across feedback.
- **Pain points**: Highlight common frustrations and challenges.
- **Opportunities**: Capture suggestions and ideas for product or feature improvements.

### 3. Quantitative Insights

- **Frequency**: How often specific themes or issues are mentioned.
- **Sentiment trends**: Sentiment over time by category.
- **Impact**: Assess impact of addressing different feedback areas.

### 4. Decision-Making Framework

- **Prioritization matrix**: Prioritize by urgency, impact, and feasibility.
- **Actionable insights**: Turn feedback into tasks (e.g. feature updates, bug fixes, pricing).
- **Ownership**: Assign owners for each feedback category or initiative.

---

## Getting Started (Planned)

1. **Clone** the repo and set up a Python virtual environment.
2. **Configure** Reddit API usage (respect rate limits; use OAuth if needed for higher limits).
3. **Run ingestion** once to create the DuckDB schema and load initial data.
4. **Schedule** the weekly refresh (e.g. via cron or GitHub Actions).
5. **Serve** the web app and use the UI to explore data and the AI SQL helper.

### Scraper (last 30 days)

Create the DB and run the schema (see `scripts/schema/README.md`), then scrape r/clickup into DuckDB:

```bash
pip install -r requirements.txt
python scripts/run_scrape_clickup_30d.py --db data/reddit.duckdb --days 30
```

Use `--dry-run` to fetch and parse without writing to the database.

### Database

- **Path:** The main DuckDB file is `data/reddit.duckdb`. It is git-ignored (`*.duckdb` in `.gitignore`), so it is not pushed to the repo.
- **Create/refresh:** Create the schema (see `scripts/schema/README.md`) and run the scraper or the 24h refresh script (see below). For **GitHub Actions** (scheduled refresh), the workflow can sync the DB via **Google Drive**: download the DB, run the refresh, then upload the updated file. That requires a Google Cloud service account with Drive API access.
- **Service account key (local):** For local runs that use Google Drive, put the service account JSON at **`secrets/gdrive-service-account.json`** (create the `secrets/` folder; it is git-ignored). For Actions, add a repo secret **`GDRIVE_SA_JSON`** with the full contents of that JSON. See the workflow file and docs for download/upload steps.

### 24-hour refresh

To refresh the DB (new posts + update engagement and comment trees) on a schedule:

- **Local (cron):** Run daily, e.g. `0 0 * * *` (midnight):  
  `cd /path/to/reddit_intelligence && .venv/bin/python scripts/run_refresh_clickup.py --db data/reddit.duckdb --max-posts 100`
- **GitHub Actions:** Use the workflow in `.github/workflows/refresh-reddit.yml` (24h schedule). Set repo secrets **`GDRIVE_SA_JSON`** (full service account JSON) and **`GDRIVE_FILE_ID`** (Drive file ID of the DuckDB file). The workflow downloads the DB from Drive, runs the refresh, and uploads the DB back.

---

## License

TBD.
