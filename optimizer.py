#!/usr/bin/env python3
"""
FIFA World Cup Fantasy 2026 — Team Optimizer
Selects the optimal 15-player squad under the $100m budget using a
greedy + local-search approach (no external dependencies required).
"""

import json
import sys
import itertools
from pathlib import Path

BASE_DIR = Path(__file__).parent


def load_players(path: str | None = None) -> tuple[dict, list[dict]]:
    p = Path(path) if path else BASE_DIR / "players.json"
    data = json.loads(p.read_text())
    return data["meta"], data["players"]


def is_valid_squad(squad: list[dict], meta: dict) -> tuple[bool, str]:
    req = meta["positions"]
    counts = {pos: sum(1 for p in squad if p["pos"] == pos) for pos in req}
    for pos, needed in req.items():
        if counts.get(pos, 0) != needed:
            return False, f"Need {needed} {pos}, have {counts.get(pos, 0)}"

    total_cost = sum(p["price"] for p in squad)
    if total_cost > meta["budget"] + 0.001:
        return False, f"Over budget: ${total_cost:.1f}m > ${meta['budget']}m"

    # Nation limit
    from collections import Counter
    nation_counts = Counter(p["nation"] for p in squad)
    for nation, cnt in nation_counts.items():
        if cnt > meta["max_per_nation"]:
            return False, f"Too many from {nation}: {cnt} > {meta['max_per_nation']}"

    return True, "OK"


def nation_count(squad: list[dict], nation: str) -> int:
    return sum(1 for p in squad if p["nation"] == nation)


def optimize(meta: dict, players: list[dict]) -> list[dict]:
    req = meta["positions"]
    budget = meta["budget"]
    max_per_nation = meta["max_per_nation"]

    # Sort all players by value (xp / price) descending within each position
    by_pos: dict[str, list[dict]] = {}
    for pos in req:
        by_pos[pos] = sorted(
            [p for p in players if p["pos"] == pos],
            key=lambda p: p["xp"] / p["price"],
            reverse=True,
        )

    best_squad: list[dict] | None = None
    best_score = -1.0

    # Precompute cheapest-n prices per position (for lookahead)
    cheapest_prices: dict[str, list[float]] = {
        pos: sorted(p["price"] for p in players if p["pos"] == pos)
        for pos in req
    }

    def min_future_cost(pos_order: list[str], pos_idx: int, picks_done: int, excluded: list[dict]) -> float:
        """Minimum budget needed to fill remaining slots after current pick."""
        total = 0.0
        for future_pos in pos_order[pos_idx:]:
            future_needed = req[future_pos]
            if future_pos == pos_order[pos_idx]:
                future_needed -= picks_done + 1  # slots still needed in current pos
            if future_needed <= 0:
                continue
            avail = sorted(
                p["price"] for p in players
                if p["pos"] == future_pos and p not in excluded
            )
            if len(avail) < future_needed:
                return float("inf")
            total += sum(avail[:future_needed])
        return total

    # Phase 1: greedy seed with lookahead — pick best value players per position
    # while ensuring enough budget remains for remaining required slots.
    def greedy_build(pos_order: list[str]) -> list[dict] | None:
        squad: list[dict] = []
        remaining_budget = budget
        nation_counts: dict[str, int] = {}

        for pi, pos in enumerate(pos_order):
            needed = req[pos]
            candidates = [p for p in by_pos[pos] if p not in squad]
            picks = 0
            for candidate in candidates:
                if picks == needed:
                    break
                if candidate["price"] > remaining_budget:
                    continue
                if nation_counts.get(candidate["nation"], 0) >= max_per_nation:
                    continue
                # Lookahead: ensure remaining budget covers future required slots
                future = min_future_cost(pos_order, pi, picks, squad + [candidate])
                if candidate["price"] + future > remaining_budget + 0.001:
                    continue
                squad.append(candidate)
                remaining_budget -= candidate["price"]
                nation_counts[candidate["nation"]] = nation_counts.get(candidate["nation"], 0) + 1
                picks += 1
            if picks < needed:
                return None
        return squad

    # Try several position orderings to find good seeds
    pos_list = list(req.keys())
    orderings = [
        pos_list,
        list(reversed(pos_list)),
        ["FWD", "MID", "DEF", "GK"],
        ["GK", "DEF", "MID", "FWD"],
        ["MID", "FWD", "DEF", "GK"],
        ["FWD", "DEF", "MID", "GK"],
    ]
    seeds: list[list[dict]] = []
    for order in orderings:
        result = greedy_build(order)
        if result:
            seeds.append(result)

    if not seeds:
        # Fallback: pick cheapest valid squad as a seed for local search
        cheapest_squad: list[dict] = []
        for pos, n in req.items():
            pos_players = sorted([p for p in players if p["pos"] == pos], key=lambda p: p["price"])
            cheapest_squad.extend(pos_players[:n])
        if is_valid_squad(cheapest_squad, meta)[0]:
            seeds = [cheapest_squad]

    # Phase 2: local search — swap one player at a time to improve score
    def squad_xp(s: list[dict]) -> float:
        return sum(p["xp"] for p in s)

    def swap_improve(squad: list[dict]) -> list[dict]:
        improved = True
        current = list(squad)
        while improved:
            improved = False
            for i, player in enumerate(current):
                pos = player["pos"]
                squad_without = [p for j, p in enumerate(current) if j != i]
                remaining = budget - sum(p["price"] for p in squad_without)
                nations_without = {}
                for p in squad_without:
                    nations_without[p["nation"]] = nations_without.get(p["nation"], 0) + 1
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

    for seed in seeds:
        improved = swap_improve(seed)
        score = squad_xp(improved)
        if score > best_score:
            valid, msg = is_valid_squad(improved, meta)
            if valid:
                best_squad = improved
                best_score = score

    if best_squad is None:
        raise RuntimeError("Could not build a valid squad. Check players.json data.")

    return best_squad


def pick_starting_xi(squad: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (starting_xi, bench) picking the highest xp valid formation."""
    gks = sorted([p for p in squad if p["pos"] == "GK"], key=lambda p: p["xp"], reverse=True)
    defs = sorted([p for p in squad if p["pos"] == "DEF"], key=lambda p: p["xp"], reverse=True)
    mids = sorted([p for p in squad if p["pos"] == "MID"], key=lambda p: p["xp"], reverse=True)
    fwds = sorted([p for p in squad if p["pos"] == "FWD"], key=lambda p: p["xp"], reverse=True)

    best_xi = None
    best_xp = -1.0
    # Try all valid formations: 1 GK, 3-5 DEF, 2-5 MID, 1-3 FWD, total 11
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
                best_xp = xp
                best_xi = xi

    bench = [p for p in squad if p not in best_xi]
    return best_xi, bench


def pick_captain(xi: list[dict]) -> dict:
    return max(xi, key=lambda p: p["xp"])


def format_player(p: dict, extra: str = "") -> str:
    flag = {
        "Norway": "🇳🇴", "France": "🇫🇷", "Brazil": "🇧🇷", "Egypt": "🇪🇬",
        "Portugal": "🇵🇹", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "Spain": "🇪🇸", "Germany": "🇩🇪",
        "Belgium": "🇧🇪", "Senegal": "🇸🇳", "Morocco": "🇲🇦", "Netherlands": "🇳🇱",
        "Argentina": "🇦🇷", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Uruguay": "🇺🇾", "Poland": "🇵🇱",
        "Switzerland": "🇨🇭", "Colombia": "🇨🇴", "Canada": "🇨🇦", "USA": "🇺🇸",
        "Czechia": "🇨🇿", "Guinea": "🇬🇳", "Ivory Coast": "🇨🇮", "Ghana": "🇬🇭",
    }.get(p["nation"], "🌍")
    return f"  {p['pos']:3s} | {flag} {p['nation']:15s} | ${p['price']:.1f}m | xp {p['xp']:4.1f} | {p['name']}{extra}"


def print_team(meta: dict, squad: list[dict]) -> None:
    xi, bench = pick_starting_xi(squad)
    captain = pick_captain(xi)
    vice = sorted([p for p in xi if p != captain], key=lambda p: p["xp"], reverse=True)[0]

    total_cost = sum(p["price"] for p in squad)
    total_xp = sum(p["xp"] for p in xi)

    print("=" * 70)
    print("  FIFA WORLD CUP FANTASY 2026 — OPTIMAL SQUAD")
    print("=" * 70)
    print(f"  Total squad cost : ${total_cost:.1f}m  (budget ${meta['budget']}m, ${meta['budget']-total_cost:.1f}m remaining)")
    print(f"  Starting XI xp   : {total_xp:.1f} expected points")
    print(f"  Captain          : {captain['name']} (×2 pts)")
    print(f"  Vice-captain     : {vice['name']}")
    print()

    print("  STARTING XI")
    print("  " + "-" * 66)
    print(f"  {'POS':3s} | {'NATION':17s} | {'PRICE':6s} | {'XP':6s} | NAME")
    print("  " + "-" * 66)

    # Group by position for readability
    for pos_label, pos_code in [("GOALKEEPER", "GK"), ("DEFENDERS", "DEF"), ("MIDFIELDERS", "MID"), ("FORWARDS", "FWD")]:
        pos_players = [p for p in xi if p["pos"] == pos_code]
        if pos_players:
            print(f"\n  [{pos_label}]")
            for p in sorted(pos_players, key=lambda x: x["xp"], reverse=True):
                cap_tag = " ★ CAPTAIN" if p == captain else (" © vice-captain" if p == vice else "")
                print(format_player(p, cap_tag))

    print()
    print("  BENCH (4 players)")
    print("  " + "-" * 66)
    for p in sorted(bench, key=lambda x: x["xp"], reverse=True):
        print(format_player(p))

    print()
    print("  NOTES ON KEY PICKS")
    print("  " + "-" * 66)
    for p in sorted(xi, key=lambda x: x["xp"], reverse=True)[:5]:
        print(f"  • {p['name']}: {p.get('notes','')}")

    print()
    print("  BOOSTER CHIP STRATEGY")
    print("  " + "-" * 66)
    boosters = meta["boosters"]
    print("  1. Maximum Captain   — Use in the quarter-finals or semi-finals when")
    print("     your top player has a standout fixture. Auto-assigns the double.")
    print("  2. 12th Man          — Use in a matchday with a huge fixture list")
    print("     (e.g. Round of 32) so bench depth maximises your total score.")
    print("  3. Qualification Booster — Best used just before a knockout round")
    print("     when you're confident most of your XI will advance (+2 per player).")
    print("  4. Wildcard          — Available from Round 2 onwards; use after")
    print("     surprise early exits to overhaul your squad for free.")
    print("  5. Mystery Booster   — Revealed at Round of 32. Evaluate then.")
    print()
    print("  TRANSFER RULES")
    print("  " + "-" * 66)
    print("  • Group stage MD1-3 : 1 free transfer per matchday; rollovers allowed")
    print("    (except MD3 → Round of 32, where unlimited transfers kick in).")
    print("  • Round of 32+      : Unlimited free transfers each round.")
    print("=" * 70)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="FIFA WC Fantasy 2026 Optimizer")
    parser.add_argument("--data", help="Path to players.json", default=None)
    parser.add_argument("--budget", type=float, help="Override budget (default 100.0)", default=None)
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of formatted text")
    args = parser.parse_args()

    meta, players = load_players(args.data)
    if args.budget:
        meta["budget"] = args.budget

    print("Optimizing squad...\n", file=sys.stderr)
    squad = optimize(meta, players)

    if args.json:
        xi, bench = pick_starting_xi(squad)
        captain = pick_captain(xi)
        print(json.dumps({
            "squad": squad,
            "starting_xi": xi,
            "bench": bench,
            "captain": captain,
            "total_cost": round(sum(p["price"] for p in squad), 1),
            "xi_xp": round(sum(p["xp"] for p in xi), 1),
        }, indent=2))
    else:
        print_team(meta, squad)


if __name__ == "__main__":
    main()
