#!/usr/bin/env python3
"""
Unit tests for the scoring engine.

Run with:  python test_scoring.py   (or pytest test_scoring.py)

Exact-value tests pin the SCORING_TABLE to the official rules; behavioral
tests verify the xp model responds correctly to each input (clean sheets,
difficulty, minutes, penalties, ownership, shrinkage) without depending on
internal constants.
"""

from scoring import (
    SCORING_TABLE,
    POSITION_PRIORS,
    SHRINK,
    calc_xp_per_game,
    calc_xp_group_stage,
    effective_stats,
    pts,
)


def make_player(pos, ownership=0.50, **stats):
    base = {
        "start_prob": 1.0, "min_60_prob": 1.0, "yellow_p90": 0.0,
        "win_pen_p90": 0.0, "pen_taker": False, "fk_taker": False,
        "goals_p90": 0.0, "assists_p90": 0.0, "sot_p90": 0.0,
        "kp_p90": 0.0, "tackles_p90": 0.0, "saves_p90": 0.0,
        "obx_ratio": 0.0,
    }
    base.update(stats)
    return {"name": "Test", "pos": pos, "nation": "X",
            "ownership": ownership, "stats": base}


# ---------------------------------------------------------------------------
# Official scoring table values
# ---------------------------------------------------------------------------

def test_goal_points_by_position():
    assert pts("goal", "GK") == 6
    assert pts("goal", "DEF") == 6
    assert pts("goal", "MID") == 5
    assert pts("goal", "FWD") == 4


def test_clean_sheet_points():
    assert pts("clean_sheet", "GK") == 5
    assert pts("clean_sheet", "DEF") == 5
    assert pts("clean_sheet", "MID") == 1
    assert pts("clean_sheet", "FWD") == 0


def test_misc_table_values():
    assert pts("assist", "FWD") == 3
    assert pts("pen_save", "GK") == 3      # corrected from 5
    assert pts("red", "MID") == -2         # corrected from -3
    assert pts("yellow", "DEF") == -1
    assert pts("miss_penalty", "FWD") == -2
    assert pts("win_penalty", "MID") == 2
    assert pts("scouting_bonus", "FWD") == 2


def test_position_gated_bonuses():
    assert pts("tackle_per_3", "MID") == 1 and pts("tackle_per_3", "DEF") == 0
    assert pts("chance_per_2", "MID") == 1 and pts("chance_per_2", "FWD") == 0
    assert pts("sot_per_2", "FWD") == 1 and pts("sot_per_2", "MID") == 0
    assert pts("save_per_3", "GK") == 1 and pts("save_per_3", "DEF") == 0


# ---------------------------------------------------------------------------
# Model behavior
# ---------------------------------------------------------------------------

def test_clean_sheet_helps_def_not_fwd():
    d = make_player("DEF")
    f = make_player("FWD")
    assert calc_xp_per_game(d, 0.9) > calc_xp_per_game(d, 0.0)
    assert calc_xp_per_game(f, 0.9) == calc_xp_per_game(f, 0.0)


def test_easy_fixture_boosts_attacker():
    p = make_player("FWD", goals_p90=0.8, sot_p90=2.5)
    assert calc_xp_per_game(p, 0.3, difficulty=1) > calc_xp_per_game(p, 0.3, difficulty=3)
    assert calc_xp_per_game(p, 0.3, difficulty=3) > calc_xp_per_game(p, 0.3, difficulty=5)


def test_hard_fixture_boosts_gk_saves():
    # Same CS prob: a GK facing a stronger side faces more shots → more saves
    gk = make_player("GK", saves_p90=3.0)
    assert calc_xp_per_game(gk, 0.3, difficulty=5) > calc_xp_per_game(gk, 0.3, difficulty=3)
    assert calc_xp_per_game(gk, 0.3, difficulty=3) > calc_xp_per_game(gk, 0.3, difficulty=1)


def test_minutes_prorate_attacking_output():
    full = make_player("FWD", goals_p90=0.8, min_60_prob=0.95)
    subbed = make_player("FWD", goals_p90=0.8, min_60_prob=0.50)
    assert calc_xp_per_game(full, 0.3) > calc_xp_per_game(subbed, 0.3)


def test_pen_taker_nets_positive_value():
    # Extra pen goals must outweigh the occasional miss
    taker = make_player("FWD", goals_p90=0.5, pen_taker=True)
    non = make_player("FWD", goals_p90=0.5, pen_taker=False)
    assert calc_xp_per_game(taker, 0.3) > calc_xp_per_game(non, 0.3)


def test_scouting_bonus_for_low_ownership():
    hidden = make_player("FWD", ownership=0.03, goals_p90=0.8, sot_p90=2.5)
    popular = make_player("FWD", ownership=0.40, goals_p90=0.8, sot_p90=2.5)
    assert calc_xp_per_game(hidden, 0.3) > calc_xp_per_game(popular, 0.3)


def test_shrinkage_pulls_extremes_toward_prior():
    p = make_player("FWD", goals_p90=2.0)
    eff = effective_stats(p)
    prior = POSITION_PRIORS["FWD"]["goals_p90"]
    assert prior < eff["goals_p90"] < 2.0
    expected = (1 - SHRINK) * 2.0 + SHRINK * prior
    assert abs(eff["goals_p90"] - expected) < 1e-9


def test_shrinkage_leaves_probabilities_alone():
    p = make_player("MID", start_prob=0.6, min_60_prob=0.7)
    eff = effective_stats(p)
    assert eff["start_prob"] == 0.6
    assert eff["min_60_prob"] == 0.7


def test_group_stage_sums_three_games():
    p = make_player("MID", goals_p90=0.4, kp_p90=2.0)
    per_game = [calc_xp_per_game(p, cs, d)
                for cs, d in zip([0.3, 0.4, 0.2], [2, 3, 4])]
    total = calc_xp_group_stage(p, [0.3, 0.4, 0.2], [2, 3, 4])
    assert abs(total - sum(per_game)) < 0.02


def test_yellow_cards_cost_points():
    clean = make_player("MID")
    dirty = make_player("MID", yellow_p90=0.5)
    assert calc_xp_per_game(clean, 0.0) > calc_xp_per_game(dirty, 0.0)


if __name__ == "__main__":
    import sys
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS  {name}")
            except AssertionError as e:
                failures += 1
                print(f"  FAIL  {name}: {e}")
    print(f"\n{failures} failure(s)" if failures else "\nAll tests passed.")
    sys.exit(1 if failures else 0)
