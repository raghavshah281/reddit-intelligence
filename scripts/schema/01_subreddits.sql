-- Global registry of tracked subreddits and their DuckDB schema names.
-- Run once per database. Each subreddit gets its own schema (see 02_*).

CREATE SCHEMA IF NOT EXISTS meta;

CREATE TABLE IF NOT EXISTS meta.subreddits (
    subreddit_id   VARCHAR PRIMARY KEY,  -- Reddit id e.g. t5_xxxxx
    name           VARCHAR NOT NULL,     -- normalized name e.g. clickup
    display_name   VARCHAR,              -- e.g. ClickUp
    schema_name    VARCHAR NOT NULL,     -- DuckDB schema e.g. clickup
    subscribers    INTEGER,
    last_synced_at TIMESTAMP,
    created_at     TIMESTAMP DEFAULT current_timestamp,
    updated_at     TIMESTAMP DEFAULT current_timestamp
);
