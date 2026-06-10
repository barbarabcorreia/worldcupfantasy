# FIFA World Cup Fantasy 2026 — Team Optimizer

When this command is invoked, help the user build the best possible FIFA World Cup Fantasy 2026 team. Follow these steps:

## Step 1: Get Fresh Intel (optional but recommended)

Search the web for the latest news that may affect player selection:
1. Search: `"FIFA World Cup Fantasy 2026" best picks matchday site:fantasyfootballscout.co.uk OR site:allaboutfpl.com OR site:rotowire.com`
2. Search: `"World Cup Fantasy 2026" injuries suspensions player news [current date]`
3. Look for any price changes, injury updates, or newly revealed lineup news.

Summarize key updates that should affect the players.json database.

## Step 2: Update Players if Needed

If new information is found (injuries, suspensions, confirmed non-starters), update `/home/user/worldcupfantasy/players.json`:
- Reduce `xp` for injured/suspended players (set to 0 if certain miss)
- Add new players if discovered with correct position/price/xp

## Step 3: Run the Optimizer

Execute the optimizer:

```bash
cd /home/user/worldcupfantasy && python3 optimizer.py
```

## Step 4: Present Results

Present the full output to the user, then add your expert commentary:

### Captain Recommendation
Explain who to captain and why (fixture, form, penalty duty). Suggest a live-captain switch strategy if their fixture looks risky early.

### Key Value Picks
Highlight the 2-3 best value differentials (low ownership, high ceiling). The Scouting Bonus (+2 pts) activates for players owned by <5% of managers who score >4 pts in a round.

### Chip Strategy
Recommend when to use each of the 5 boosters:
- **Maximum Captain**: Use in QF/SF when your captain plays a weak opponent
- **12th Man**: Use in Round of 32 (16 matches in one round)
- **Qualification Booster**: Best in QF (fewer teams, most of your XI likely progresses)
- **Wildcard**: Save until after surprise group exits are confirmed (not available in Round 1)
- **Mystery Booster**: Wait and evaluate when revealed at Round of 32

### Transfer Priorities
Based on the squad selected, flag which bench players are most likely to need replacing first and suggest high-value targets.

## Step 5: Answer Follow-ups

Be ready to:
- Re-run with a different budget (e.g. `python3 optimizer.py --budget 105` for knockout stages)
- Explain why a specific player was or wasn't selected
- Suggest alternative squads if the user wants different players
- Update players.json with player edits and re-optimize
- Show the scoring system in full detail

## FIFA World Cup Fantasy 2026 — Quick Reference

### Game Rules
- **Squad**: 15 players (2 GK, 5 DEF, 5 MID, 3 FWD)
- **Starting XI**: Any valid formation from your 15
- **Budget**: $100m (group stage), $105m (knockout stages)
- **Nation limit**: Max 3 players from the same country
- **Player prices**: Fixed throughout the tournament

### Scoring System
| Action | GK | DEF | MID | FWD |
|--------|-----|-----|-----|-----|
| Playing ≥60 min | +2 | +2 | +2 | +2 |
| Playing <60 min | +1 | +1 | +1 | +1 |
| Goal scored | +6 | +6 | +5 | +4 |
| Goal outside box (bonus) | +1 | +1 | +1 | +1 |
| Assist | +3 | +3 | +3 | +3 |
| Clean sheet (60+ min) | +5 | +5 | +1 | — |
| Every 3 saves | +1 | — | — | — |
| Penalty saved | +5 | — | — | — |
| Yellow card | -1 | -1 | -1 | -1 |
| Red card | -3 | -3 | -3 | -3 |
| Own goal | -2 | -2 | -2 | -2 |
| Missed penalty | -2 | -2 | -2 | -2 |
| Player of the Match | +3 | +3 | +3 | +3 |
| Scouting Bonus (<5% owned, >4 pts) | +2 | +2 | +2 | +2 |
| Goal from free kick (bonus) | +1 | +1 | +1 | +1 |

### Transfers
- **Group stage**: 1 free transfer per matchday; can roll over 1 (except MD3 → R32)
- **Round of 32+**: Unlimited free transfers each round

### Boosters (5 total, one at a time)
1. **Wildcard**: Unlimited free transfers (not usable in Round 1 or before Round of 32)
2. **12th Man**: All bench players automatically sub into starting XI for that round
3. **Maximum Captain**: Your highest-scoring starting XI player auto-doubles their points
4. **Qualification Booster**: +2 pts for each starting XI player that advances to the next round
5. **Mystery Booster**: Revealed when Round of 32 opens

### Captain Rules
- Captains score **double points**
- Can change captain **unlimited times** during a live round (but not retroactively)
- Vice-captain scores double if the captain doesn't play
