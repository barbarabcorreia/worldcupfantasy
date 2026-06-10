#!/usr/bin/env python3
"""
FIFA World Cup Fantasy 2026 — Team Optimizer
Selects the optimal 15-player squad under the $100m budget using a
greedy + local-search approach (no external dependencies required).

Expected points are now computed by scoring.py using per-game stats
(goals/90, assists/90, SoT/90, key passes/90, tackles/90, saves/90)
and per-match clean sheet probabilities from fixtures.json.
"""

import json
import sys
from pathlib import Path
from collections import Counter
from scoring import calc_xp_group_stage, calc_xp_per_game, describe_scoring

BASE_DIR = Path(__file__).parent

# Weight of bench xp in the squad objective. Only the XI scores, but a bench
# with some xp covers rotation/injury risk and the 12th Man chip.
BENCH_WEIGHT = 0.15
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


def get_cs_probs_for_player(player: dict, fixtures: dict) -> list[float]:
    """Return [cs_md1, cs_md2, cs_md3] for a player from fixtures cs_prob data."""
    if not fixtures or "groups" not in fixtures:
        return [0.30, 0.30, 0.30]
    group_id = player.get("group")
    if not group_id:
        return [0.30, 0.30, 0.30]
    nation = player["nation"]
    group = fixtures["groups"].get(group_id, {})
    probs = {}
    for fix in group.get("fixtures", []):
        if fix["home"] == nation or fix["away"] == nation:
            md = fix["md"]
            cs = fix.get("cs_prob", {}).get(nation, 0.30)
            probs[md] = cs
    return [probs.get(1, 0.30), probs.get(2, 0.30), probs.get(3, 0.30)]


def get_difficulties_for_player(player: dict, fixtures: dict) -> list[int]:
    """Return [diff_md1, diff_md2, diff_md3] for a player from fixtures."""
    if not fixtures or "groups" not in fixtures:
        return [3, 3, 3]
    group_id = player.get("group")
    if not group_id:
        return [3, 3, 3]
    nation = player["nation"]
    group = fixtures["groups"].get(group_id, {})
    diffs = {}
    for fix in group.get("fixtures", []):
        if fix["home"] == nation or fix["away"] == nation:
            diffs[fix["md"]] = fix["difficulty"].get(nation, 3)
    return [diffs.get(1, 3), diffs.get(2, 3), diffs.get(3, 3)]


def compute_player_xp(player: dict, fixtures: dict) -> float:
    """
    Compute expected group-stage points using the scoring engine if stats
    are available, else fall back to the hand-estimated player['xp'].
    """
    if player.get("stats"):
        cs_probs = get_cs_probs_for_player(player, fixtures)
        difficulties = get_difficulties_for_player(player, fixtures)
        return calc_xp_group_stage(player, cs_probs, difficulties)
    return player.get("xp", 0.0)


def player_md_xp(player: dict, fixtures: dict, md: int) -> float:
    """Expected points for one specific matchday (1-3)."""
    if not player.get("stats"):
        return round(player.get("xp", 0.0) / 3, 2)
    cs = get_cs_probs_for_player(player, fixtures)[md - 1]
    diff = get_difficulties_for_player(player, fixtures)[md - 1]
    return calc_xp_per_game(player, cs, diff)


def load_data(players_path: str | None = None, fixtures_path: str | None = None):
    pp = Path(players_path) if players_path else BASE_DIR / "players.json"
    fp = Path(fixtures_path) if fixtures_path else BASE_DIR / "fixtures.json"
    pdata = json.loads(pp.read_text())
    fdata = json.loads(fp.read_text()) if fp.exists() else {}
    # Recompute xp for all players that have stats
    for p in pdata["players"]:
        p["xp"] = compute_player_xp(p, fdata)
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

    def squad_value(s):
        """Objective: starting XI xp + captain doubling + weighted bench.
        Only the XI scores points, and the captain scores double — a flat
        15-player sum would waste budget on bench players."""
        xi, bench = pick_starting_xi(s)
        xi_xp = sum(p["xp"] for p in xi)
        captain_xp = max(p["xp"] for p in xi)
        return xi_xp + captain_xp + BENCH_WEIGHT * sum(p["xp"] for p in bench)

    # Candidate pools for swap moves: top by xp (XI upgrades) plus the
    # cheapest few (bench enablers that free budget for the XI).
    swap_cands: dict[str, list[dict]] = {}
    for pos in req:
        by_xp = sorted(by_pos[pos], key=lambda p: p["xp"], reverse=True)[:12]
        by_price = sorted(by_pos[pos], key=lambda p: p["price"])[:6]
        seen, pool = set(), []
        for p in by_xp + by_price:
            if p["name"] not in seen:
                seen.add(p["name"])
                pool.append(p)
        swap_cands[pos] = pool

    def single_swap_improve(squad):
        improved, current = True, list(squad)
        while improved:
            improved = False
            cur_val = squad_value(current)
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
                    if squad_value(new_squad) > cur_val + 0.001:
                        current = new_squad
                        improved = True
                        break
                if improved:
                    break
        return current

    def two_swap_improve(squad):
        """Replace two players at once. Escapes the single-swap trap where
        an XI upgrade is only affordable by also downgrading a bench spot."""
        current = list(squad)
        cur_val = squad_value(current)
        n = len(current)
        for i in range(n):
            for j in range(i + 1, n):
                pi, pj = current[i], current[j]
                rest = [p for k, p in enumerate(current) if k not in (i, j)]
                rest_cost = sum(p["price"] for p in rest)
                rest_names = {p["name"] for p in rest}
                nations_rest = Counter(p["nation"] for p in rest)
                for a in swap_cands[pi["pos"]]:
                    if a["name"] in rest_names:
                        continue
                    for b in swap_cands[pj["pos"]]:
                        if b["name"] in rest_names or b["name"] == a["name"]:
                            continue
                        if rest_cost + a["price"] + b["price"] > budget + 0.001:
                            continue
                        nations = nations_rest.copy()
                        nations[a["nation"]] += 1
                        nations[b["nation"]] += 1
                        if any(c > max_per_nation for c in nations.values()):
                            continue
                        new_squad = rest + [a, b]
                        if squad_value(new_squad) > cur_val + 0.001:
                            return new_squad, True
        return current, False

    def improve(squad):
        current = list(squad)
        while True:
            current = single_swap_improve(current)
            current, changed = two_swap_improve(current)
            if not changed:
                return current

    best_squad, best_score = None, -1.0
    for seed in seeds:
        improved = improve(seed)
        score = squad_value(improved)
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


def suggest_transfers(squad, players, fixtures, meta, top_n=3):
    """For each upcoming matchday, rank the best single transfers
    (1 free transfer per matchday) by xp gained over the remaining games."""
    bank = meta["budget"] - sum(p["price"] for p in squad)
    squad_names = {p["name"] for p in squad}
    plans = []
    for label, window in [("Before MD2 (gain over MD2+MD3)", [2, 3]),
                          ("Before MD3 (gain over MD3)", [3])]:
        options = []
        for out_p in squad:
            out_val = sum(player_md_xp(out_p, fixtures, m) for m in window)
            nations = Counter(q["nation"] for q in squad if q["name"] != out_p["name"])
            for in_p in players:
                if in_p["pos"] != out_p["pos"] or in_p["name"] in squad_names:
                    continue
                if in_p["price"] > out_p["price"] + bank + 0.001:
                    continue
                if nations.get(in_p["nation"], 0) >= meta["max_per_nation"]:
                    continue
                gain = sum(player_md_xp(in_p, fixtures, m) for m in window) - out_val
                if gain > 0.5:
                    options.append((gain, out_p, in_p))
        options.sort(key=lambda t: -t[0])
        plans.append((label, options[:top_n]))
    return plans


def top_differentials(players, squad, max_ownership=0.10, top_n=5):
    """Low-ownership players ranked by leverage (xp × share of rivals
    who DON'T own them). These gain the most rank when they haul."""
    cands = [p for p in players if p.get("ownership", 1.0) < max_ownership]
    squad_names = {p["name"] for p in squad}
    ranked = sorted(cands, key=lambda p: p["xp"] * (1 - p.get("ownership", 0)), reverse=True)
    return [(p, p["name"] in squad_names) for p in ranked[:top_n]]


def fmt(p, extra=""):
    flag = FLAGS.get(p["nation"], "🌍")
    return f"  {p['pos']:3s} | {flag} {p['nation']:15s} | ${p['price']:.1f}m | xp {p['xp']:4.1f} | {p['name']}{extra}"


def print_team(meta: dict, squad: list[dict], fixtures: dict, players: list[dict]) -> None:
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
    print("  FIXTURE GUIDE — Starting XI by matchday expected points (stats-driven)")
    print("  " + "-" * 68)
    print(f"  {'Player':22s} | {'MD1':20s} | {'MD2':20s} | {'MD3':20s}")
    print("  " + "-" * 68)
    for p in sorted(xi, key=lambda x: x["xp"], reverse=True):
        fixs = get_player_fixtures(p, fixtures)
        fix_map = {f["md"]: f for f in fixs}
        cells = []
        for md in [1, 2, 3]:
            f = fix_map.get(md)
            xp_game = player_md_xp(p, fixtures, md)
            opp = f["opponent"][:9] if f else "?"
            cells.append(f"vs {opp:9s} {xp_game:.1f}pt")
        print(f"  {p['name']:22s} | {cells[0]:20s} | {cells[1]:20s} | {cells[2]:20s}")

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

    # --- Transfer plan ---
    plans = suggest_transfers(squad, players, fixtures, meta)
    print()
    print("  TRANSFER PLAN (1 free transfer per matchday, rollable once)")
    print("  " + "-" * 68)
    any_plan = False
    for label, options in plans:
        if not options:
            continue
        any_plan = True
        print(f"  {label}:")
        for gain, out_p, in_p in options:
            print(f"    OUT {out_p['name']:20s} → IN {in_p['name']:20s} (+{gain:.1f} xp)")
    if not any_plan:
        print("  No transfer beats the current squad by >0.5 xp — hold your free")
        print("  transfer and roll it over to react to injuries/suspensions.")

    # --- Differentials ---
    diffs = top_differentials(players, squad)
    if diffs:
        print()
        print("  DIFFERENTIALS (<10% owned — big rank gains when they haul)")
        print("  " + "-" * 68)
        for p, in_squad in diffs:
            own = p.get("ownership", 0) * 100
            tag = "  ← in your squad" if in_squad else ""
            print(f"    {p['name']:22s} {p['pos']:3s} ${p['price']:.1f}m  "
                  f"xp {p['xp']:5.1f}  own {own:4.1f}%{tag}")

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
    parser.add_argument("--scoring",  action="store_true", help="Print scoring table and exit")
    parser.add_argument("--differential", action="store_true",
                        help="Optimize leverage-adjusted xp (downweights highly-owned "
                             "players) — for chasing rank in a league, not max points")
    args = parser.parse_args()

    if args.scoring:
        print(describe_scoring())
        return

    meta, players, fixtures = load_data(args.data, args.fixtures)
    if args.budget:
        meta["budget"] = args.budget

    if args.differential:
        # Discount xp by ownership: a haul from a player everyone owns barely
        # moves your rank. Capped so superstars stay viable as captains.
        for p in players:
            p["xp"] = round(p["xp"] * (1 - 0.5 * min(p.get("ownership", 0.0), 0.6)), 2)
        print("Differential mode: xp discounted by ownership.\n", file=sys.stderr)

    print("Optimizing squad...\n", file=sys.stderr)
    squad = optimize(meta, players)

    if args.json:
        xi, bench = pick_starting_xi(squad)
        captain = max(xi, key=lambda p: p["xp"])
        plans = suggest_transfers(squad, players, fixtures, meta)
        print(json.dumps({
            "squad": squad, "starting_xi": xi, "bench": bench,
            "captain": captain,
            "total_cost": round(sum(p["price"] for p in squad), 1),
            "xi_xp": round(sum(p["xp"] for p in xi), 1),
            "clashes": find_head_to_head_clashes(squad, fixtures),
            "transfer_plan": [
                {"window": label,
                 "options": [{"out": o["name"], "in": i["name"], "gain": round(g, 1)}
                             for g, o, i in opts]}
                for label, opts in plans
            ],
        }, indent=2))
    else:
        print_team(meta, squad, fixtures, players)


if __name__ == "__main__":
    main()
