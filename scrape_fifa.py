#!/usr/bin/env python3
"""
scrape_fifa.py — pull the FULL FIFA World Cup Fantasy player pool + points
from play.fifa.com using a real, logged-in browser (Playwright).

WHY THIS (and not fetch_pool.py): the plain HTTP fetcher gets 403'd from
datacenter IPs and can't log in. A real browser on YOUR home connection,
with YOUR session, sees exactly what the website sees — every player's
price, ownership, and points.

WHAT IT DOES
  1. Opens a visible Chromium window at the Fantasy site.
  2. You log in manually (handles 2FA / cookie walls), then press Enter.
  3. It captures the game's internal player-data API responses as you
     browse to the player list, AND probes known endpoints using your
     authenticated session.
  4. Saves raw JSON to ./fifa_raw/ and the best player list to
     ./fifa_pool_raw.json, then prints the field names so the optimizer
     can be wired to the real 2026 schema.

SETUP + RUN (on your own computer, not a server):
    python3 -m venv .venv
    source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
    pip install playwright
    playwright install chromium
    python3 scrape_fifa.py
"""

import json
import re
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("Playwright not installed. Run:\n"
             "  pip install playwright\n"
             "  playwright install chromium")

BASE = Path(__file__).parent
RAW_DIR = BASE / "fifa_raw"
RAW_DIR.mkdir(exist_ok=True)
# Persists your login between runs so you don't re-auth every time.
# (git-ignored — it holds your session cookies, keep it off GitHub.)
PROFILE_DIR = BASE / ".fifa_browser_profile"

START_URL = "https://play.fifa.com/fantasy"

# Pages that make the frontend load the full player pool:
POOL_URLS = [
    "https://play.fifa.com/fantasy/transfers",
    "https://play.fifa.com/fantasy/statistics",
    "https://play.fifa.com/fantasy/players",
]

# Same candidate endpoints as fetch_pool.py, but probed WITH your cookies:
CANDIDATE_ENDPOINTS = [
    "https://play.fifa.com/json/fantasy/players.json",
    "https://play.fifa.com/services/api/fantasy/players",
    "https://fantasy.fifa.com/services/api/gameplay/players",
    "https://play.fifa.com/api/fantasy/v1/players",
]

PLAYER_KEYS = ("players", "data", "elements", "Value", "items", "results", "list")
PLAYER_FIELD_HINTS = ("pFName", "name", "web_name", "playerName",
                      "skill", "position", "pos", "value", "price")


def find_player_list(obj, depth=0):
    """Heuristically locate a list of player dicts anywhere in the JSON."""
    if depth > 6:
        return None

    def is_player_list(lst):
        return (isinstance(lst, list) and len(lst) > 20
                and isinstance(lst[0], dict)
                and any(k in lst[0] for k in PLAYER_FIELD_HINTS))

    if is_player_list(obj):
        return obj
    if isinstance(obj, dict):
        for k in PLAYER_KEYS:
            if is_player_list(obj.get(k)):
                return obj[k]
        for v in obj.values():
            if isinstance(v, (dict, list)):
                found = find_player_list(v, depth + 1)
                if found:
                    return found
    elif isinstance(obj, list):
        for v in obj[:5]:            # only peek at the first few entries
            if isinstance(v, (dict, list)):
                found = find_player_list(v, depth + 1)
                if found:
                    return found
    return None


def safe_name(url):
    return re.sub(r"[^a-zA-Z0-9]+", "_", url)[:120]


captured = []   # (url, player_list)


def on_response(resp):
    if "json" not in resp.headers.get("content-type", "").lower():
        return
    try:
        data = resp.json()
    except Exception:
        return
    players = find_player_list(data)
    if players:
        captured.append((resp.url, players))
        (RAW_DIR / f"{safe_name(resp.url)}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ captured {len(players)} players from {resp.url}")


def main():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=False,
            viewport={"width": 1280, "height": 900})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.on("response", on_response)

        print("Opening the Fantasy site...")
        page.goto(START_URL, wait_until="domcontentloaded")

        print("\n" + "=" * 64)
        print("  LOG IN in the browser window if you're not already.")
        print("  Make sure you can see your team / the game loads.")
        print("=" * 64)
        input("\nPress Enter HERE once you're logged in... ")

        # Trigger the pool to load by visiting player-heavy pages.
        for url in POOL_URLS:
            try:
                print(f"Loading {url} ...")
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(2)
            except Exception as e:
                print(f"  (skipped {url}: {e})")

        # Probe known API endpoints using the authenticated session.
        for url in CANDIDATE_ENDPOINTS:
            try:
                r = ctx.request.get(url, timeout=15000)
                if r.ok and "json" in r.headers.get("content-type", "").lower():
                    players = find_player_list(r.json())
                    if players:
                        captured.append((url, players))
                        (RAW_DIR / f"{safe_name(url)}.json").write_text(
                            r.text(), encoding="utf-8")
                        print(f"  ✓ endpoint {url} -> {len(players)} players")
                else:
                    print(f"  endpoint {url} -> HTTP {r.status}")
            except Exception as e:
                print(f"  endpoint {url} -> {e}")

        ctx.close()

    if not captured:
        print("\nNo player data captured. Two things you can do:")
        print("  1. Open ./fifa_raw to see what JSON the site returned.")
        print("  2. In the browser, open DevTools > Network, click the")
        print("     player list, and tell me the request URL you see.")
        sys.exit(1)

    url, pool = max(captured, key=lambda c: len(c[1]))
    (BASE / "fifa_pool_raw.json").write_text(
        json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 64}")
    print(f"  SUCCESS: {len(pool)} players from {url}")
    print(f"  Wrote fifa_pool_raw.json")
    print(f"  Sample record fields: {list(pool[0].keys())}")
    print(f"{'=' * 64}")
    print("\nNext: commit fifa_pool_raw.json (or paste the 'Sample record")
    print("fields' line above) and I'll map it into players.json + the optimizer.")


if __name__ == "__main__":
    main()
