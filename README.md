# Faceless Channel Tracker — reliable setup

This fixes the duplicate problem. The old way had the AI *guess* whether a channel
already existed (fuzzy search). The new way: the AI just finds channels, and a small
script checks for duplicates **exactly** and writes the new ones. No more guessing,
no more duplicates.

## How it works (simple version)

1. The Claude routine runs at 5am and finds channels on NexLev (same as today).
2. It saves them to a file called `candidates.json`.
3. It runs `python notion_writer.py`.
4. The script reads every Channel ID already in your Notion DB, throws out anything
   that's already there, and writes only the truly new ones — printing the real
   page IDs Notion gives back.

The script never fakes a write. If it can't write, the routine turns red instead of
lying that it succeeded.

## One-time setup

### 1. Make a Notion integration token (2 minutes)
- Go to https://www.notion.so/my-integrations → **New integration** → name it
  "Faceless Tracker" → copy the **Internal Integration Secret** (starts with `ntn_`).
- Open your "📊 Faceless Channel Tracker" database → top-right **•••** → **Connections**
  → add the integration you just made. (If you skip this, the script sees an empty DB.)

### 2. Put this folder in a GitHub repo
- Create a new empty repo on github.com (e.g. `faceless-tracker`).
- Upload these files to it (`notion_writer.py`, `requirements.txt`, this README).

### 3. Attach the repo + token to your routine
- In Claude Code → your "Daily Niche Research" routine → edit.
- Attach the repo you just made.
- In the routine's **environment**, add a secret/variable:
  `NOTION_TOKEN = ntn_...your token...`
- Replace the routine instructions with `routine_prompt.md` (in this folder).

### 4. If the script can't reach Notion
The routine's cloud environment blocks unknown domains. If a run errors with
`403 host_not_allowed`, add `api.notion.com` to the environment's **Allowed domains**.

## candidates.json shape (what the routine writes for the script)

A list of objects like:

```json
[
  {
    "ytChannelId": "UCxxxx",
    "title": "Channel Name",
    "channelCreationDate": "2026-05-01",
    "outlierScore": 3.4,
    "discoverySource": "Vidrush Scan",
    "category": { "name": "History" },
    "tags": ["history"],
    "stats": {
      "subscribers": 12000,
      "monthlyViews": 800000,
      "monthlyRevenue": 2100.50,
      "avgVideoLength": 900,
      "rpm": { "total": 4.2 }
    },
    "lastUploadedVideos": [
      { "videoId": "abc123", "viewCount": 50000 }
    ]
  }
]
```

Missing fields are fine — the script only writes what's present, and always leaves
`Doability` blank for you.
