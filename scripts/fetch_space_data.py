#!/usr/bin/env python3
"""
XTROBE - Nightly Space Events & ISS Tracker JSON Generator
Fetches launches, events, news, and ISS TLE data → saves to data/ directory
"""

import requests
import json
from datetime import datetime, timedelta, timezone
import os
import time

OUTPUT_DIR = "./data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {"User-Agent": "XTROBE-Space-Calendar-Nightly-Job/1.0"}


# ==============================================================================
# 🛰️ ISS TLE DATA FETCHER
# This function grabs the daily orbital rules (Two-Line Element set) for the ISS.
# It saves it to 'iss_data.json' so the frontend can calculate live GPS coordinates.
# ==============================================================================
def fetch_iss_tle():
    print("🛰️ Fetching ISS TLE data...")
    url = "https://celestrak.org/NORAD/elements/stations.txt"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        
        # The text file has 3 lines per satellite. The ISS is the first 3 lines.
        lines = response.text.split('\n')
        
        iss_data = {
            "name": lines[0].strip(),
            "tle_line1": lines[1].strip(),
            "tle_line2": lines[2].strip(),
            "fetched_at": datetime.now(timezone.utc).isoformat()
        }
        
        path = os.path.join(OUTPUT_DIR, "iss_data.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(iss_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved ISS TLE data → {path}")
        
    except Exception as e:
        print(f"❌ Failed to fetch ISS TLE: {e}")
# ==============================================================================


def fetch_paginated(start_url, max_pages=3):
    results = []
    url = start_url
    pages = 0

    while url and pages < max_pages:
        try:
            print(f"  → Fetching: {url}")
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            data = r.json()
            results.extend(data.get("results", []))
            url = data.get("next")
            pages += 1
            time.sleep(1)
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Request error: {e}")
            break
        except json.JSONDecodeError:
            print("  ❌ JSON parse error (API may be down)")
            break

    return results


def main():
    print("🚀 XTROBE nightly fetch started...")

    # 1. Fetch ISS Data first
    fetch_iss_tle()

    # 2. Setup dates for launches, events, and news
    today         = datetime.now(timezone.utc).isoformat()[:10]
    thirty_ago    = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()[:10]
    ten_ago       = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()[:10]

    # 3. Fetch Launches
    print("📡 Fetching launches...")
    launches = fetch_paginated(
        f"https://ll.thespacedevs.com/2.2.0/launch/?limit=100&net__gte={today}&mode=detailed",
        max_pages=4
    )

    # 4. Fetch Events
    print("📡 Fetching space events...")
    events = fetch_paginated(
        f"https://ll.thespacedevs.com/2.2.0/event/?limit=100&date__gte={thirty_ago}",
        max_pages=2
    )

    # 5. Fetch News
    print("📡 Fetching news...")
    news = fetch_paginated(
        f"https://api.spaceflightnewsapi.net/v4/articles/?limit=100&published_at__gte={ten_ago}",
        max_pages=2
    )

    # 6. Process and compile the main events list
    all_events = []

    for l in launches:
        net = l.get("net") or l.get("window_start")
        vid_urls = l.get("vidURLs") or []
        webcast = l.get("webcast_live") or (vid_urls[0].get("url") if vid_urls else None)
        all_events.append({
            "id":          f"launch_{l.get('id')}",
            "type":        "launch",
            "title":       l.get("name", "Unknown Launch"),
            "date":        net,
            "provider":    l.get("launch_service_provider", {}).get("name", "Unknown"),
            "rocket":      l.get("rocket", {}).get("configuration", {}).get("name", ""),
            "mission":     l.get("mission", {}).get("name", "") if l.get("mission") else "",
            "description": l.get("mission", {}).get("description", "Rocket launch") if l.get("mission") else "Rocket launch",
            "pad":         l.get("pad", {}).get("name", ""),
            "status":      l.get("status", {}).get("name", "TBD"),
            "probability": l.get("probability"),
            "webcast":     webcast,
            "image":       l.get("image"),
            "link":        l.get("url"),
            "source":      "Launch Library 2"
        })

    for e in events:
        all_events.append({
            "id":          f"event_{e.get('id')}",
            "type":        "event",
            "title":       e.get("name", "Space Event"),
            "date":        e.get("date"),
            "description": e.get("description", ""),
            "location":    e.get("location"),
            "image":       e.get("feature_image"),
            "link":        e.get("url"),
            "source":      "Launch Library 2"
        })

    for n in news:
        all_events.append({
            "id":        f"news_{n.get('id')}",
            "type":      "news",
            "title":     n.get("title"),
            "date":      n.get("published_at"),
            "summary":   n.get("summary", ""),
            "image":     n.get("image_url"),
            "link":      n.get("url"),
            "news_site": n.get("news_site"),
            "source":    "Spaceflight News API"
        })

    # Sort everything chronologically
    all_events.sort(key=lambda x: x["date"] if x["date"] else "")

    # Final Output Structure for Events/News
    output = {
        "schema":                "xtrobe-v1",
        "generated_at":          datetime.now(timezone.utc).isoformat(),
        "total_events_captured": len(all_events),
        "events":                all_events
    }

    # Save Events/News JSON
    path = os.path.join(OUTPUT_DIR, "rockets_space_events.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved {len(all_events)} items → {path}")
    except IOError as e:
        print(f"❌ File write error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
