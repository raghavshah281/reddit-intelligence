-- Per-subreddit schema: users, posts, comments.
-- Repeat this pattern for each new subreddit (e.g. schema name = normalized subreddit name).
-- This file creates the clickup schema for r/clickup.

CREATE SCHEMA IF NOT EXISTS clickup;

-- Users who have posted or commented in this subreddit.
CREATE TABLE IF NOT EXISTS clickup.users (
    user_id       VARCHAR PRIMARY KEY,   -- Reddit author_fullname e.g. t2_xxxxx
    username      VARCHAR NOT NULL,      -- Reddit author
    is_premium    BOOLEAN,
    flair_text    VARCHAR,
    first_seen_at TIMESTAMP,
    last_seen_at  TIMESTAMP
);

-- Posts: primary content table. post_id is the main key referenced by comments.
CREATE TABLE IF NOT EXISTS clickup.posts (
    post_id                  VARCHAR PRIMARY KEY,
    user_id                  VARCHAR NOT NULL REFERENCES clickup.users(user_id),
    title                    VARCHAR NOT NULL,
    selftext                 VARCHAR,
    selftext_html            VARCHAR,
    permalink                VARCHAR,
    url                      VARCHAR,
    domain                   VARCHAR,
    score                    INTEGER,
    ups                      INTEGER,
    downs                    INTEGER,
    upvote_ratio             DOUBLE,
    num_comments             INTEGER,
    num_crossposts           INTEGER,
    total_awards_received    INTEGER,
    created_utc              TIMESTAMP,
    edited_at                TIMESTAMP,
    is_self                  BOOLEAN,
    post_hint                VARCHAR,
    is_video                 BOOLEAN,
    over_18                  BOOLEAN,
    spoiler                  BOOLEAN,
    locked                   BOOLEAN,
    archived                 BOOLEAN,
    stickied                 BOOLEAN,
    subreddit_subscribers    INTEGER,
    inserted_at              TIMESTAMP DEFAULT current_timestamp,
    updated_at               TIMESTAMP DEFAULT current_timestamp
);

-- Comments and replies. parent_comment_id NULL = top-level; non-NULL = reply to that comment.
-- thread_path: materialized path from root [post_id, comment_id_1, ...] for tree queries.
CREATE TABLE IF NOT EXISTS clickup.comments (
    comment_id               VARCHAR PRIMARY KEY,
    post_id                  VARCHAR NOT NULL REFERENCES clickup.posts(post_id),
    user_id                  VARCHAR NOT NULL REFERENCES clickup.users(user_id),
    parent_reddit_id         VARCHAR NOT NULL,   -- Reddit parent_id e.g. t3_xxx or t1_xxx
    parent_comment_id        VARCHAR REFERENCES clickup.comments(comment_id),
    depth                    INTEGER NOT NULL,  -- 0 = top-level
    thread_path              VARCHAR[],         -- path from root; DuckDB: LIST stored as VARCHAR[] or use LIST type
    body                     VARCHAR,
    body_html                VARCHAR,
    score                    INTEGER,
    ups                      INTEGER,
    downs                    INTEGER,
    total_awards_received    INTEGER,
    controversiality        INTEGER,
    created_utc              TIMESTAMP,
    edited_at                TIMESTAMP,
    score_hidden             BOOLEAN,
    stickied                 BOOLEAN,
    removed                  BOOLEAN,
    locked                   BOOLEAN,
    inserted_at              TIMESTAMP DEFAULT current_timestamp,
    updated_at               TIMESTAMP DEFAULT current_timestamp
);
