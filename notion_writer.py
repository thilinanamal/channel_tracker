#!/usr/bin/env python3
"""
notion_writer.py
----------------
The reliable half of the Faceless Channel Tracker.

What it does (and does NOT do):
  - READS every existing "Channel ID" already in your Notion database (exact, all rows).
  - Compares today's candidates against them in memory (no fuzzy search, no guessing).
  - WRITES only the genuinely new channels as REAL pages via Notion's official REST API.
  - Prints the REAL page ids Notion returns. It never fakes a write. (Honors §0.)

It does NOT discover channels. The Claude routine still does NexLev discovery and
drops the candidates into candidates.json next to this script. This script only
handles the part the routine keeps getting wrong: dedup + writing.

Setup needs ONE secret: NOTION_TOKEN  (a Notion internal integration token).
Run:  python notion_writer.py
Input file: candidates.json  (a list of channel objects, shape described in README)
"""

import json
import os
import sys
from datetime import date, datetime

import requests

# ---- Config -------------------------------------------------------------
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "b9c3445e-c9e9-4ed4-a8f2-f2eeb1b1db66")
NOTION_VERSION = "2022-06-28"
CANDIDATES_FILE = os.environ.get("CANDIDATES_FILE", "candidates.json")
BODY_NOTE = "Revenue, RPM, and view figures are Nexlev estimates."

NICHE_OPTIONS = {
    "history", "crime", "sleep", "science", "wildlife", "health", "politics",
    "travel", "tech", "finance", "life stories", "celebrity", "movies", "other",
}

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


# ---- Helpers ------------------------------------------------------------
def die(msg):
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(1)


def mmss(seconds):
    try:
        s = int(round(float(seconds)))
    except (TypeError, ValueError):
        return ""
    return f"{s // 60:02d}:{s % 60:02d}"


def pick_niche(channel):
    """Map tags/category to one allowed Niche option, else 'Other'."""
    candidates = []
    cat = channel.get("category")
    if isinstance(cat, dict):
        candidates.append(cat.get("name", ""))
    candidates.append(channel.get("googleTrendsKeyword", ""))
    candidates.extend(channel.get("tags", []) or [])
    for c in candidates:
        if isinstance(c, str) and c.strip().lower() in NICHE_OPTIONS:
            # return with the canonical casing from the schema
            low = c.strip().lower()
            return low.title() if low != "life stories" else "Life Stories"
    return "Other"


def best_video(channel):
    """Return (url, views) of the highest-view recent video, or (None, None)."""
    vids = channel.get("lastUploadedVideos") or []
    best = None
    for v in vids:
        views = v.get("viewCount") or v.get("views") or 0
        try:
            views = int(views)
        except (TypeError, ValueError):
            views = 0
        if best is None or views > best[1]:
            vid_id = v.get("videoId") or v.get("id")
            if vid_id:
                best = (f"https://www.youtube.com/watch?v={vid_id}", views)
    return best if best else (None, None)


def channel_age_days(created):
    try:
        d = datetime.fromisoformat(str(created)[:10]).date()
        return (date.today() - d).days
    except Exception:
        return None


# ---- Read existing Channel IDs (exact, all rows, paginated) -------------
def fetch_existing_channel_ids():
    known = set()
    cursor = None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers=HEADERS, json=payload, timeout=30,
        )
        if r.status_code != 200:
            die(f"Could not query Notion ({r.status_code}): {r.text[:300]}")
        data = r.json()
        for row in data.get("results", []):
            prop = row.get("properties", {}).get("Channel ID", {})
            for t in prop.get("rich_text", []):
                txt = (t.get("plain_text") or "").strip()
                if txt:
                    known.add(txt)
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return known


# ---- Build one Notion page payload --------------------------------------
def build_page(channel):
    cid = str(channel["ytChannelId"]).strip()
    age = channel_age_days(channel.get("channelCreationDate"))
    outlier = float(channel.get("outlierScore") or 0)
    viral = (outlier >= 3) and (age is not None and age <= 45)
    stats = channel.get("stats", {}) or {}
    bv_url, bv_views = best_video(channel)

    props = {
        "Channel Name": {"title": [{"text": {"content": str(channel.get("title", "Untitled"))}}]},
        "Channel ID": {"rich_text": [{"text": {"content": cid}}]},
        "Channel URL": {"url": f"https://www.youtube.com/channel/{cid}"},
        "Outlier Score": {"number": round(outlier, 2)},
        "Discovery Source": {"select": {"name": channel.get("discoverySource", "Vidrush Scan")}},
        "Niche": {"select": {"name": pick_niche(channel)}},
        "Viral Flag": {"checkbox": viral},
        "Date Added": {"date": {"start": date.today().isoformat()}},
    }
    if age is not None:
        props["Channel Age (days)"] = {"number": age}
    if stats.get("subscribers") is not None:
        props["Subscribers"] = {"number": int(stats["subscribers"])}
    if stats.get("monthlyViews") is not None:
        props["Monthly Views"] = {"number": int(stats["monthlyViews"])}
    rpm = (stats.get("rpm") or {}).get("total") if isinstance(stats.get("rpm"), dict) else stats.get("rpm")
    if rpm is not None:
        props["RPM ($)"] = {"number": round(float(rpm), 2)}
    if stats.get("monthlyRevenue") is not None:
        props["Est Monthly Rev ($)"] = {"number": round(float(stats["monthlyRevenue"]), 2)}
    if stats.get("avgVideoLength") is not None:
        props["Avg Video Length"] = {"rich_text": [{"text": {"content": mmss(stats["avgVideoLength"])}}]}
    if bv_url:
        props["Best Video URL"] = {"url": bv_url}
        props["Best Video Views"] = {"number": int(bv_views)}

    # NOTE: 'Doability' is intentionally never set — left blank for your manual review.
    return {
        "parent": {"database_id": DATABASE_ID},
        "properties": props,
        "children": [{
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": BODY_NOTE}}]},
        }],
    }


def create_page(payload):
    r = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload, timeout=30)
    if r.status_code != 200:
        return None, f"{r.status_code}: {r.text[:300]}"
    return r.json().get("id"), None


# ---- Main ---------------------------------------------------------------
def main():
    if not NOTION_TOKEN:
        die("NOTION_TOKEN env var is missing. Set it in the routine environment.")
    if not os.path.exists(CANDIDATES_FILE):
        die(f"{CANDIDATES_FILE} not found. The routine must write it before this runs.")

    with open(CANDIDATES_FILE) as f:
        candidates = json.load(f)
    candidates = [c for c in candidates if c.get("ytChannelId")]

    print(f"Loaded {len(candidates)} candidate(s) from {CANDIDATES_FILE}")
    known = fetch_existing_channel_ids()
    print(f"Found {len(known)} channel(s) already in Notion")

    seen_this_run = set()
    new_channels = []
    for c in candidates:
        cid = str(c["ytChannelId"]).strip()
        if cid in known or cid in seen_this_run:
            continue
        seen_this_run.add(cid)
        new_channels.append(c)

    print(f"Genuinely new: {len(new_channels)}")

    created, failed = [], []
    for c in new_channels:
        page_id, err = create_page(build_page(c))
        if page_id:
            created.append((c.get("title"), page_id))
            print(f"  WROTE  {c.get('title')}  ->  {page_id}")
        else:
            failed.append((c.get("title"), err))
            print(f"  FAILED {c.get('title')}  ->  {err}")

    print("\n=== SUMMARY ===")
    print(f"Already in Notion (skipped): {len(candidates) - len(new_channels)}")
    print(f"New written (real page ids): {len(created)}")
    print(f"Write failures:              {len(failed)}")
    if failed:
        sys.exit(1)  # fail loudly so the routine shows red, not fake-green


if __name__ == "__main__":
    main()
