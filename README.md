# FM27 — Football Manager 27

A deep, self-contained football management simulation for the terminal.
Manage one of 44 real English clubs across the Premier League and EFL
Championship, or sit back and watch the world evolve across **decades of
simulated seasons**.

Pure Python 3.10+, standard library only — no dependencies to install.
An unofficial fan project: real club names are used descriptively; all
players are fictional.

## Quick start

```bash
# Interactive career mode
python -m fm27

# Headless multi-year simulation: 25 seasons, reproducible seed
python -m fm27 --sim 25 --seed 7

# Continue a saved world for another 10 seasons and save it again
python -m fm27 --sim 10 --load saves/world.json --save-to world
```

## Features

**The world**
- 44 real English clubs: the 20-team Premier League and 24-team Championship,
  each with its own fixture calendar (38 and 46 matchdays, interleaved)
- Promotion and relegation (3 up / 3 down) with a 3rd–6th place
  **promotion playoff**
- The FA Cup: knockout for all 44 clubs, with first-round byes for the
  biggest sides, extra time, and penalty shootouts

**The match engine**
- Probabilistic engine driven by the selected XI: attack/midfield/defence
  strengths from player attributes, fitness, morale, tactics, and home advantage
- Goals, assists, cards, suspensions (including totting-up bans), injuries,
  clean sheets, and per-player match ratings

**Squads & players**
- 17 attributes per player across four groups — Technical (finishing,
  dribbling, passing, crossing, tackling, heading), Mental (vision,
  positioning, composure, work rate), Physical (pace, stamina, strength),
  and Keeping (reflexes, handling, aerial, kicking) — blended into a
  position-weighted overall rating
- Ageing with a realistic profile: pace and stamina fade first, mental
  attributes barely decline; hidden potential drives youth growth curves
- Team selection always fields the strongest available XI in their natural
  positions — a tired star still starts, and a 99-rated striker is never
  repurposed to patch a weak back line. Elite finishers dominate their
  team's goal share like real ones do
- The league's overall quality is anchored: as veterans retire and regens
  arrive, average ability stays level across decades instead of inflating —
  eras of great players are followed by leaner ones
- Youth intake every season, retirements, squad-size discipline, and
  multi-decade career records
- Six formations and three mentalities that genuinely change how matches play

**Transfers, loans & scouting**
- Two transfer windows a season — summer and January. Deals only happen
  while a window is open, for you and for the 43 AI clubs
- **Loans**: send youngsters out for a season of first-team football (they
  develop on the minutes they actually play), or bring in promising loanees
  from bigger clubs. The AI runs its own loan market every window
- **Scouting network**: market listings only show ability/potential bands
  until you send a scout. Reports take a matchday, reveal exact attributes,
  estimate potential, and grade targets out of five stars. Keep a shortlist
  of players you're tracking
- Sell players by fielding AI offers; every deal respects budgets, wage
  rooms, and squad-depth rules

**Contracts & free agency**
- Every player is on a contract that runs down each season; expiring players
  walk for free unless you offer a new deal from the Contracts screen, and
  a player running down his deal is worth far less on the market
- AI clubs renew the players they want and release the rest into a
  free-agent pool you (and they) can sign from for wages only

**The dugout is a hot seat**
- Board confidence tracks every result against expectations set by your
  club's stature — finish above your means and it soars, slump and the
  axe falls, mid-season or at the year-end review
- Get sacked and you'll field job offers from clubs willing to take a
  chance on you, or walk away; your managerial career history is tracked
  across every stint
- Prefer a quiet life? Enable **job security** at career start (or toggle
  it on the Club page) and the board can never fire you
- Set a per-player **training focus** (Technical / Mental / Physical /
  Keeping) to steer how your youngsters develop

**In-game editor**
- Edit any player in the world at any time: name, age, position, every
  attribute, potential, fitness/morale, instant injury healing — or move a
  player to any club, FM-editor style

**Finances**
- TV money (growing year on year), gate receipts, prize money, parachute
  payments for relegated clubs, wage bills, and board intervention when
  the money runs out

**Multi-year simulation**
- Simulate 1–200 seasons in one command, in-career or as a spectator
- While simming, your assistant can run your club's transfers, loans,
  free-agent signings, and contract renewals (autopilot) — or leave the
  squad untouched if you'd rather handle every deal yourself
- Season-by-season history: champions, cup winners, golden boots,
  players of the season, promotions and relegations
- All-time records: top scorers, most decorated players, club honours
  boards, biggest wins, and a Hall of Fame of retired greats
- Save/load any world as JSON, with fully deterministic resumption
  (a reloaded save replays *identically*)

## Playing a career

1. `python -m fm27` → *New career* → pick a seed (or leave blank), your name,
   and a club.
2. **Continue** simulates forward to your next match — other leagues and cup
   rounds play out along the way, scout reports land, and the January
   window opens mid-season.
3. Squad, tables, fixtures, transfers & loans, scouting, tactics, finances,
   club page, history, and the editor are all one keypress away.
4. Hand the reins to your assistant any time: *Sim to end of season* or
   *Sim multiple seasons* (1–100 years at once).
5. Save from the menu; saves land in `./saves/`.

Potential shows as a band (A ≥ 85, B ≥ 75, C ≥ 65, D below) until your
scouts have watched a player — signing young "A" prospects cheaply, or
loaning them, is how small clubs climb.

## Project layout

| Module | Purpose |
| --- | --- |
| `fm27/player.py` | Player attributes, ability, value, development, careers |
| `fm27/club.py` | Squads, tactics, lineup selection, club finances |
| `fm27/match_engine.py` | The probabilistic match simulation |
| `fm27/competition.py` | League scheduling/tables, FA Cup, promotion playoff |
| `fm27/transfers.py` | Transfer windows, AI deals, user bids, the loan market |
| `fm27/world.py` | Season calendar, windows, scouting, end-of-season, multi-year sims |
| `fm27/editor.py` | The in-game player editor |
| `fm27/records.py` | All-time records and Hall of Fame queries |
| `fm27/save.py` | JSON save/load |
| `fm27/cli.py` | Interactive terminal interface |

## Tests

```bash
python -m unittest discover -s tests
```

36 tests cover scheduling correctness, match-engine sanity (home advantage,
strength ordering), full-season and multi-year invariants, loan, transfer,
contract, and free-agency integrity, board confidence and sackings (and the
unsackable mode), autopilot squad management, training focus, the scouting
pipeline, the editor, star-player selection and scoring, league-quality
stability, legacy-save migration, and deterministic save/load round-trips.
