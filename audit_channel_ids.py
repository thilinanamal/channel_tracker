#!/usr/bin/env python3
"""
audit_channel_ids.py  (run once, by hand)
-----------------------------------------
Scans your Notion tracker and flags any Channel IDs that don't look clean,
so the first run of notion_writer.py doesn't re-add them as false "new" rows.

It only READS. It changes nothing. You fix anything it flags by hand in Notion.

A clean YouTube channel id looks like:  UC + 22 more characters  (24 total, e.g. UCxxxxxxxxxxxxxxxxxxxxxx)

Run:  NOTION_TOKEN=ntn_... python audit_channel_ids.py
"""

import os
import re
import sys

import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "b9c3445e-c9e9-4ed4-a8f2-f2eeb1b1db66")
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# A well-formed channel id: starts with UC, then 22 chars of [A-Za-z0-9_-], 24 total.
CLEAN = re.compile(r"^UC[A-Za-z0-9_-]{22}$")


def main():
    if not NOTION_TOKEN:
        print("FATAL: set NOTION_TOKEN", file=sys.stderr)
        sys.exit(1)

    rows, cursor = [], None
    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor
        r = requests.post(
            f"https://api.notion.com/v1/databases/{DATABASE_ID}/query",
            headers=HEADERS, json=payload, timeout=30,
        )
        if r.status_code != 200:
            print(f"FATAL query {r.status_code}: {r.text[:300]}", file=sys.stderr)
            sys.exit(1)
        data = r.json()
        rows.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")

    flagged, seen, dupes = [], {}, []
    for row in rows:
        name_prop = row.get("properties", {}).get("Channel Name", {}).get("title", [])
        name = name_prop[0].get("plain_text") if name_prop else "(no name)"
        url = row.get("url", "")
        raw = "".join(
            t.get("plain_text", "")
            for t in row.get("properties", {}).get("Channel ID", {}).get("rich_text", [])
        )
        stripped = raw.strip()

        problems = []
        if not stripped:
            problems.append("EMPTY")
        else:
            if raw != stripped:
                problems.append("has spaces")
            if "/" in stripped or "youtube.com" in stripped.lower():
                problems.append("looks like a URL, not an id")
            if not CLEAN.match(stripped):
                problems.append("doesn't match UC+22 format")
            # duplicate detection (same id stored twice)
            key = stripped.lower()
            if key in seen:
                dupes.append((name, stripped, seen[key], url))
            else:
                seen[key] = name

        if problems:
            flagged.append((name, repr(raw), ", ".join(problems), url))

    print(f"Scanned {len(rows)} row(s).\n")

    if flagged:
        print(f"--- {len(flagged)} row(s) with messy Channel IDs (fix these by hand) ---")
        for name, raw, why, url in flagged:
            print(f"  • {name}\n      stored: {raw}\n      issue : {why}\n      page  : {url}\n")
    else:
        print("No messy Channel IDs found. ✅")

    if dupes:
        print(f"--- {len(dupes)} duplicate id(s) already in the DB ---")
        for name, cid, first, url in dupes:
            print(f"  • {cid}: '{name}' duplicates '{first}'  ({url})")
    else:
        print("No existing duplicates found. ✅")

    print("\nDone. This script changed nothing — fix flagged rows in Notion manually.")


if __name__ == "__main__":
    main()
