#!/usr/bin/env python3
"""
Fetch the FULL player pool (prices, positions, ownership) from the official
FIFA Fantasy game and merge it into players.json.

Why: the hand-picked 71-player pool can miss cheap enablers and differentials.
The official game serves its complete player list as JSON; this script tries
the known endpoint patterns and merges whatever it finds.

Usage:
    python fetch_pool.py            # fetch + merge into players.json
    python fetch_pool.py --dry-run  # show what would change, don't write

Note: play.fifa.com sits behind a CDN that blocks datacenter IPs (HTTP 403),
so this script may only work from a residential connection. Run it locally,
then commit the updated players.json. Hand-maintained stats in
enrich_stats.py are preserved — this only syncs price/ownership/pool.
"""

import json
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Endpoint patterns used by FIFA's fantasy games (the 2022 edition exposed
# /services/api/... JSON feeds; 2026 paths may differ — all are attempted).
CANDIDATE_ENDPOINTS = [
    "https://play.fifa.com/json/fantasy/players.json",
    "https://play.fifa.com/services/api/fantasy/players",
    "https://fantasy.fifa.com/services/api/gameplay/players",
    "https://play.fifa.com/api/fantasy/v1/players",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Accept": "application/json",
}

POS_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD",
           "GK": "GK", "DEF": "DEF", "MID": "MID", "FWD": "FWD",
           "GOALKEEPER": "GK", "DEFENDER": "DEF",
           "MIDFIELDER": "MID", "FORWARD": "FWD"}


def fetch_raw_pool() -> list[dict] | None:
    for url in CANDIDATE_ENDPOINTS:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
                # Feeds wrap the list differently across editions
                if isinstance(data, list):
                    return data
                for key in ("players", "data", "elements", "Value"):
                    if isinstance(data.get(key), list):
                        return data[key]
        except Exception as e:
            print(f"  {url} → {e}", file=sys.stderr)
    return None


def normalize(raw: dict) -> dict | None:
    """Map one raw API player onto our players.json schema. Field names vary
    by edition, so try the known aliases for each attribute."""
    def first(*keys, default=None):
        for k in keys:
            if raw.get(k) is not None:
                return raw[k]
        return default

    name = first("pFName", "name", "web_name", "playerName")
    pos_raw = first("skill", "position", "element_type", "pos")
    price = first("value", "price", "now_cost", "cost")
    nation = first("cCode", "nation", "team_name", "country")
    ownership = first("selPer", "ownership", "selected_by_percent", default=0)
    if not name or pos_raw is None or price is None:
        return None
    pos = POS_MAP.get(pos_raw)
    if pos is None:
        return None
    price = float(price)
    if price > 25:  # some feeds use tenths of a million
        price /= 10
    ownership = float(ownership)
    if ownership > 1:  # percentage → fraction
        ownership /= 100
    return {"name": str(name), "pos": pos, "nation": str(nation),
            "price": round(price, 1), "ownership": round(ownership, 3)}


def merge(dry_run: bool = False) -> None:
    print("Fetching official player pool...")
    raw = fetch_raw_pool()
    if raw is None:
        print("\nCould not reach any FIFA fantasy endpoint (CDN likely blocks"
              " this network).\nRun this script from a residential connection,"
              " or update players.json manually.", file=sys.stderr)
        sys.exit(1)

    pool = [p for p in (normalize(r) for r in raw) if p]
    print(f"Fetched {len(pool)} players from the official game.")

    players_path = BASE_DIR / "players.json"
    pdata = json.loads(players_path.read_text())
    ours = {p["name"]: p for p in pdata["players"]}

    updated, added = 0, 0
    for p in pool:
        if p["name"] in ours:
            cur = ours[p["name"]]
            if cur["price"] != p["price"] or cur.get("ownership") != p["ownership"]:
                print(f"  update {p['name']}: ${cur['price']}m→${p['price']}m, "
                      f"own {cur.get('ownership', 0):.0%}→{p['ownership']:.0%}")
                cur["price"], cur["ownership"] = p["price"], p["ownership"]
                updated += 1
        else:
            p.update({"group": None, "xp": 0.0, "xp_md": [0, 0, 0],
                      "notes": "auto-imported from official pool"})
            pdata["players"].append(p)
            added += 1

    print(f"\n{updated} updated, {added} added "
          f"(pool now {len(pdata['players'])} players).")
    if added:
        print("New players need 'group' set and stats in enrich_stats.py, "
              "then re-run: python enrich_stats.py")
    if dry_run:
        print("Dry run — nothing written.")
        return
    players_path.write_text(json.dumps(pdata, indent=2, ensure_ascii=False))
    print("players.json written.")


if __name__ == "__main__":
    merge(dry_run="--dry-run" in sys.argv)
