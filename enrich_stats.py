#!/usr/bin/env python3
"""
Enrich players.json with per-game stats (goals, assists, SoT, key passes,
tackles, saves) and fixtures.json with clean-sheet probabilities per match.

Stats are derived from:
  - 2026 WCQ qualifying campaign (primary source)
  - 2025-26 club season form (secondary source)
  - Reasonable position-based defaults for players with limited data

Clean sheet probabilities are estimated from:
  - Match betting win/draw/loss odds (converted to implied CS probability)
  - Team xGC from qualifying
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# Per-game stats for each player.
# Keys: goals_p90, assists_p90, sot_p90, kp_p90, tackles_p90, saves_p90,
#       pen_taker, fk_taker, start_prob, min_60_prob, yellow_p90, obx_ratio,
#       win_pen_p90
# ---------------------------------------------------------------------------
PLAYER_STATS: dict[str, dict] = {
    # === FORWARDS ===
    "Erling Haaland": {
        # 16G in 8 WCQ games (2.0 G/game). Top UEFA qualifier scorer.
        # 41 shots, 28 SoT in qualifying (3.5 SoT/game). Penalty taker.
        # MD3: Norway vs France — BOTH teams already qualified (6pts each).
        # Dead rubber: Haaland very likely rested for Round of 32.
        "goals_p90": 2.00, "assists_p90": 0.12, "sot_p90": 3.50,
        "pen_taker": True, "start_prob": 0.50, "min_60_prob": 0.70,
        "obx_ratio": 0.10, "yellow_p90": 0.05, "win_pen_p90": 0.08,
    },
    "Kylian Mbappe": {
        # 5G in WCQ qualifiers (lower due to fewer games played). Penalty taker.
        # 3 SoT/game estimate from club form.
        # MD3: France vs Norway — BOTH teams already qualified (6pts each).
        # Dead rubber: Deschamps historically rests key players in dead rubbers.
        "goals_p90": 0.85, "assists_p90": 0.40, "sot_p90": 3.20,
        "pen_taker": True, "start_prob": 0.45, "min_60_prob": 0.65,
        "obx_ratio": 0.15, "yellow_p90": 0.08, "win_pen_p90": 0.06,
    },
    "Mikel Oyarzabal": {
        # 6G 4A in 6 WCQ starts. 1.0 G/game, 0.67 A/game.
        # Spain penalty taker when Morata doesn't play.
        "goals_p90": 1.00, "assists_p90": 0.67, "sot_p90": 2.50,
        "pen_taker": False, "fk_taker": False, "start_prob": 0.90,
        "min_60_prob": 0.82, "obx_ratio": 0.20, "yellow_p90": 0.10,
        "win_pen_p90": 0.05,
    },
    "Kai Havertz": {
        # Arsenal penalty taker, good goal rate vs weak opponents.
        "goals_p90": 0.60, "assists_p90": 0.25, "sot_p90": 2.00,
        "pen_taker": True, "start_prob": 0.85, "min_60_prob": 0.80,
        "obx_ratio": 0.15, "yellow_p90": 0.12,
    },
    "Lautaro Martinez": {
        # Argentina penalty taker, 6.5 xG/6 WCQ games.
        "goals_p90": 0.65, "assists_p90": 0.28, "sot_p90": 2.80,
        "pen_taker": True, "start_prob": 0.92, "min_60_prob": 0.85,
        "obx_ratio": 0.12, "yellow_p90": 0.10,
    },
    "Cristiano Ronaldo": {
        # 5G in qualifying (declining), but still penalty taker for Portugal.
        "goals_p90": 0.45, "assists_p90": 0.20, "sot_p90": 2.20,
        "pen_taker": True, "start_prob": 0.88, "min_60_prob": 0.78,
        "obx_ratio": 0.08, "yellow_p90": 0.08,
    },
    "Robert Lewandowski": {
        # Poland penalty taker, 8G in qualifying.
        "goals_p90": 0.72, "assists_p90": 0.18, "sot_p90": 2.60,
        "pen_taker": True, "start_prob": 0.92, "min_60_prob": 0.85,
        "obx_ratio": 0.10, "yellow_p90": 0.08,
    },
    "Nick Woltemade": {
        # Good club form, emerging striker.
        "goals_p90": 0.55, "assists_p90": 0.20, "sot_p90": 2.10,
        "pen_taker": False, "start_prob": 0.80, "min_60_prob": 0.72,
        "obx_ratio": 0.22,
    },
    "Antoine Griezmann": {
        # France's creative FWD, assists and goals.
        "goals_p90": 0.45, "assists_p90": 0.45, "sot_p90": 2.00,
        "pen_taker": False, "start_prob": 0.85, "min_60_prob": 0.78,
        "obx_ratio": 0.18, "yellow_p90": 0.10,
    },
    "Darwin Nunez": {
        "goals_p90": 0.50, "assists_p90": 0.22, "sot_p90": 2.20,
        "pen_taker": False, "start_prob": 0.82, "min_60_prob": 0.75,
        "obx_ratio": 0.12, "yellow_p90": 0.15,
    },
    "Richarlison": {
        "goals_p90": 0.55, "assists_p90": 0.18, "sot_p90": 2.30,
        "pen_taker": False, "start_prob": 0.78, "min_60_prob": 0.72,
        "obx_ratio": 0.10, "yellow_p90": 0.12,
    },
    "Nicolas Jackson": {
        "goals_p90": 0.45, "assists_p90": 0.20, "sot_p90": 1.80,
        "pen_taker": False, "start_prob": 0.80, "min_60_prob": 0.72,
    },
    "Alvaro Morata": {
        # Spain striker. Not guaranteed starter but when he plays, scores.
        "goals_p90": 0.48, "assists_p90": 0.22, "sot_p90": 1.80,
        "pen_taker": True, "start_prob": 0.75, "min_60_prob": 0.68,
        "obx_ratio": 0.10,
    },
    "Serhou Guirassy": {
        # Bundesliga top scorer 2024-25, penalty taker.
        "goals_p90": 0.65, "assists_p90": 0.18, "sot_p90": 2.40,
        "pen_taker": True, "start_prob": 0.85, "min_60_prob": 0.78,
        "obx_ratio": 0.12,
    },
    "Memphis Depay": {
        # 8G in qualifying, Netherlands penalty taker.
        "goals_p90": 0.62, "assists_p90": 0.30, "sot_p90": 2.20,
        "pen_taker": True, "start_prob": 0.82, "min_60_prob": 0.75,
        "obx_ratio": 0.15, "yellow_p90": 0.10,
    },
    "Jhon Duran": {
        "goals_p90": 0.50, "assists_p90": 0.15, "sot_p90": 2.00,
        "pen_taker": False, "start_prob": 0.78, "min_60_prob": 0.70,
    },
    "Christopher Nkunku": {
        "goals_p90": 0.48, "assists_p90": 0.30, "sot_p90": 2.10,
        "pen_taker": False, "start_prob": 0.72, "min_60_prob": 0.65,
        "obx_ratio": 0.20,
    },
    "Gabriel Martinelli": {
        "goals_p90": 0.38, "assists_p90": 0.25, "sot_p90": 1.80,
        "pen_taker": False, "start_prob": 0.72, "min_60_prob": 0.65,
    },
    "Vitor Roque": {
        "goals_p90": 0.35, "assists_p90": 0.12, "sot_p90": 1.50,
        "pen_taker": False, "start_prob": 0.65, "min_60_prob": 0.58,
    },
    "Rodrigo": {
        "goals_p90": 0.42, "assists_p90": 0.18, "sot_p90": 1.80,
        "pen_taker": False, "start_prob": 0.75, "min_60_prob": 0.68,
    },
    "Ferran Torres": {
        "goals_p90": 0.38, "assists_p90": 0.20, "sot_p90": 1.60,
        "pen_taker": False, "start_prob": 0.70, "min_60_prob": 0.62,
    },
    "Sébastien Haller": {
        "goals_p90": 0.38, "assists_p90": 0.12, "sot_p90": 1.60,
        "pen_taker": True, "start_prob": 0.75, "min_60_prob": 0.68,
    },
    "Donyell Malen": {
        "goals_p90": 0.38, "assists_p90": 0.22, "sot_p90": 1.80,
        "pen_taker": False, "start_prob": 0.72, "min_60_prob": 0.65,
    },
    "André Ayew": {
        # EXCLUDED from Ghana's WC 2026 squad by coach Carlos Queiroz
        "goals_p90": 0.28, "assists_p90": 0.12, "sot_p90": 1.20,
        "pen_taker": False, "start_prob": 0.0, "min_60_prob": 0.0,
    },

    # === MIDFIELDERS ===
    "Vinícius Júnior": {
        # High dribbling, SoT and chances created. Not a pen taker.
        "goals_p90": 0.48, "assists_p90": 0.38, "sot_p90": 2.80,
        "kp_p90": 2.40, "tackles_p90": 0.80,
        "pen_taker": False, "start_prob": 0.92, "min_60_prob": 0.85,
        "obx_ratio": 0.25, "yellow_p90": 0.15,
    },
    "Bruno Fernandes": {
        # 21 EPL assists in 2025-26; 10G in qualifying. Set piece + pen taker for Portugal.
        # ~1.8 key passes/game for NT, 0.8 G/game, 1.4 A/game estimate.
        "goals_p90": 0.60, "assists_p90": 1.00, "sot_p90": 2.80,
        "kp_p90": 2.80, "tackles_p90": 1.20,
        "pen_taker": True, "fk_taker": True, "start_prob": 0.95,
        "min_60_prob": 0.88, "obx_ratio": 0.22, "yellow_p90": 0.18,
        "win_pen_p90": 0.05,
    },
    "Lamine Yamal": {
        # 12.81 xG, 37 SoT in La Liga. Key chance creator for Spain.
        # June 11: Barcelona advised Spain to cap him at ~15 min vs Cape Verde
        # (MD1) as he returns from the April hamstring injury. Likely bench
        # cameo MD1, building toward starts in MD2/MD3 — heavy minutes discount.
        "goals_p90": 0.48, "assists_p90": 0.62, "sot_p90": 3.00,
        "kp_p90": 3.20, "tackles_p90": 0.80,
        "pen_taker": False, "fk_taker": True, "start_prob": 0.55,
        "min_60_prob": 0.55, "obx_ratio": 0.30, "yellow_p90": 0.08,
    },
    "Jude Bellingham": {
        # Set piece threat. Goals and assists for England.
        "goals_p90": 0.42, "assists_p90": 0.35, "sot_p90": 2.20,
        "kp_p90": 2.20, "tackles_p90": 1.50,
        "pen_taker": False, "fk_taker": False, "start_prob": 0.92,
        "min_60_prob": 0.88, "obx_ratio": 0.18, "yellow_p90": 0.12,
    },
    "Leandro Trossard": {
        # Belgium FWD playing as MID. Strong goal and assist threat.
        "goals_p90": 0.42, "assists_p90": 0.38, "sot_p90": 2.20,
        "kp_p90": 1.80, "tackles_p90": 1.00,
        "pen_taker": False, "start_prob": 0.88, "min_60_prob": 0.82,
        "obx_ratio": 0.20, "yellow_p90": 0.12,
    },
    "Declan Rice": {
        # Set piece taker, deep-lying MID. Fewer goals but solid points.
        "goals_p90": 0.20, "assists_p90": 0.28, "sot_p90": 1.20,
        "kp_p90": 1.80, "tackles_p90": 2.80,
        "pen_taker": False, "fk_taker": True, "start_prob": 0.92,
        "min_60_prob": 0.88, "yellow_p90": 0.20,
    },
    "Phil Foden": {
        # EXCLUDED from England's WC 2026 squad by Tuchel (poor club form at Man City)
        "start_prob": 0.0, "min_60_prob": 0.0, "goals_p90": 0.38, "assists_p90": 0.38,
        "sot_p90": 2.00, "kp_p90": 2.20, "tackles_p90": 0.80, "yellow_p90": 0.08,
    },
    "Bukayo Saka": {
        # June 2026: Achilles injury from March still limiting him — Tuchel
        # says he can't train consecutive days, "not close to 100%".
        "goals_p90": 0.35, "assists_p90": 0.38, "sot_p90": 2.10,
        "kp_p90": 2.50, "tackles_p90": 1.00,
        "pen_taker": False, "fk_taker": True, "start_prob": 0.70,
        "min_60_prob": 0.68, "yellow_p90": 0.10,
    },
    "Mohamed Salah": {
        # Poor 2025-26 club season. Pen taker for Egypt.
        "goals_p90": 0.32, "assists_p90": 0.28, "sot_p90": 2.20,
        "kp_p90": 2.00, "tackles_p90": 0.50,
        "pen_taker": True, "start_prob": 0.90, "min_60_prob": 0.82,
        "obx_ratio": 0.18, "yellow_p90": 0.06,
    },
    "Pedri": {
        "goals_p90": 0.28, "assists_p90": 0.32, "sot_p90": 1.60,
        "kp_p90": 3.00, "tackles_p90": 2.20,
        "pen_taker": False, "start_prob": 0.85, "min_60_prob": 0.78,
        "yellow_p90": 0.14,
    },
    "Dani Olmo": {
        "goals_p90": 0.32, "assists_p90": 0.28, "sot_p90": 1.80,
        "kp_p90": 2.20, "tackles_p90": 1.50,
        "pen_taker": False, "start_prob": 0.82, "min_60_prob": 0.75,
        "obx_ratio": 0.22,
    },
    "Bernardo Silva": {
        "goals_p90": 0.22, "assists_p90": 0.30, "sot_p90": 1.40,
        "kp_p90": 2.80, "tackles_p90": 1.20,
        "pen_taker": False, "start_prob": 0.85, "min_60_prob": 0.78,
    },
    "Federico Valverde": {
        "goals_p90": 0.25, "assists_p90": 0.20, "sot_p90": 1.60,
        "kp_p90": 1.80, "tackles_p90": 2.50,
        "pen_taker": False, "start_prob": 0.88, "min_60_prob": 0.82,
        "yellow_p90": 0.18,
    },
    "John McGinn": {
        # Set piece taker, Scotland captain.
        "goals_p90": 0.20, "assists_p90": 0.22, "sot_p90": 1.20,
        "kp_p90": 1.50, "tackles_p90": 2.20,
        "pen_taker": False, "fk_taker": True, "start_prob": 0.90,
        "min_60_prob": 0.85, "yellow_p90": 0.15,
    },
    "Gavi": {
        "goals_p90": 0.18, "assists_p90": 0.22, "sot_p90": 1.00,
        "kp_p90": 2.80, "tackles_p90": 3.20,
        "pen_taker": False, "start_prob": 0.78, "min_60_prob": 0.70,
        "yellow_p90": 0.22,
    },
    "Rodrigo Bentancur": {
        "goals_p90": 0.12, "assists_p90": 0.15, "sot_p90": 0.80,
        "kp_p90": 1.20, "tackles_p90": 2.80,
        "pen_taker": False, "start_prob": 0.78, "min_60_prob": 0.72,
        "yellow_p90": 0.20,
    },
    "Carlos Soler": {
        "goals_p90": 0.18, "assists_p90": 0.15, "sot_p90": 0.90,
        "kp_p90": 1.50, "tackles_p90": 1.80,
        "pen_taker": False, "start_prob": 0.72, "min_60_prob": 0.65,
    },
    "Jarrod Bowen": {
        "goals_p90": 0.22, "assists_p90": 0.18, "sot_p90": 1.20,
        "kp_p90": 1.40, "tackles_p90": 1.00,
        "pen_taker": False, "start_prob": 0.68, "min_60_prob": 0.60,
    },

    # === DEFENDERS ===
    "Achraf Hakimi": {
        # Attacking RB. High assists and SoT for a DEF.
        # June 2026: hamstring pull in May CL semi; expected fit but a
        # small re-injury/management risk remains.
        "goals_p90": 0.22, "assists_p90": 0.32, "sot_p90": 0.0,
        "tackles_p90": 1.50,
        "pen_taker": False, "start_prob": 0.86, "min_60_prob": 0.80,
        "obx_ratio": 0.30, "yellow_p90": 0.15,
    },
    "Virgil van Dijk": {
        "goals_p90": 0.12, "assists_p90": 0.08, "sot_p90": 0.0,
        "tackles_p90": 0.80,
        "pen_taker": False, "start_prob": 0.92, "min_60_prob": 0.88,
        "yellow_p90": 0.10,
    },
    "Alejandro Balde": {
        # EXCLUDED from Spain's WC 2026 squad (Cucurella/Grimaldo preferred at LB)
        "start_prob": 0.0, "min_60_prob": 0.0, "goals_p90": 0.12, "assists_p90": 0.28,
        "tackles_p90": 1.20, "yellow_p90": 0.12,
    },
    "William Saliba": {
        # Back injury: initially "very doubtful", Deschamps says he'll be managed.
        # Expected to play but minutes managed — reduced start/min60 probabilities.
        "goals_p90": 0.06, "assists_p90": 0.06, "sot_p90": 0.0,
        "tackles_p90": 1.00,
        "pen_taker": False, "start_prob": 0.70, "min_60_prob": 0.62,
        "yellow_p90": 0.10,
    },
    "Jules Kounde": {
        "goals_p90": 0.08, "assists_p90": 0.18, "sot_p90": 0.0,
        "tackles_p90": 1.20,
        "pen_taker": False, "start_prob": 0.88, "min_60_prob": 0.82,
        "yellow_p90": 0.12,
    },
    "Dayot Upamecano": {
        "goals_p90": 0.08, "assists_p90": 0.05, "sot_p90": 0.0,
        "tackles_p90": 0.80,
        "pen_taker": False, "start_prob": 0.85, "min_60_prob": 0.80,
        "yellow_p90": 0.12,
    },
    "Marc Guehi": {
        # 3 assists in WCQ for England — set piece threat!
        "goals_p90": 0.10, "assists_p90": 0.30, "sot_p90": 0.0,
        "tackles_p90": 1.20,
        "pen_taker": False, "start_prob": 0.88, "min_60_prob": 0.82,
        "yellow_p90": 0.10,
    },
    "Nuno Mendes": {
        "goals_p90": 0.10, "assists_p90": 0.22, "sot_p90": 0.0,
        "tackles_p90": 1.20,
        "pen_taker": False, "start_prob": 0.85, "min_60_prob": 0.78,
        "yellow_p90": 0.12,
    },
    "Goncalo Inacio": {
        "goals_p90": 0.08, "assists_p90": 0.08, "sot_p90": 0.0,
        "tackles_p90": 1.00,
        "pen_taker": False, "start_prob": 0.85, "min_60_prob": 0.80,
        "yellow_p90": 0.10,
    },
    "Jonathan Clauss": {
        # EXCLUDED from France's WC 2026 squad (Gusto/Hernandez brothers as fullbacks)
        "start_prob": 0.0, "min_60_prob": 0.0, "goals_p90": 0.10, "assists_p90": 0.22,
        "tackles_p90": 1.40, "yellow_p90": 0.12,
    },
    "Jose Gimenez": {
        "goals_p90": 0.08, "assists_p90": 0.06, "sot_p90": 0.0,
        "tackles_p90": 1.00,
        "pen_taker": False, "start_prob": 0.85, "min_60_prob": 0.80,
        "yellow_p90": 0.12,
    },
    "Dani Carvajal": {
        # EXCLUDED — no Real Madrid players in Spain's WC 2026 squad
        "start_prob": 0.0, "min_60_prob": 0.0, "goals_p90": 0.08, "assists_p90": 0.18,
        "tackles_p90": 1.00, "yellow_p90": 0.12,
    },
    "Tyler Adams": {
        "goals_p90": 0.06, "assists_p90": 0.08, "sot_p90": 0.0,
        "tackles_p90": 2.00,
        "pen_taker": False, "start_prob": 0.82, "min_60_prob": 0.75,
        "yellow_p90": 0.18,
    },
    "Perr Schuurs": {
        # NOT in Netherlands WC 2026 squad (recovering from serious knee injury Oct 2023)
        "goals_p90": 0.06, "assists_p90": 0.05, "sot_p90": 0.0,
        "tackles_p90": 0.80,
        "pen_taker": False, "start_prob": 0.0, "min_60_prob": 0.0,
        "yellow_p90": 0.10,
    },
    "Robin Gosens": {
        "goals_p90": 0.10, "assists_p90": 0.18, "sot_p90": 0.0,
        "tackles_p90": 1.50,
        "pen_taker": False, "start_prob": 0.78, "min_60_prob": 0.70,
        "yellow_p90": 0.15,
    },
    "Ladislav Krejci": {
        "goals_p90": 0.06, "assists_p90": 0.06, "sot_p90": 0.0,
        "tackles_p90": 1.20,
        "pen_taker": False, "start_prob": 0.82, "min_60_prob": 0.75,
        "yellow_p90": 0.10,
    },
    "Mojica": {
        "goals_p90": 0.08, "assists_p90": 0.15, "sot_p90": 0.0,
        "tackles_p90": 1.80,
        "pen_taker": False, "start_prob": 0.85, "min_60_prob": 0.78,
        "yellow_p90": 0.15,
    },
    "Ricardo Horta": {
        # EXCLUDED from Portugal's WC 2026 squad
        "start_prob": 0.0, "min_60_prob": 0.0, "goals_p90": 0.06, "assists_p90": 0.06,
        "tackles_p90": 0.80,
    },

    # === NEW PLAYERS ADDED POST-MD2 ===
    "Lionel Messi": {
        # Hat-trick MD1 (vs Algeria 3-0). Argentina pen taker. Age 38 but still elite
        # in major tournaments. Argentina qualified after 2 wins (6pts).
        # MD3 vs Jordan: very easy fixture. Scaloni typically plays Messi regardless.
        # Slight rotation risk (~20%) as Argentina might manage minutes.
        "goals_p90": 0.90, "assists_p90": 0.55, "sot_p90": 2.80,
        "kp_p90": 2.20, "tackles_p90": 0.40,
        "pen_taker": True, "fk_taker": True, "start_prob": 0.82,
        "min_60_prob": 0.75, "obx_ratio": 0.20, "yellow_p90": 0.08,
        "win_pen_p90": 0.06,
    },
    "Sadio Mane": {
        # Senegal captain, primary pen taker. MD3 vs Iraq (both eliminated, 0pts each).
        # Consolation fixture but Mane always plays and Iraq is very weak.
        # Community's #1 differential at 2% owned — scouting bonus candidate.
        "goals_p90": 0.65, "assists_p90": 0.35, "sot_p90": 2.50,
        "kp_p90": 1.80, "tackles_p90": 0.80,
        "pen_taker": True, "fk_taker": False, "start_prob": 0.92,
        "min_60_prob": 0.82, "obx_ratio": 0.18, "yellow_p90": 0.10,
        "win_pen_p90": 0.05,
    },

    # === NEW PLAYERS ADDED IN MD1 REVIEW ===
    "Harry Kane": {
        # England captain, Bayern Munich. Primary pen taker + FK scorer. Easy group.
        # 55 WC goals for England in 92 apps; elite aerial, movement inside box.
        "goals_p90": 0.72, "assists_p90": 0.25, "sot_p90": 2.80,
        "kp_p90": 1.20, "tackles_p90": 0.30,
        "pen_taker": True, "fk_taker": True, "start_prob": 0.95,
        "min_60_prob": 0.88, "obx_ratio": 0.12, "yellow_p90": 0.08,
        "win_pen_p90": 0.06,
    },
    "Marc Cucurella": {
        # Spain LB (Chelsea). Confirmed starter, key to Spain's build-up play.
        # More defensive than Balde; fewer attacking returns but solid CS value.
        "goals_p90": 0.06, "assists_p90": 0.14, "sot_p90": 0.0,
        "tackles_p90": 1.30,
        "pen_taker": False, "start_prob": 0.88, "min_60_prob": 0.82,
        "yellow_p90": 0.18,
    },
    "Alejandro Grimaldo": {
        # Spain DEF option (Bayer Leverkusen). Attacking LB, set piece threat.
        # Leverkusen's full season stats: ~6G + 15A — very high offensive returns.
        "goals_p90": 0.15, "assists_p90": 0.32, "sot_p90": 0.0,
        "tackles_p90": 1.50,
        "pen_taker": False, "fk_taker": True, "start_prob": 0.82,
        "min_60_prob": 0.75, "yellow_p90": 0.12,
    },
    "Theo Hernandez": {
        # France LB (Al-Hilal). Consistent starter under Deschamps, attacking threat.
        # MD3: France vs Norway — dead rubber, both qualified. Rotation risk.
        "goals_p90": 0.18, "assists_p90": 0.22, "sot_p90": 0.0,
        "tackles_p90": 1.20,
        "pen_taker": False, "start_prob": 0.50, "min_60_prob": 0.65,
        "yellow_p90": 0.15,
    },

    # === GOALKEEPERS ===
    "Emiliano Martinez": {
        # Argentina conceded very little in qualifying. Dominant presence.
        "goals_p90": 0.0, "saves_p90": 3.20,
        "start_prob": 0.95, "min_60_prob": 0.92, "yellow_p90": 0.05,
    },
    "Jordan Pickford": {
        # England conceded 0 in qualifying!
        "goals_p90": 0.0, "saves_p90": 2.60,
        "start_prob": 0.95, "min_60_prob": 0.92, "yellow_p90": 0.04,
    },
    "Mike Maignan": {
        "goals_p90": 0.0, "saves_p90": 2.80,
        "start_prob": 0.95, "min_60_prob": 0.92, "yellow_p90": 0.04,
    },
    "Bart Verbruggen": {
        # 3 clean sheets in 6 qualifying. Good shot-stopper.
        "goals_p90": 0.0, "saves_p90": 2.80,
        "start_prob": 0.92, "min_60_prob": 0.90, "yellow_p90": 0.04,
    },
    "Unai Simon": {
        "goals_p90": 0.0, "saves_p90": 2.50,
        "start_prob": 0.92, "min_60_prob": 0.90, "yellow_p90": 0.04,
    },
    "Manuel Neuer": {
        "goals_p90": 0.0, "saves_p90": 2.40,
        "start_prob": 0.90, "min_60_prob": 0.88, "yellow_p90": 0.03,
    },
    "Yann Sommer": {
        "goals_p90": 0.0, "saves_p90": 2.60,
        "start_prob": 0.92, "min_60_prob": 0.90, "yellow_p90": 0.03,
    },
    "Ederson": {
        "goals_p90": 0.0, "saves_p90": 2.40,
        "start_prob": 0.92, "min_60_prob": 0.90, "yellow_p90": 0.03,
    },
    "Maxime Crepeau": {
        "goals_p90": 0.0, "saves_p90": 3.00,
        "start_prob": 0.88, "min_60_prob": 0.85, "yellow_p90": 0.04,
    },
    "Paulo Gazzaniga": {
        # NOT in Argentina's WC 2026 squad (last played for Argentina in 2018)
        "goals_p90": 0.0, "saves_p90": 2.80,
        "start_prob": 0.0, "min_60_prob": 0.0, "yellow_p90": 0.04,
    },
    "David Raya": {
        "goals_p90": 0.0, "saves_p90": 2.50,
        "start_prob": 0.72, "min_60_prob": 0.70, "yellow_p90": 0.04,
    },
}

# ---------------------------------------------------------------------------
# Clean sheet probability per team per matchday.
# Derived from win/CS betting odds and xGC from qualifying.
# P(CS) ≈ P(win) * cs_given_win + P(draw) * cs_given_draw
# ---------------------------------------------------------------------------
CLEAN_SHEET_PROBS: dict[str, list[float]] = {
    # [md1_cs, md2_cs, md3_cs]
    "Norway":      [0.52, 0.32, 0.18],  # vs Iraq, Senegal, France (MD3 dead rubber — both qualified)
    "France":      [0.40, 0.60, 0.20],  # vs Senegal, Iraq, Norway (MD3 dead rubber — both qualified)
    "Senegal":     [0.20, 0.22, 0.40],  # vs France, Norway, Iraq
    "Iraq":        [0.08, 0.10, 0.22],  # vs Norway, France, Senegal
    "Spain":       [0.65, 0.50, 0.28],  # vs Cape Verde, Saudi Arabia, Uruguay
    "Cape Verde":  [0.06, 0.18, 0.30],
    "Saudi Arabia":[0.18, 0.12, 0.30],
    "Uruguay":     [0.30, 0.45, 0.20],  # vs Saudi Arabia, Cape Verde, Spain
    "England":     [0.42, 0.55, 0.60],  # vs Croatia, Ghana, Panama
    "Croatia":     [0.30, 0.40, 0.35],
    "Ghana":       [0.22, 0.18, 0.30],
    "Panama":      [0.12, 0.25, 0.10],
    "Portugal":    [0.62, 0.62, 0.35],  # vs Congo DR, Uzbekistan, Colombia
    "Congo DR":    [0.08, 0.18, 0.28],
    "Uzbekistan":  [0.12, 0.10, 0.28],
    "Colombia":    [0.40, 0.45, 0.22],
    "Brazil":      [0.28, 0.50, 0.65],  # vs Morocco (hard), Scotland, Haiti
    "Morocco":     [0.25, 0.52, 0.40],  # vs Brazil (hard), Haiti, Scotland
    "Haiti":       [0.08, 0.10, 0.08],
    "Scotland":    [0.40, 0.08, 0.28],  # vs Haiti (easy), Brazil (hard), Morocco
    "Belgium":     [0.38, 0.52, 0.72],  # vs Egypt, Iran, New Zealand (MUST WIN — full strength)
    "Egypt":       [0.20, 0.28, 0.35],
    "Iran":        [0.22, 0.22, 0.30],
    "New Zealand": [0.20, 0.30, 0.18],
    "Netherlands": [0.35, 0.38, 0.50],  # vs Japan, Sweden, Tunisia
    "Japan":       [0.30, 0.30, 0.32],
    "Sweden":      [0.42, 0.28, 0.30],
    "Tunisia":     [0.28, 0.30, 0.18],
    "Germany":     [0.70, 0.55, 0.38],  # vs Curacao, Ivory Coast, Ecuador
    "Curacao":     [0.05, 0.22, 0.30],
    "Ivory Coast": [0.28, 0.08, 0.48],  # vs Ecuador, Germany, Curacao
    "Ecuador":     [0.25, 0.50, 0.18],
    "Argentina":   [0.50, 0.40, 0.65],  # vs Algeria, Austria, Jordan
    "Algeria":     [0.22, 0.30, 0.25],
    "Austria":     [0.42, 0.28, 0.35],
    "Jordan":      [0.12, 0.15, 0.12],
    "Mexico":      [0.38, 0.32, 0.30],
    "South Africa":[0.18, 0.28, 0.28],
    "South Korea": [0.25, 0.22, 0.22],
    "Czechia":     [0.30, 0.42, 0.30],
    "Canada":      [0.35, 0.48, 0.30],
    "Bosnia-Herzegovina": [0.22, 0.20, 0.30],
    "Qatar":       [0.10, 0.22, 0.30],
    "Switzerland": [0.52, 0.38, 0.35],  # vs Qatar, Bosnia, Canada
    "USA":         [0.32, 0.30, 0.32],
    "Paraguay":    [0.20, 0.22, 0.22],
    "Australia":   [0.22, 0.20, 0.25],
    "Turkey":      [0.22, 0.22, 0.25],
    "Guinea":      [0.30, 0.30, 0.30],  # Group TBC
    "Poland":      [0.28, 0.25, 0.30],  # vs South Korea/Mexico/Czechia (Group A)
}


def enrich():
    players_path = BASE_DIR / "players.json"
    fixtures_path = BASE_DIR / "fixtures.json"

    # Update players
    pdata = json.loads(players_path.read_text())
    enriched = 0
    for player in pdata["players"]:
        name = player["name"]
        if name in PLAYER_STATS:
            player["stats"] = PLAYER_STATS[name]
            enriched += 1

    # Fix scoring table in meta
    pdata["meta"]["scoring"].update({
        "penalty_save": 3,       # corrected from 5
        "red_card": -2,          # corrected from -3
        "win_penalty": 2,        "concede_penalty": -1,
        "tackle_per_3_MID": 1,   "chance_per_2_MID": 1,
        "sot_per_2_FWD": 1,
    })

    # Update fixtures with CS probs
    fdata = json.loads(fixtures_path.read_text())
    for group in fdata["groups"].values():
        for fix in group["fixtures"]:
            for team in [fix["home"], fix["away"]]:
                md = fix["md"]
                cs_list = CLEAN_SHEET_PROBS.get(team)
                if cs_list and len(cs_list) >= md:
                    if "cs_prob" not in fix:
                        fix["cs_prob"] = {}
                    fix["cs_prob"][team] = cs_list[md - 1]

    # Regenerate xp / xp_md from the scoring engine so the stored values
    # always match what the optimizer actually uses (no stale hand-estimates).
    from optimizer import player_md_xp
    for player in pdata["players"]:
        xp_md = [round(player_md_xp(player, fdata, md), 2) for md in (1, 2, 3)]
        player["xp_md"] = xp_md
        player["xp"] = round(sum(xp_md), 1)

    players_path.write_text(json.dumps(pdata, indent=2, ensure_ascii=False))
    print(f"Enriched {enriched}/{len(pdata['players'])} players with stats "
          f"and regenerated model xp/xp_md.")
    fixtures_path.write_text(json.dumps(fdata, indent=2, ensure_ascii=False))
    print("Updated fixtures.json with clean sheet probabilities.")


if __name__ == "__main__":
    enrich()
