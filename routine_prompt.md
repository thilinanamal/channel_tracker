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
  **CRITICAL — where the channel id is:** this tool does NOT return a `ytChannelId`.
  Its top-level `id` is a NexLev DB row id (e.g. `474890`), NOT a YouTube id — never
  use it. The real YouTube id lives ONLY in the `url` field
  (`https://youtube.com/channel/UC...`); parse the `UC...` out of `url` and use THAT
  as `ytChannelId`. (This is the exception to the "don't reconstruct from URL" rule
  below, which applies only to `search_niche_finder_channels`.) Every id you carry
  forward must start with `UC` — if it starts with `DB_` or is a bare number, you
  grabbed the wrong field and the writer will drop it.

**Sleep bucket**
- 5 semantic queries ("sleep stories", "sleep meditation", "bedtime history documentary
  narration", "calm long-form sleep narration", "relaxing sleep documentary"),
  faceless+monetized, last 90 days, minMonthlyViews 200000, minScore 0.35, paginate to page 2.
- `find_outlier_faceless_channels` minOutlierScore ≥ 1.5, keep only sleep-tagged + ≤90 days.
- Tag all `discoverySource = "Sleep Scan"`.

### Step 2 — Clean the pool
- Merge both buckets, dedupe by ytChannelId (keep highest outlierScore on collision).
- **Preserve `ytChannelId` exactly as NexLev returns it.** For `search_niche_finder_channels`
  (Vidrush + Sleep scans) do NOT reconstruct it from a URL field — niche-finder results
  sometimes have a null URL, and rebuilding from URL is what silently dropped whole buckets
  before. Carry the raw id straight through. **EXCEPTION:** `find_outlier_faceless_channels`
  has no id field at all — its real YouTube id exists only inside `url`, so for that tool you
  MUST parse the `UC...` out of `url` (see Step 1). Either way, every `ytChannelId` must be a
  real YouTube id starting with `UC`; never carry a `DB_...` / numeric NexLev db id forward.
- Drop disqualifiers: created >90 days ago, **monthly views < 500,000 (ALL buckets)**,
  not monetized, missing channel id, (Vidrush only) avg length outside 600–2400s.
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
- The script independently enforces the 500,000-view floor and drops missing-id rows,
  and prints how many it dropped for each reason. If "Dropped (missing id)" is large,
  a bucket was lost upstream — treat that as a problem to investigate, not a clean run.
- DO NOT push changes to GitHub. This routine is for discovery and Notion writes only.
  Any local `candidates.json` or `notion_writer.py` fixes belong in manual commits/PRs.
  The routine should end after the Notion writer completes.