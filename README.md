# FM27 — Football Manager 27

A deep, self-contained football management simulation for the terminal.
Take charge of one of 28 fictional clubs across a two-division pyramid, or sit
back and watch the world evolve across **decades of simulated seasons**.

Pure Python 3.10+, standard library only — no dependencies to install.

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
- 28 clubs in two divisions (Premier Division & Championship) with
  promotion, relegation, and a 3rd–6th place **promotion playoff**
- The FA National Cup: straight knockout for all 28 clubs, with byes,
  extra time, and penalty shootouts
- Fixture calendar interleaving league matchdays, cup rounds, and playoffs

**The match engine**
- Probabilistic engine driven by the selected XI: attack/midfield/defence
  strengths from player attributes, fitness, morale, tactics, and home advantage
- Goals, assists, cards, suspensions (including totting-up bans), injuries,
  clean sheets, and per-player match ratings

**Squads & players**
- Six-attribute players (pace, shooting, passing, defending, physical,
  goalkeeping) with hidden potential, growth curves, and age-related decline
- Youth intake every season, retirements, and multi-decade career records
- Six formations and three mentalities that genuinely change how matches play

**Management**
- Transfer market: scout targets, negotiate bids, field offers for your
  players — while AI clubs strengthen their own squads every window
- Finances: TV money, gate receipts, prize money, parachute payments,
  wage bills, and board intervention when the money runs out
- Save/load any world as JSON, with fully deterministic resumption
  (a reloaded save replays *identically*)

**Multi-year simulation**
- Simulate 1–200 seasons in one command, in-career or as a spectator
- Season-by-season history: champions, cup winners, golden boots,
  players of the season, promotions and relegations
- All-time records: top scorers, most decorated players, club honours
  boards, biggest wins, and a Hall of Fame of retired greats

## Playing a career

1. `python -m fm27` → *New career* → pick a seed (or leave blank), your name,
   and a club.
2. Play matchday by matchday, or hand the reins to your assistant and
   simulate whole seasons at a time (*Sim multiple seasons*).
3. Squad, tables, fixtures, transfers, tactics, finances, club page, and
   history menus are all one keypress away.
4. Save from the menu; saves land in `./saves/`.

Player potential is shown as a band (A ≥ 85, B ≥ 75, C ≥ 65, D below) —
scouting young "A" players cheaply is how small clubs climb.

## Project layout

| Module | Purpose |
| --- | --- |
| `fm27/player.py` | Player attributes, ability, value, development, careers |
| `fm27/club.py` | Squads, tactics, lineup selection, club finances |
| `fm27/match_engine.py` | The probabilistic match simulation |
| `fm27/competition.py` | League scheduling/tables, cup, promotion playoff |
| `fm27/transfers.py` | AI transfer windows and user bids/sales |
| `fm27/world.py` | Season calendar, end-of-season processing, multi-year sims |
| `fm27/records.py` | All-time records and Hall of Fame queries |
| `fm27/save.py` | JSON save/load |
| `fm27/cli.py` | Interactive terminal interface |

## Tests

```bash
python -m unittest discover -s tests
```

The suite covers scheduling correctness, match-engine sanity (home
advantage, strength ordering), full-season and multi-year invariants,
player development, transfer integrity, and deterministic save/load
round-trips.
