-- Post-level engagement snapshots for weekly refresh / time-series analysis.
-- One row per post per snapshot time. Create in each subreddit schema.

CREATE TABLE IF NOT EXISTS clickup.engagement_snapshots (
    snapshot_id   VARCHAR PRIMARY KEY,  -- e.g. uuid or post_id || '_' || snapshot_at
    post_id       VARCHAR NOT NULL REFERENCES clickup.posts(post_id),
    snapshot_at   TIMESTAMP NOT NULL,
    score         INTEGER,
    num_comments  INTEGER,
    upvote_ratio  DOUBLE
);
