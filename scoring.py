"""
FIFA World Cup Fantasy 2026 — Official Scoring Engine

Complete scoring table sourced from play.fifa.com/fantasy/help/rules
and corroborated by multiple fantasy analysis sites.

Bonus stats are position-gated (confirmed from official sources):
  - Tackles (+1/3):        MID only
  - Chances created (+1/2): MID only
  - Shots on target (+1/2): FWD only
  - Saves (+1/3):           GK only
"""

from __future__ import annotations

SCORING_TABLE = {
    # Minutes played
    "played_u60":     {"GK": 1,  "DEF": 1,  "MID": 1,  "FWD": 1},
    "played_60plus":  {"GK": 2,  "DEF": 2,  "MID": 2,  "FWD": 2},
    # Goals
    "goal":           {"GK": 6,  "DEF": 6,  "MID": 5,  "FWD": 4},
    "goal_obx_bonus": {"GK": 1,  "DEF": 1,  "MID": 1,  "FWD": 1},  # outside box
    "goal_fk_bonus":  {"GK": 1,  "DEF": 1,  "MID": 1,  "FWD": 1},  # direct free kick
    # Assists
    "assist":         {"GK": 3,  "DEF": 3,  "MID": 3,  "FWD": 3},
    # Clean sheets (for 60+ min players)
    "clean_sheet":    {"GK": 5,  "DEF": 5,  "MID": 1,  "FWD": 0},
    # Goalkeeping
    "save_per_3":     {"GK": 1,  "DEF": 0,  "MID": 0,  "FWD": 0},
    "pen_save":       {"GK": 3,  "DEF": 0,  "MID": 0,  "FWD": 0},
    # Bonus stats (position-gated)
    "tackle_per_3":   {"GK": 0,  "DEF": 0,  "MID": 1,  "FWD": 0},   # MID only
    "chance_per_2":   {"GK": 0,  "DEF": 0,  "MID": 1,  "FWD": 0},   # MID only
    "sot_per_2":      {"GK": 0,  "DEF": 0,  "MID": 0,  "FWD": 1},   # FWD only
    # Penalty events
    "win_penalty":    {"GK": 2,  "DEF": 2,  "MID": 2,  "FWD": 2},
    "concede_penalty":{"GK": -1, "DEF": -1, "MID": -1, "FWD": -1},
    # Negative events
    "yellow":         {"GK": -1, "DEF": -1, "MID": -1, "FWD": -1},
    "red":            {"GK": -2, "DEF": -2, "MID": -2, "FWD": -2},
    "own_goal":       {"GK": -2, "DEF": -2, "MID": -2, "FWD": -2},
    "miss_penalty":   {"GK": -2, "DEF": -2, "MID": -2, "FWD": -2},
    # Bonuses
    "potm":           {"GK": 3,  "DEF": 3,  "MID": 3,  "FWD": 3},
    "scouting_bonus": {"GK": 2,  "DEF": 2,  "MID": 2,  "FWD": 2},  # <5% owned, >4pts
}


DEFAULT_STATS = {
    # Typical values per 90 min for an average starter (fallback)
    "goals_p90":    0.20,
    "assists_p90":  0.15,
    "sot_p90":      1.50,   # shots on target (FWD/MID)
    "kp_p90":       1.00,   # key passes / chances created (MID)
    "tackles_p90":  1.50,   # tackles (MID)
    "saves_p90":    2.50,   # GK
    "pen_taker":    False,
    "fk_taker":     False,
    "start_prob":   0.85,   # probability of starting (vs being benched/injured)
    "min_60_prob":  0.80,   # P(plays 60+ | starts)
    "yellow_p90":   0.15,
    "obx_ratio":    0.20,   # fraction of goals scored from outside the box
    "win_pen_p90":  0.02,   # probability of winning a penalty per 90
}


def pts(action: str, pos: str) -> float:
    return SCORING_TABLE[action].get(pos, 0)


# Difficulty multiplier for outfield attacking output (goals, assists).
# difficulty 1 = very easy → +30% more, difficulty 5 = very hard → -30% less
DIFFICULTY_MULT = {1: 1.30, 2: 1.12, 3: 1.00, 4: 0.85, 5: 0.70}

# GK save volume moves the OPPOSITE way: harder opponent → more shots faced.
SAVES_MULT = {1: 0.75, 2: 0.88, 3: 1.00, 4: 1.15, 5: 1.30}

# Penalty event rates
PEN_ATTEMPT_PG = 0.115  # attempts per game for a team's designated taker
PEN_CONVERT    = 0.78   # conversion rate → 0.09 pen goals/game (taker)
PEN_FACED_PG   = 0.10   # penalties faced by a GK per game
PEN_SAVE_RATE  = 0.22   # share of faced penalties saved

# ---------------------------------------------------------------------------
# Shrinkage: observed per-90 rates come from small samples (6-10 qualifiers,
# often vs weak opposition). Blend each volume stat toward a positional prior
# so the model doesn't over-trust two or three hot data points.
# ---------------------------------------------------------------------------
SHRINK = 0.35  # weight on the prior (0 = trust data fully, 1 = ignore data)

POSITION_PRIORS = {
    "GK":  {"goals_p90": 0.00, "assists_p90": 0.01, "sot_p90": 0.00,
            "kp_p90": 0.05, "tackles_p90": 0.05, "saves_p90": 2.60},
    "DEF": {"goals_p90": 0.08, "assists_p90": 0.12, "sot_p90": 0.30,
            "kp_p90": 0.60, "tackles_p90": 1.40, "saves_p90": 0.00},
    "MID": {"goals_p90": 0.25, "assists_p90": 0.25, "sot_p90": 1.30,
            "kp_p90": 1.80, "tackles_p90": 1.60, "saves_p90": 0.00},
    "FWD": {"goals_p90": 0.45, "assists_p90": 0.20, "sot_p90": 2.00,
            "kp_p90": 1.00, "tackles_p90": 0.70, "saves_p90": 0.00},
}


def effective_stats(player: dict) -> dict:
    """Merge player stats over defaults, then shrink volume rates toward
    the positional prior. Probabilities and flags are left untouched."""
    s = {**DEFAULT_STATS, **player.get("stats", {})}
    prior = POSITION_PRIORS.get(player["pos"], {})
    for key, prior_val in prior.items():
        s[key] = (1 - SHRINK) * s[key] + SHRINK * prior_val
    return s


def calc_xp_per_game(player: dict, cs_prob: float, difficulty: int = 3) -> float:
    """
    Expected fantasy points for ONE game given a clean sheet probability
    and fixture difficulty (1=very easy … 5=very hard).

    player must have a 'stats' dict with per-game rates. Missing keys fall
    back to DEFAULT_STATS; volume rates are shrunk toward positional priors.
    """
    pos = player["pos"]
    s = effective_stats(player)
    att_mult = DIFFICULTY_MULT.get(difficulty, 1.0)  # scale goals/assists by fixture

    start_p   = s["start_prob"]
    min60_p   = s["min_60_prob"]
    goals_pg  = s["goals_p90"]
    assists_pg = s["assists_p90"]
    sot_pg    = s["sot_p90"]
    kp_pg     = s["kp_p90"]
    tackles_pg = s["tackles_p90"]
    saves_pg  = s["saves_p90"]
    yellow_pg = s["yellow_p90"]
    obx_r     = s["obx_ratio"]
    pen_taker = s["pen_taker"]
    fk_taker  = s["fk_taker"]
    win_pen_pg = s["win_pen_p90"]

    # Expected minutes per start: starters subbed off early produce less.
    # All volume stats (goals, assists, SoT, KP, tackles, saves) are prorated.
    exp_min = min60_p * 88 + (1 - min60_p) * 45
    vol = start_p * (exp_min / 90.0)

    pen_goals_pg = PEN_ATTEMPT_PG * PEN_CONVERT if pen_taker else 0.0
    pen_miss_pg  = PEN_ATTEMPT_PG * (1 - PEN_CONVERT) if pen_taker else 0.0
    fk_goals_pg  = 0.04 if fk_taker else 0.0
    total_goals  = goals_pg + pen_goals_pg

    xp = 0.0

    # Minutes
    xp += start_p * (min60_p * pts("played_60plus", pos) + (1 - min60_p) * pts("played_u60", pos))

    # Goals (basic) — scaled by fixture difficulty
    g = total_goals * att_mult
    goal_pt = pts("goal", pos)
    xp += vol * (g - fk_goals_pg - g * obx_r) * goal_pt
    xp += vol * g * obx_r * (goal_pt + pts("goal_obx_bonus", pos))
    xp += vol * fk_goals_pg * (goal_pt + pts("goal_fk_bonus", pos))

    # Missed penalties (takers attempt ~0.115/game, ~22% missed)
    xp += vol * pen_miss_pg * att_mult * pts("miss_penalty", pos)

    # Assists — scaled by fixture difficulty
    xp += vol * (assists_pg * att_mult) * pts("assist", pos)

    # Clean sheet (only if plays 60+ min)
    cs_pt = pts("clean_sheet", pos)
    if cs_pt > 0:
        xp += start_p * min60_p * cs_prob * cs_pt

    # GK: saves scale UP with difficulty (more shots faced), plus pen saves
    if pos == "GK":
        save_mult = SAVES_MULT.get(difficulty, 1.0)
        xp += vol * (saves_pg * save_mult / 3) * pts("save_per_3", pos)
        xp += start_p * PEN_FACED_PG * PEN_SAVE_RATE * pts("pen_save", pos)

    # MID: tackles + chances created bonuses
    if pos == "MID":
        xp += vol * (tackles_pg / 3) * pts("tackle_per_3", pos)
        xp += vol * (kp_pg / 2) * pts("chance_per_2", pos)

    # FWD: shots on target bonus
    if pos == "FWD":
        xp += vol * (sot_pg * att_mult / 2) * pts("sot_per_2", pos)

    # Winning a penalty
    xp += vol * win_pen_pg * pts("win_penalty", pos)

    # Yellow card
    xp += start_p * yellow_pg * pts("yellow", pos)

    # Scouting Bonus: +2 if <5% owned and scores >4 pts in the game.
    # P(>4 pts) approximated from the game's expected points.
    ownership = player.get("ownership", 1.0)
    if ownership < 0.05:
        p_haul = max(0.0, min(0.6, (xp - 2.5) / 8.0))
        xp += pts("scouting_bonus", pos) * p_haul

    return round(xp, 3)


def calc_xp_group_stage(
    player: dict,
    game_cs_probs: list[float],
    difficulties: list[int] | None = None,
) -> float:
    """
    Expected fantasy points for ALL 3 group stage games.
    game_cs_probs: [cs_prob_md1, cs_prob_md2, cs_prob_md3]
    difficulties:  [diff_md1, diff_md2, diff_md3]  (1=very easy … 5=very hard)
    """
    diffs = difficulties if difficulties else [3, 3, 3]
    total = 0.0
    for cs_prob, diff in zip(game_cs_probs, diffs):
        total += calc_xp_per_game(player, cs_prob, diff)
    return round(total, 2)


def describe_scoring() -> str:
    lines = [
        "FIFA WORLD CUP FANTASY 2026 — COMPLETE SCORING TABLE",
        "=" * 60,
        f"{'Action':<30} {'GK':>4} {'DEF':>4} {'MID':>4} {'FWD':>4}",
        "-" * 60,
    ]
    labels = {
        "played_u60":       "Playing (<60 min)",
        "played_60plus":    "Playing (60+ min)",
        "goal":             "Goal scored",
        "goal_obx_bonus":   "Goal outside box (bonus)",
        "goal_fk_bonus":    "Goal direct free-kick (bonus)",
        "assist":           "Assist",
        "clean_sheet":      "Clean sheet (60+ min)",
        "save_per_3":       "Every 3 saves",
        "pen_save":         "Penalty saved",
        "tackle_per_3":     "Every 3 tackles",
        "chance_per_2":     "Every 2 chances created",
        "sot_per_2":        "Every 2 shots on target",
        "win_penalty":      "Winning a penalty",
        "concede_penalty":  "Conceding a penalty",
        "yellow":           "Yellow card",
        "red":              "Red card",
        "own_goal":         "Own goal",
        "miss_penalty":     "Missed penalty",
        "potm":             "Player of the Match",
        "scouting_bonus":   "Scouting Bonus (<5% owned, >4pts)",
    }
    for key, label in labels.items():
        row = SCORING_TABLE[key]
        gk  = row.get("GK",  0)
        de  = row.get("DEF", 0)
        mi  = row.get("MID", 0)
        fw  = row.get("FWD", 0)
        if gk == de == mi == fw:
            val = f"{gk:+d}" if gk != 0 else "  —"
            lines.append(f"  {label:<28} {val:>4} {val:>4} {val:>4} {val:>4}")
        else:
            def fmt(v): return f"{v:+d}" if v != 0 else "  —"
            lines.append(f"  {label:<28} {fmt(gk):>4} {fmt(de):>4} {fmt(mi):>4} {fmt(fw):>4}")
    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe_scoring())
