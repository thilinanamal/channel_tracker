# Faceless Channel Daily Tracker — Routine (script-backed)

**Goal:** Each day, find high-performing faceless YouTube channels on NexLev, save them
to `candidates.json`, then run `notion_writer.py`, which does EXACT dedup and writes only
genuinely new channels to Notion. Duplicates are handled by the script, not by you.

## YOUR JOB (the agent)

You do discovery only. You do NOT decide duplicates and you do NOT call notion-create-pages.
The script handles all Notion writing reliably.

### Step 1 — Discover candidates on NexLev
Run the two buckets exactly as before:

**Vidrush bucket**
- `search_niche_finder_channels` query `"*"`, faceless+monetized, created in last 90 days,
  minMonthlyViews 500000, avg length 600–2400s, not shorts-only. Paginate to page 2.
  Tag each `discoverySource = "Vidrush Scan"`.
- `find_outlier_faceless_channels` minOutlierScore ≥ 1.5. Keep only created ≤ 90 days,
  drop sleep/meditation/calm/bedtime tags, drop avg length <600 or >2400s.
  Tag `discoverySource = "Outlier Pass"`.

**Sleep bucket**
- 5 semantic queries ("sleep stories", "sleep meditation", "bedtime history documentary
  narration", "calm long-form sleep narration", "relaxing sleep documentary"),
  faceless+monetized, last 90 days, minMonthlyViews 200000, minScore 0.35, paginate to page 2.
- `find_outlier_faceless_channels` minOutlierScore ≥ 1.5, keep only sleep-tagged + ≤90 days.
- Tag all `discoverySource = "Sleep Scan"`.

### Step 2 — Clean the pool
- Merge both buckets, dedupe by ytChannelId (keep highest outlierScore on collision).
- Drop disqualifiers: created >90 days ago, monthlyViews 0/missing, not monetized,
  missing channel id, (Vidrush only) avg length outside 600–2400s.
- Sleep bucket: keep top 5 by outlierScore — EXCEPT any channel with outlierScore ≥ 3
  AND age ≤ 45 days, which always stays.

### Step 3 — Write candidates.json
Save the surviving channels to `candidates.json` in the repo root, each as:
`ytChannelId, title, channelCreationDate, outlierScore, discoverySource, category, tags,
stats{subscribers, monthlyViews, monthlyRevenue, avgVideoLength, rpm}, lastUploadedVideos[]`

### Step 4 — Run the writer (this is the real write)
Run in the shell:

    pip install -r requirements.txt
    python notion_writer.py

The script reads all existing Channel IDs from Notion, skips anything already there,
and writes ONLY new channels as real pages — printing the real page ids. It leaves
`Doability` blank for your manual review and sets Viral Flag automatically.

### Step 5 — Report honestly
Repeat the script's printed SUMMARY (skipped / new written / failures). If the script
exits with an error, the run is a FAILURE — say so, do not report success.

## Hard rules
- Do NOT call notion-create-pages yourself. The script is the only writer.
- Do NOT touch the `Doability` field anywhere.
- Never report success unless `python notion_writer.py` finished without error.
