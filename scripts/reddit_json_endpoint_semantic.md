# Reddit JSON Endpoint — Reference & Extraction Scope

Semantic reference for Reddit’s public JSON endpoints. Use this when building ingestion for **posts**, **full comment trees**, **authors**, **timestamps**, and **engagement** across one or more subreddits.

---

## 1. Data extraction scope (this project)

We need to extract:

| Scope | Details |
|-------|--------|
| **Posts** | One record per post (all fields below). |
| **Comment tree** | Full nested thread per post (every comment + reply). |
| **Author** | Post author + comment authors (usernames, IDs). |
| **Time** | Creation/edit timestamps (UTC) for posts and comments. |
| **Engagement** | Score, upvotes, downvotes, upvote_ratio, num_comments, awards, etc. |
| **Subreddits** | Support multiple subreddits; start with one, extend later. |

### Target subreddits (initial)

| Subreddit | URL |
|-----------|-----|
| **ClickUp** | `https://www.reddit.com/r/clickup/` |

*More subreddits will be added later.*

---

## 2. Request basics

- **Pattern**: Append `.json` to any Reddit page URL.
- **User-Agent**: Set a `User-Agent` header (e.g. `Mozilla/5.0`) or requests may be blocked.
- **Rate limit**: ~1 request per second recommended.

Example:

```python
import requests

headers = {"User-Agent": "Mozilla/5.0"}
url = "https://www.reddit.com/r/clickup/.json"
response = requests.get(url, headers=headers)
data = response.json()
```

---

## 3. Endpoints we use

### 3.1 Subreddit listing (posts)

Get posts for a subreddit.

| Purpose | URL pattern | Notes |
|---------|-------------|--------|
| Posts (default sort) | `https://www.reddit.com/r/{subreddit}/.json` | |
| New | `/r/{subreddit}/new.json` | |
| Hot | `/r/{subreddit}/hot.json` | |
| Top | `/r/{subreddit}/top.json` | |
| Best | `/r/{subreddit}/best.json` | |
| Top + time | `/r/{subreddit}/top.json?t=day` | `t`: `hour`, `day`, `week`, `month`, `year`, `all` |

**Query params:**

- `limit=100` — posts per request (max 100).
- `after=t3_{postid}` — pagination cursor for next page.

Example:

```
https://www.reddit.com/r/clickup/.json?limit=100
```

### 3.2 Single post + comment tree

Get one post and its full comment tree.

| Purpose | URL pattern |
|---------|-------------|
| Post + comments | `https://www.reddit.com/r/{subreddit}/comments/{postid}/{slug}/.json` |

Response is an array:

- `[0]` — listing with the **post** (one child).
- `[1]` — listing with **comments**; nested replies under `replies.data.children`.

Post ID can be taken from the post’s `id` or from `name` (e.g. `t3_xxxxx` → `xxxxx`).

### 3.3 Search (optional)

- All of Reddit: `https://www.reddit.com/search.json?q=keyword`
- Within subreddit: `https://www.reddit.com/r/{subreddit}/search.json?q=query&restrict_sr=1`

---

## 4. JSON shape (listings)

Subreddit or comment listing:

```
Listing
  data
    after      — pagination cursor
    dist       — number of items in this response
    children[] — array of things (t3 = post, t1 = comment)
      kind     — "t3" or "t1"
      data     — object with fields below
```

Example listing:

```json
{
  "kind": "Listing",
  "data": {
    "after": "t3_abcdef",
    "dist": 25,
    "children": [
      { "kind": "t3", "data": { /* post fields */ } }
    ]
  }
}
```

Thread response (post + comments):

- First listing: one `t3` (the post).
- Second listing: `t1` comments; each comment can have `replies` (same structure: `data.children`).

---

## 5. Post fields (extract for each post)

### 5.1 Core

| Field | Description |
|-------|-------------|
| `id` | Post ID (short). |
| `name` | Full ID, e.g. `t3_xxxxx`. |
| `title` | Post title. |
| `selftext` | Body (plain text). |
| `selftext_html` | Body (HTML). |
| `author` | Username. |
| `author_fullname` | User ID, e.g. `t2_xxxxx`. |
| `subreddit` | Subreddit name. |
| `subreddit_name_prefixed` | e.g. `r/clickup`. |
| `subreddit_id` | e.g. `t5_xxxxx`. |
| `permalink` | URL path. |
| `url` | Link (external or permalink). |
| `domain` | Domain of linked content. |

### 5.2 Engagement

| Field | Description |
|-------|-------------|
| `score` | Net score. |
| `ups` | Upvotes. |
| `downs` | Downvotes (often hidden). |
| `upvote_ratio` | Upvote ratio. |
| `num_comments` | Comment count. |
| `num_crossposts` | Crosspost count. |
| `total_awards_received` | Total awards. |
| `all_awardings` | List of awards. |
| `gilded` / `gildings` | Gold / award details. |

### 5.3 Time

| Field | Description |
|-------|-------------|
| `created_utc` | Created (UTC unix). |
| `created` | Created (local unix). |
| `edited` | Edit time or `false`. |

### 5.4 Author & subreddit metadata

| Field | Description |
|-------|-------------|
| `author_premium` | Reddit premium. |
| `author_flair_text` | Flair text. |
| `author_flair_background_color` | Flair style. |
| `author_flair_text_color` | Flair text color. |
| `subreddit_type` | e.g. public/private. |
| `subreddit_subscribers` | Subscriber count. |

### 5.5 Type & content

| Field | Description |
|-------|-------------|
| `is_self` | Text post. |
| `post_hint` | e.g. image/link/video. |
| `is_video` | Video post. |
| `over_18` | NSFW. |
| `spoiler` | Spoiler. |
| `locked` | Comments locked. |
| `archived` | Archived. |
| `stickied` | Pinned. |

### 5.6 Moderation (optional)

| Field | Description |
|-------|-------------|
| `approved_at_utc` | Approval time. |
| `removed_by_category` | Removal reason. |
| `banned_by` | Ban info. |
| `mod_reports` / `user_reports` | Reports. |

### 5.7 Media (optional)

| Field | Description |
|-------|-------------|
| `thumbnail`, `thumbnail_width`, `thumbnail_height` | Thumbnail. |
| `preview` | Image previews. |
| `media_metadata` | Media metadata. |
| `secure_media` | Embedded media. |

### 5.8 Pagination (listing root)

| Field | Description |
|-------|-------------|
| `after` | Cursor for next page. |
| `before` | Cursor for previous page. |
| `dist` | Number of items in this response. |

---

## 6. Comment fields (extract for each comment in the tree)

Each comment is `kind: "t1"` with a `data` object. Nested replies are in `data.replies` (same structure: listing → `data.children`).

### 6.1 Core

| Field | Description |
|-------|-------------|
| `id` | Comment ID. |
| `name` | Full ID, e.g. `t1_xxxxx`. |
| `body` | Comment text. |
| `body_html` | Comment HTML. |
| `author` | Username. |
| `author_fullname` | User ID. |
| `parent_id` | ID of parent (post or comment), e.g. `t3_xxx` or `t1_xxx`. |
| `link_id` | Post ID (e.g. `t3_xxx`). |

### 6.2 Engagement

| Field | Description |
|-------|-------------|
| `score` | Net score. |
| `ups` | Upvotes. |
| `downs` | Downvotes (often hidden). |
| `total_awards_received` | Awards. |
| `controversiality` | Controversy flag. |

### 6.3 Time

| Field | Description |
|-------|-------------|
| `created_utc` | Created (UTC unix). |
| `created` | Created (local unix). |
| `edited` | Edit time or `false`. |

### 6.4 Structure

| Field | Description |
|-------|-------------|
| `depth` | Nesting level (0 = top-level). |
| `replies` | Listing with `data.children` of nested comments. |
| `score_hidden` | Whether score is hidden. |

### 6.5 Moderation & state

| Field | Description |
|-------|-------------|
| `approved_by` | Approver. |
| `removed` | Removal flag. |
| `stickied` | Pinned in thread. |
| `locked` | Replies locked. |

---

## 7. Collection workflow (high level)

1. **Subreddit posts**: Fetch `/r/{subreddit}/.json` (with pagination via `after`).
2. **Per post**: From each post get `id` (or strip `t3_` from `name`) and `permalink`.
3. **Comment tree**: Fetch `https://www.reddit.com/r/{subreddit}/comments/{postid}/.../.json` (permalink or `{postid}/_/.json`).
4. **Parse**: Extract post from first listing; walk `replies` in second listing to build full comment tree.
5. **Store**: Save posts and comments (with parent/link IDs and depth) into structured storage (e.g. DuckDB).

Pipeline sketch:

```
subreddit.json  →  post list  →  for each post: comments/{id}.json  →  post + comment tree  →  DB
```

---

## 8. Limitations

- Unofficial; rate limits and behaviour can change.
- Vote counts (e.g. `ups`/`downs`) are sometimes obfuscated or hidden.
- Deep or large threads may be paginated or truncated.
- For very large or historical collection, consider Reddit’s official API or external datasets (e.g. Pushshift).

---

## 9. Minimal dataset (reminder)

Useful minimal set for analytics:

- **Posts**: `id`, `title`, `author`, `subreddit`, `created_utc`, `score`, `upvote_ratio`, `num_comments`, `post_type` (or `is_self`/`post_hint`), `url`, `subreddit_subscribers`.
- **Comments**: `id`, `link_id`, `parent_id`, `author`, `body`, `created_utc`, `score`, `depth` (and optionally `edited`, `total_awards_received`).

This file is the single reference for **what** we extract and **where** it comes from; execution details (scripts, scheduling, DB schema) will be added separately.
