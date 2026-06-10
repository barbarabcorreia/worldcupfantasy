#!/usr/bin/env python3
"""
FIFA World Cup Fantasy 2026 — Team Optimizer
Selects the optimal 15-player squad under the $100m budget using a
greedy + local-search approach (no external dependencies required).
"""

import json
import sys
from pathlib import Path
from collections import Counter

BASE_DIR = Path(__file__).parent
FLAGS = {
    "Norway": "🇳🇴", "France": "🇫🇷", "Brazil": "🇧🇷", "Egypt": "🇪🇬",
    "Portugal": "🇵🇹", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Spain": "🇪🇸", "Germany": "🇩🇪",
    "Belgium": "🇧🇪", "Senegal": "🇸🇳", "Morocco": "🇲🇦", "Netherlands": "🇳🇱",
    "Argentina": "🇦🇷", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Uruguay": "🇺🇾", "Poland": "🇵🇱",
    "Switzerland": "🇨🇭", "Colombia": "🇨🇴", "Canada": "🇨🇦", "USA": "🇺🇸",
    "Czechia": "🇨🇿", "Guinea": "🇬🇳", "Ivory Coast": "🇨🇮", "Ghana": "🇬🇭",
    "Mexico": "🇲🇽", "Japan": "🇯🇵", "Croatia": "🇭🇷", "Austria": "🇦🇹",
}
DIFF_LABEL = {1: "★★★★★ very easy", 2: "★★★★☆ easy", 3: "★★★☆☆ medium",
              4: "★★☆☆☆ hard", 5: "★☆☆☆☆ very hard"}


def load_data(players_path: str | None = None, fixtures_path: str | None = None):
    pp = Path(players_path) if players_path else BASE_DIR / "players.json"
    fp = Path(fixtures_path) if fixtures_path else BASE_DIR / "fixtures.json"
    pdata = json.loads(pp.read_text())
    fdata = json.loads(fp.read_text()) if fp.exists() else {}
    return pdata["meta"], pdata["players"], fdata


def get_player_fixtures(player: dict, fixtures: dict) -> list[dict]:
    """Return list of {md, date, opponent, difficulty} for a player's nation."""
    if not fixtures or "groups" not in fixtures:
        return []
    group_id = player.get("group")
    if not group_id:
        return []
    group = fixtures["groups"].get(group_id, {})
    nation = player["nation"]
    result = []
    for fix in group.get("fixtures", []):
        if fix["home"] == nation or fix["away"] == nation:
            opponent = fix["away"] if fix["home"] == nation else fix["home"]
            diff = fix["difficulty"].get(nation, 3)
            result.append({"md": fix["md"], "date": fix["date"], "opponent": opponent, "difficulty": diff})
    return sorted(result, key=lambda x: x["md"])


def find_head_to_head_clashes(squad: list[dict], fixtures: dict) -> list[str]:
    """Detect pairs of players in the squad who face each other in the group stage."""
    clashes = []
    if not fixtures or "groups" not in fixtures:
        return clashes
    for group_id, group in fixtures["groups"].items():
        nations_in_squad = [p["nation"] for p in squad if p.get("group") == group_id]
        if len(nations_in_squad) < 2:
            continue
        for fix in group.get("fixtures", []):
            home, away = fix["home"], fix["away"]
            if home in nations_in_squad and away in nations_in_squad:
                home_players = [p["name"] for p in squad if p["nation"] == home]
                away_players = [p["name"] for p in squad if p["nation"] == away]
                date = fix["date"]
                md = fix["md"]
                clashes.append(
                    f"MD{md} ({date}): {', '.join(home_players)} ({home}) vs "
                    f"{', '.join(away_players)} ({away})"
                )
    return clashes


def is_valid_squad(squad: list[dict], meta: dict) -> tuple[bool, str]:
    req = meta["positions"]
    counts = {pos: sum(1 for p in squad if p["pos"] == pos) for pos in req}
    for pos, needed in req.items():
        if counts.get(pos, 0) != needed:
            return False, f"Need {needed} {pos}, have {counts.get(pos, 0)}"
    total_cost = sum(p["price"] for p in squad)
    if total_cost > meta["budget"] + 0.001:
        return False, f"Over budget: ${total_cost:.1f}m > ${meta['budget']}m"
    nation_counts = Counter(p["nation"] for p in squad)
    for nation, cnt in nation_counts.items():
        if cnt > meta["max_per_nation"]:
            return False, f"Too many from {nation}: {cnt} > {meta['max_per_nation']}"
    return True, "OK"


def optimize(meta: dict, players: list[dict]) -> list[dict]:
    req = meta["positions"]
    budget = meta["budget"]
    max_per_nation = meta["max_per_nation"]

    by_pos: dict[str, list[dict]] = {}
    for pos in req:
        by_pos[pos] = sorted(
            [p for p in players if p["pos"] == pos],
            key=lambda p: p["xp"] / p["price"],
            reverse=True,
        )

    def min_future_cost(pos_order, pos_idx, picks_done, excluded):
        total = 0.0
        for i, future_pos in enumerate(pos_order[pos_idx:]):
            future_needed = req[future_pos] - (picks_done + 1 if i == 0 else 0)
            if future_needed <= 0:
                continue
            avail = sorted(p["price"] for p in players if p["pos"] == future_pos and p not in excluded)
            if len(avail) < future_needed:
                return float("inf")
            total += sum(avail[:future_needed])
        return total

    def greedy_build(pos_order):
        squad, remaining, nation_counts = [], budget, {}
        for pi, pos in enumerate(pos_order):
            needed = req[pos]
            candidates = [p for p in by_pos[pos] if p not in squad]
            picks = 0
            for candidate in candidates:
                if picks == needed:
                    break
                if candidate["price"] > remaining:
                    continue
                if nation_counts.get(candidate["nation"], 0) >= max_per_nation:
                    continue
                future = min_future_cost(pos_order, pi, picks, squad + [candidate])
                if candidate["price"] + future > remaining + 0.001:
                    continue
                squad.append(candidate)
                remaining -= candidate["price"]
                nation_counts[candidate["nation"]] = nation_counts.get(candidate["nation"], 0) + 1
                picks += 1
            if picks < needed:
                return None
        return squad

    orderings = [
        ["GK", "DEF", "MID", "FWD"], ["FWD", "MID", "DEF", "GK"],
        ["MID", "FWD", "DEF", "GK"], ["FWD", "DEF", "MID", "GK"],
        ["GK", "FWD", "MID", "DEF"], ["DEF", "MID", "FWD", "GK"],
    ]
    seeds = [s for o in orderings if (s := greedy_build(o)) is not None]

    if not seeds:
        cheapest = []
        for pos, n in req.items():
            cheapest.extend(sorted([p for p in players if p["pos"] == pos], key=lambda p: p["price"])[:n])
        if is_valid_squad(cheapest, meta)[0]:
            seeds = [cheapest]

    if not seeds:
        raise RuntimeError("Could not build a valid squad. Check players.json data.")

    def squad_xp(s): return sum(p["xp"] for p in s)

    def swap_improve(squad):
        improved, current = True, list(squad)
        while improved:
            improved = False
            for i, player in enumerate(current):
                pos = player["pos"]
                squad_without = [p for j, p in enumerate(current) if j != i]
                remaining = budget - sum(p["price"] for p in squad_without)
                nations_without = Counter(p["nation"] for p in squad_without)
                for candidate in by_pos[pos]:
                    if candidate in squad_without:
                        continue
                    if candidate["price"] > remaining + 0.001:
                        continue
                    if nations_without.get(candidate["nation"], 0) >= max_per_nation:
                        continue
                    new_squad = squad_without + [candidate]
                    if squad_xp(new_squad) > squad_xp(current) + 0.001:
                        current = new_squad
                        improved = True
                        break
        return current

    best_squad, best_score = None, -1.0
    for seed in seeds:
        improved = swap_improve(seed)
        score = squad_xp(improved)
        if score > best_score:
            valid, _ = is_valid_squad(improved, meta)
            if valid:
                best_squad, best_score = improved, score

    return best_squad


def pick_starting_xi(squad):
    gks  = sorted([p for p in squad if p["pos"] == "GK"],  key=lambda p: p["xp"], reverse=True)
    defs = sorted([p for p in squad if p["pos"] == "DEF"], key=lambda p: p["xp"], reverse=True)
    mids = sorted([p for p in squad if p["pos"] == "MID"], key=lambda p: p["xp"], reverse=True)
    fwds = sorted([p for p in squad if p["pos"] == "FWD"], key=lambda p: p["xp"], reverse=True)

    best_xi, best_xp = None, -1.0
    for n_def in range(3, 6):
        for n_mid in range(2, 6):
            n_fwd = 11 - 1 - n_def - n_mid
            if n_fwd < 1 or n_fwd > 3:
                continue
            if n_def > len(defs) or n_mid > len(mids) or n_fwd > len(fwds):
                continue
            xi = [gks[0]] + defs[:n_def] + mids[:n_mid] + fwds[:n_fwd]
            xp = sum(p["xp"] for p in xi)
            if xp > best_xp:
                best_xp, best_xi = xp, xi
    bench = [p for p in squad if p not in best_xi]
    return best_xi, bench


def fmt(p, extra=""):
    flag = FLAGS.get(p["nation"], "🌍")
    return f"  {p['pos']:3s} | {flag} {p['nation']:15s} | ${p['price']:.1f}m | xp {p['xp']:4.1f} | {p['name']}{extra}"


def print_team(meta: dict, squad: list[dict], fixtures: dict) -> None:
    xi, bench = pick_starting_xi(squad)
    captain = max(xi, key=lambda p: p["xp"])
    vice    = sorted([p for p in xi if p != captain], key=lambda p: p["xp"], reverse=True)[0]

    total_cost = sum(p["price"] for p in squad)
    xi_xp = sum(p["xp"] for p in xi)

    print("=" * 72)
    print("  FIFA WORLD CUP FANTASY 2026 — OPTIMAL SQUAD")
    print("=" * 72)
    print(f"  Total squad cost : ${total_cost:.1f}m  (budget ${meta['budget']}m, ${meta['budget']-total_cost:.1f}m free)")
    print(f"  Starting XI xp   : {xi_xp:.1f} expected points")
    print(f"  Captain          : {captain['name']} (×2 pts)")
    print(f"  Vice-captain     : {vice['name']}")
    print()

    # --- Starting XI ---
    print("  STARTING XI")
    print("  " + "-" * 68)
    print(f"  {'POS':3s} | {'NATION':17s} | {'PRICE':6s} | {'XP':6s} | NAME")
    print("  " + "-" * 68)
    for pos_label, pos_code in [("GOALKEEPER","GK"),("DEFENDERS","DEF"),("MIDFIELDERS","MID"),("FORWARDS","FWD")]:
        pos_players = sorted([p for p in xi if p["pos"] == pos_code], key=lambda x: x["xp"], reverse=True)
        if pos_players:
            print(f"\n  [{pos_label}]")
            for p in pos_players:
                tag = " ★ CAPTAIN" if p == captain else (" © VICE" if p == vice else "")
                print(fmt(p, tag))

    print()
    print("  BENCH (4 players)")
    print("  " + "-" * 68)
    for p in sorted(bench, key=lambda x: x["xp"], reverse=True):
        print(fmt(p))

    # --- Per-Matchday Fixture Guide ---
    print()
    print("  FIXTURE GUIDE — Starting XI by matchday expected points")
    print("  " + "-" * 68)
    print(f"  {'Player':22s} | {'MD1 (pts)':18s} | {'MD2 (pts)':18s} | {'MD3 (pts)':18s}")
    print("  " + "-" * 68)
    for p in sorted(xi, key=lambda x: x["xp"], reverse=True):
        fixs = get_player_fixtures(p, fixtures)
        fix_map = {f["md"]: f for f in fixs}
        xp_md = p.get("xp_md", [None, None, None])
        cells = []
        for md in [1, 2, 3]:
            f = fix_map.get(md)
            pts = xp_md[md-1] if len(xp_md) > md-1 else "?"
            if f:
                diff_str = "●" * (6 - f["difficulty"]) + "○" * (f["difficulty"] - 1)
                cells.append(f"vs {f['opponent'][:10]:10s} {pts}")
            else:
                cells.append(f"{'?':10s} {pts}")
        print(f"  {p['name']:22s} | {cells[0]:18s} | {cells[1]:18s} | {cells[2]:18s}")

    # --- Captain Live-Switch Strategy ---
    print()
    print("  CAPTAIN LIVE-SWITCH STRATEGY")
    print("  " + "-" * 68)
    print("  The matchday LOCKS when the FIRST game of each round kicks off:")
    locks = meta.get("matchday_locks", {}) or fixtures.get("matchday_locks", {})
    for md_key in ["MD1", "MD2", "MD3"]:
        lock = locks.get(md_key, "TBC")
        print(f"    {md_key} lock: {lock}")
    print()
    print("  After lock, you can still switch captain to any player whose game")
    print("  hasn't started yet. Use this order of games to decide:")
    print()

    if fixtures and "groups" in fixtures:
        # Collect all game dates for XI players in MD1
        game_slots = {}
        for p in xi:
            fixs = get_player_fixtures(p, fixtures)
            md1 = next((f for f in fixs if f["md"] == 1), None)
            if md1:
                date = md1["date"]
                if date not in game_slots:
                    game_slots[date] = []
                game_slots[date].append((p, md1))
        print(f"  {'Date':12s} {'Player':22s} {'Opponent':14s} {'Difficulty'}")
        print("  " + "-" * 68)
        for date in sorted(game_slots):
            for p, f in game_slots[date]:
                cap_tag = " ← captain?" if p["xp"] >= sorted(xi, key=lambda x: x["xp"])[-3]["xp"] else ""
                diff_stars = "★" * (6 - f["difficulty"])
                print(f"  {date:12s} {p['name']:22s} vs {f['opponent']:14s} {diff_stars}{cap_tag}")

    # --- Head-to-Head Clashes Warning ---
    clashes = find_head_to_head_clashes(squad, fixtures)
    if clashes:
        print()
        print("  ⚠  HEAD-TO-HEAD CLASHES IN YOUR SQUAD")
        print("  " + "-" * 68)
        print("  These players face each other — one will likely blank:")
        for c in clashes:
            print(f"    • {c}")
        print()
        print("  Strategy: use the live captain switch so you can assign")
        print("  captain to whoever is in better form BEFORE their game starts.")

    # --- Notes on key picks ---
    print()
    print("  KEY PICK NOTES")
    print("  " + "-" * 68)
    for p in sorted(xi, key=lambda x: x["xp"], reverse=True)[:6]:
        print(f"  • {p['name']}: {p.get('notes','')}")

    # --- Booster chips ---
    print()
    print("  BOOSTER CHIP STRATEGY (5 chips, one at a time)")
    print("  " + "-" * 68)
    print("  1. Maximum Captain   — QF or SF when your best player has a weak opponent.")
    print("     Auto-assigns double to highest XI scorer, so no wrong guess.")
    print("  2. 12th Man          — Round of 32 (16 matches in one round).")
    print("     Max bench depth so every player contributes.")
    print("  3. Qualification Booster — Best in QF (+2 per player that advances).")
    print("     With a full 11 advancing = +22 free points.")
    print("  4. Wildcard          — After surprise group exits (MD2+).")
    print("     Not available in MD1 or before R32; overhaul the squad for free.")
    print("  5. Mystery Booster   — Revealed when Round of 32 opens. Evaluate then.")

    # --- Transfer rules ---
    print()
    print("  TRANSFER & TEAM CHANGE RULES")
    print("  " + "-" * 68)
    print("  • Before the tournament (before MD1 lock): unlimited free changes.")
    print("  • Group stage MD1-3 : 1 free transfer per matchday.")
    print("    You CAN roll 1 transfer over into the next matchday (except MD3 → R32).")
    print("    Extra transfers cost -3 pts each.")
    print("  • Round of 32+      : Unlimited free transfers each round.")
    print()
    print("  DAILY CHANGE RULES (important!):")
    print("  • Starting XI / formation: change freely BEFORE the matchday lock.")
    print("    Once the first game of a matchday kicks off → LOCKED until next round.")
    print("  • Captain: switch UNLIMITED TIMES before each player's game kicks off,")
    print("    even during a live matchday. Use the fixture guide above to time this.")
    print("  • Player transfers: counted per matchday, NOT per day. 1 free per round.")
    print("=" * 72)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="FIFA WC Fantasy 2026 Optimizer")
    parser.add_argument("--data",     help="Path to players.json", default=None)
    parser.add_argument("--fixtures", help="Path to fixtures.json", default=None)
    parser.add_argument("--budget",   type=float, help="Override budget (default 100.0)", default=None)
    parser.add_argument("--json",     action="store_true", help="Output JSON instead of formatted text")
    args = parser.parse_args()

    meta, players, fixtures = load_data(args.data, args.fixtures)
    if args.budget:
        meta["budget"] = args.budget

    print("Optimizing squad...\n", file=sys.stderr)
    squad = optimize(meta, players)

    if args.json:
        xi, bench = pick_starting_xi(squad)
        captain = max(xi, key=lambda p: p["xp"])
        print(json.dumps({
            "squad": squad, "starting_xi": xi, "bench": bench,
            "captain": captain,
            "total_cost": round(sum(p["price"] for p in squad), 1),
            "xi_xp": round(sum(p["xp"] for p in xi), 1),
            "clashes": find_head_to_head_clashes(squad, fixtures),
        }, indent=2))
    else:
        print_team(meta, squad, fixtures)


if __name__ == "__main__":
    main()
