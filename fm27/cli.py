"""Interactive terminal interface for FM27 career mode and spectator sims."""

from __future__ import annotations

import random

from . import data, records
from .club import FORMATIONS, MENTALITIES, Club
from .match_engine import MatchReport
from .save import list_saves, load_world, save_world
from .transfers import ai_offer_for, execute_transfer, scout_targets, user_bid
from .world import GameWorld

LINE = "─" * 72


# ------------------------------------------------------------- input helpers

def ask(prompt: str, default: str | None = None) -> str:
    try:
        raw = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\nGoodbye.")
        raise SystemExit(0)
    return raw or (default or "")


def ask_int(prompt: str, lo: int, hi: int, default: int | None = None) -> int:
    while True:
        raw = ask(prompt, str(default) if default is not None else None)
        try:
            v = int(raw)
            if lo <= v <= hi:
                return v
        except ValueError:
            pass
        print(f"  Enter a number between {lo} and {hi}.")


def ask_float(prompt: str, lo: float, hi: float, default: float | None = None) -> float:
    while True:
        raw = ask(prompt, f"{default:.1f}" if default is not None else None)
        try:
            v = float(raw)
            if lo <= v <= hi:
                return v
        except ValueError:
            pass
        print(f"  Enter an amount between {lo:.1f} and {hi:.1f}.")


# ---------------------------------------------------------------- formatting

def pot_band(p) -> str:
    pot = p.potential
    return "A" if pot >= 85 else "B" if pot >= 75 else "C" if pot >= 65 else "D"


def print_table(world: GameWorld, tier: int, highlight: int | None = None) -> None:
    league = world.leagues[tier]
    print(f"\n{league.name} — {world.season_label}")
    print(f"{'':3}{'Club':<24}{'P':>3}{'W':>3}{'D':>3}{'L':>3}"
          f"{'GF':>4}{'GA':>4}{'GD':>4}{'Pts':>5}")
    for pos, row in enumerate(league.table(), start=1):
        club = world.clubs[row["club_id"]]
        marker = "▶" if club.id == highlight else " "
        print(f"{marker}{pos:>2} {club.name:<24}{row['P']:>3}{row['W']:>3}"
              f"{row['D']:>3}{row['L']:>3}{row['GF']:>4}{row['GA']:>4}"
              f"{row['GD']:>4}{row['Pts']:>5}")


def print_squad(club: Club) -> None:
    print(f"\n{club.name} squad — formation {club.tactics.formation}, "
          f"{club.tactics.mentality}")
    print(f"{'#':>3} {'Pos':<4}{'Name':<22}{'Age':>3} {'Nat':<12}{'CA':>4}"
          f"{'Pot':>4} {'£M':>6}{'Fit':>4}{'Apps':>5}{'G':>3}{'A':>3}{'Rtg':>5}")
    order = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
    squad = sorted(club.squad, key=lambda p: (order[p.position], -p.ability))
    for i, p in enumerate(squad, start=1):
        note = ""
        if p.injured_for > 0:
            note = f" INJ({p.injured_for})"
        elif p.suspended_for > 0:
            note = f" SUS({p.suspended_for})"
        rtg = f"{p.avg_rating:.2f}" if p.season["apps"] else "  -"
        print(f"{i:>3} {p.position:<4}{p.name:<22}{p.age:>3} {p.nation:<12}"
              f"{p.ability:>4.0f}{pot_band(p):>4} {p.value:>6.1f}"
              f"{p.fitness:>4.0f}{p.season['apps']:>5}{p.season['goals']:>3}"
              f"{p.season['assists']:>3}{rtg:>5}{note}")


def describe_match(rep: MatchReport, detailed: bool) -> None:
    print(f"\n  {rep.home.name} vs {rep.away.name} [{rep.competition}]")
    print(f"  FULL TIME: {rep.score_line}")
    if not detailed:
        return
    for e in rep.events:
        club = rep.home if e["club_id"] == rep.home.id else rep.away
        if e["type"] == "goal":
            extra = f" ({e['detail']})" if e["detail"] else ""
            print(f"    {e['minute']:>3}' ⚽ GOAL {club.short} — {e['player']}{extra}")
        elif e["type"] == "red":
            print(f"    {e['minute']:>3}' 🟥 RED {club.short} — {e['player']}")
        elif e["type"] == "injury":
            print(f"    {e['minute']:>3}' 🚑 {club.short} — {e['player']} injured, {e['detail']}")


def describe_event_results(world: GameWorld, result: dict) -> None:
    ev = result["event"]
    reports = result["reports"]
    if ev["type"] == "league":
        title = f"Matchday {ev['round'] + 1}"
    elif ev["type"] == "cup":
        title = f"{data.CUP_NAME}"
    elif ev["type"] == "playoff_semis":
        title = "Promotion Playoff — Semi-finals"
    else:
        title = "Promotion Playoff — Final"
    print(f"\n{LINE}\n{title} — {world.season_label}\n{LINE}")
    uid = world.user_club_id
    user_report = next((r for r in reports if uid in (r.home.id, r.away.id)), None)
    if user_report:
        describe_match(user_report, detailed=True)
        xi_ratings = [(pid, r) for pid, r in user_report.ratings.items()]
        club = world.user_club
        own = [(next((p for p in club.squad if p.id == pid), None), r)
               for pid, r in xi_ratings]
        own = [(p, r) for p, r in own if p]
        if own:
            star = max(own, key=lambda t: t[1])
            print(f"  Star performer: {star[0].name} ({star[1]:.1f})")
    others = [r for r in reports if r is not user_report]
    if others:
        print("\n  Results: " + ", ".join(r.score_line for r in others))


def print_season_summary(summary: dict) -> None:
    print(f"\n{LINE}\n★ SEASON {summary['season']} REVIEW ★\n{LINE}")
    for div, champ in summary["champions"].items():
        print(f"  {div} champions: {champ} ({summary['champion_points'][div]} pts)")
    print(f"  {data.CUP_NAME} winners: {summary['cup_winner']}")
    print(f"  Playoff winners: {summary['playoff_winner']}")
    print(f"  Promoted: {', '.join(summary['promoted'])}")
    print(f"  Relegated: {', '.join(summary['relegated'])}")
    awards = summary["awards"]
    ts = awards["top_scorer"]
    print(f"  Golden Boot: {ts['name']} ({ts['club']}) — {ts['goals']} goals")
    if "player_of_season" in awards:
        ps = awards["player_of_season"]
        print(f"  Player of the Season: {ps['name']} ({ps['club']}) — {ps['rating']} avg")
    if "young_player" in awards:
        yp = awards["young_player"]
        print(f"  Young Player: {yp['name']} ({yp['club']}), age {yp['age']}")
    for note in summary.get("retired", []):
        print(f"  📣 {note}")


def one_line_summary(summary: dict) -> str:
    champ = summary["champions"][data.DIVISION_NAMES[0]]
    ts = summary["awards"]["top_scorer"]
    return (f"{summary['season']}: 🏆 {champ} | Cup: {summary['cup_winner']} | "
            f"Boot: {ts['name']} ({ts['goals']})")


# --------------------------------------------------------------- career menus

def transfer_menu(world: GameWorld) -> None:
    club = world.user_club
    while True:
        print(f"\nTransfer market — budget £{club.transfer_budget:.1f}M, "
              f"wage room £{club.wage_budget - club.wage_bill:.1f}M")
        print("  1) Scout & bid for players\n  2) Sell a player\n"
              "  3) Latest transfer news\n  0) Back")
        choice = ask_int("> ", 0, 3)
        if choice == 0:
            return
        if choice == 1:
            _buy_flow(world, club)
        elif choice == 2:
            _sell_flow(world, club)
        else:
            print("\nRecent deals around the league:")
            for line in world.last_window_transfers or ["  (quiet window)"]:
                print(f"  • {line}")


def _buy_flow(world: GameWorld, club: Club) -> None:
    pos = ask("Position filter (GK/DF/MF/FW, blank for all): ").upper()
    pos = pos if pos in ("GK", "DF", "MF", "FW") else None
    targets = scout_targets(list(world.clubs.values()), club, pos,
                            max_value=club.transfer_budget * 1.3)
    if not targets:
        print("  No affordable targets found.")
        return
    print(f"\n{'#':>3} {'Pos':<4}{'Name':<22}{'Age':>3}{'CA':>4}{'Pot':>4}"
          f"{'£M':>7}  Club")
    for i, p in enumerate(targets, start=1):
        owner = world.clubs[p.club_id]
        print(f"{i:>3} {p.position:<4}{p.name:<22}{p.age:>3}{p.ability:>4.0f}"
              f"{pot_band(p):>4}{p.value:>7.1f}  {owner.name}")
    idx = ask_int("Bid for # (0 to cancel): ", 0, len(targets))
    if idx == 0:
        return
    target = targets[idx - 1]
    seller = world.clubs[target.club_id]
    bid = ask_float(f"Your bid in £M (value £{target.value:.1f}M): ",
                    0.1, max(0.2, club.transfer_budget),
                    default=min(club.transfer_budget, target.value * 1.2))
    ok, msg = user_bid(club, seller, target, bid)
    print(f"  {msg}")


def _sell_flow(world: GameWorld, club: Club) -> None:
    squad = sorted(club.squad, key=lambda p: -p.value)
    for i, p in enumerate(squad, start=1):
        print(f"{i:>3} {p.position:<4}{p.name:<22} age {p.age}  "
              f"CA {p.ability:.0f}  value £{p.value:.1f}M")
    idx = ask_int("List player # for sale (0 to cancel): ", 0, len(squad))
    if idx == 0:
        return
    player = squad[idx - 1]
    if len(club.squad) <= 14:
        print("  Squad too thin to sell anyone.")
        return
    offer = ai_offer_for(world.rng, list(world.clubs.values()), club, player)
    if offer is None:
        print(f"  No club came in for {player.name} this time.")
        return
    buyer, fee = offer
    print(f"  {buyer.name} offer £{fee:.1f}M for {player.name} "
          f"(valued £{player.value:.1f}M).")
    if ask("Accept? (y/n): ").lower().startswith("y"):
        t = execute_transfer(buyer, club, player, fee)
        print(f"  {t}")
    else:
        print("  Offer rejected.")


def tactics_menu(club: Club) -> None:
    forms = list(FORMATIONS)
    print("\nFormations: " + ", ".join(f"{i + 1}) {f}" for i, f in enumerate(forms)))
    fi = ask_int(f"Pick formation (current {club.tactics.formation}): ", 1, len(forms))
    club.tactics.formation = forms[fi - 1]
    print("Mentality: " + ", ".join(f"{i + 1}) {m}" for i, m in enumerate(MENTALITIES)))
    mi = ask_int(f"Pick mentality (current {club.tactics.mentality}): ", 1, len(MENTALITIES))
    club.tactics.mentality = MENTALITIES[mi - 1]
    print(f"  Set: {club.tactics.formation}, {club.tactics.mentality}.")


def finances_view(club: Club) -> None:
    print(f"\n{club.name} finances")
    print(f"  Balance:          £{club.balance:>8.1f}M")
    print(f"  Transfer budget:  £{club.transfer_budget:>8.1f}M")
    print(f"  Wage budget:      £{club.wage_budget:>8.1f}M / bill £{club.wage_bill:.1f}M")
    top = sorted(club.squad, key=lambda p: -p.wage)[:5]
    print("  Top earners: " + ", ".join(f"{p.name} £{p.wage:.1f}M" for p in top))


def history_menu(world: GameWorld) -> None:
    while True:
        print("\nHistory & records\n  1) Past seasons\n  2) All-time top scorers\n"
              "  3) Most decorated players\n  4) Club honours board\n"
              "  5) Hall of fame\n  6) World records\n  0) Back")
        c = ask_int("> ", 0, 6)
        if c == 0:
            return
        if c == 1:
            if not world.history:
                print("  No completed seasons yet.")
            for s in world.history[-20:]:
                print("  " + one_line_summary(s))
        elif c == 2:
            for i, e in enumerate(records.all_time_scorers(world), start=1):
                tag = "" if e["status"] == "active" else " (retired)"
                print(f"  {i:>2}. {e['name']:<22} {e['goals']:>4} goals in "
                      f"{e['apps']} apps — {e['club']}{tag}")
        elif c == 3:
            for i, e in enumerate(records.most_decorated_players(world), start=1):
                print(f"  {i:>2}. {e['name']:<22} {e['trophies']} trophies — {e['club']}")
        elif c == 4:
            rows = records.title_counts(world)
            if not rows:
                print("  Honours boards are bare — simulate some seasons!")
            for name, lg, cup in rows:
                print(f"  {name:<24} league titles: {lg:<3} cups: {cup}")
        elif c == 5:
            hof = records.hall_of_fame(world)
            if not hof:
                print("  The Hall of Fame awaits its first inductee.")
            for e in hof:
                print(f"  {e['name']:<22} {e['position']} — {e['career']['goals']} goals, "
                      f"{e['career']['apps']} apps, {len(e['trophies'])} trophies "
                      f"(retired {e['season']})")
        else:
            r = world.records
            if r["biggest_win"]:
                b = r["biggest_win"]
                print(f"  Biggest win: {b['line']} ({b['season']})")
            if r["best_season_points"]:
                b = r["best_season_points"]
                print(f"  Best title-winning points: {b['club']} — {b['points']} "
                      f"({b['season']})")
            if r["most_goals_in_season"]:
                b = r["most_goals_in_season"]
                print(f"  Most goals in a season: {b['name']} ({b['club']}) — "
                      f"{b['goals']} ({b['season']})")


def club_page(world: GameWorld) -> None:
    club = world.user_club
    print(f"\n{club.name} — {data.DIVISION_NAMES[club.division]}")
    if club.trophies:
        for comp, seasons in club.trophies.items():
            print(f"  {comp}: {len(seasons)} ({', '.join(seasons[-5:])})")
    for season, tier, pos in club.season_finishes[-10:]:
        print(f"  {season}: {pos}{_ordinal(pos)} in {data.DIVISION_NAMES[tier]}")


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def show_fixtures(world: GameWorld) -> None:
    club = world.user_club
    league = world.league_of(club.id)
    print(f"\n{club.name} — league fixtures {world.season_label}")
    for r, h, a in league.fixtures_for(club.id):
        played = next(((hg, ag) for hh, aa, hg, ag in league.results[r]
                       if (hh, aa) == (h, a)), None)
        opp = world.clubs[a if h == club.id else h]
        venue = "H" if h == club.id else "A"
        score = f"{played[0]}-{played[1]}" if played else "  -  "
        print(f"  MD{r + 1:>2} ({venue}) {opp.name:<24} {score}")


# ------------------------------------------------------------------ main loop

def career_loop(world: GameWorld) -> None:
    while True:
        club = world.user_club
        league = world.league_of(club.id)
        pos = league.position_of(club.id)
        nxt = world.next_event()
        nxt_str = {"league": f"Matchday {nxt['round'] + 1}" if nxt else "",
                   "cup": "Cup round", "playoff_semis": "Playoff semis",
                   "playoff_final": "Playoff final"}.get(nxt["type"], "") if nxt else "season end"
        print(f"\n{LINE}")
        print(f"{world.season_label} | {club.name} | "
              f"{data.DIVISION_NAMES[club.division]} pos {pos or '-'} | "
              f"Manager: {world.manager_name} | Next: {nxt_str}")
        print(LINE)
        print("  1) Continue (play next matchday)   6) Fixtures & results")
        print("  2) Sim to end of season            7) Transfer market")
        print("  3) Sim multiple seasons            8) Tactics")
        print("  4) Squad                           9) Finances")
        print("  5) League tables                  10) Club page")
        print(" 11) History & records              12) Save game")
        print("  0) Quit to main menu")
        choice = ask_int("> ", 0, 12)
        if choice == 0:
            if ask("Quit without saving? (y/n): ").lower().startswith("y"):
                return
        elif choice == 1:
            result = world.advance()
            describe_event_results(world, result)
            if result["season_summary"]:
                print_season_summary(result["season_summary"])
        elif choice == 2:
            summary = world.simulate_rest_of_season()
            print_season_summary(summary)
        elif choice == 3:
            years = ask_int("How many seasons to simulate (1-100)? ", 1, 100)
            print(f"\nSimulating {years} season(s) — your assistant handles team "
                  "selection while you watch the years roll by...\n")
            world.simulate_years(years,
                                 progress=lambda s: print("  " + one_line_summary(s)))
            print("\nDone. The world has moved on — check the history menus.")
        elif choice == 4:
            print_squad(club)
        elif choice == 5:
            print_table(world, 0, highlight=club.id)
            print_table(world, 1, highlight=club.id)
        elif choice == 6:
            show_fixtures(world)
        elif choice == 7:
            transfer_menu(world)
        elif choice == 8:
            tactics_menu(club)
        elif choice == 9:
            finances_view(club)
        elif choice == 10:
            club_page(world)
        elif choice == 11:
            history_menu(world)
        elif choice == 12:
            name = ask("Save name [career]: ", "career")
            path = save_world(world, name)
            print(f"  Saved to {path}")


def new_career() -> None:
    seed_raw = ask("World seed (blank for random): ")
    seed = int(seed_raw) if seed_raw.isdigit() else None
    print("\nBuilding the world...")
    world = GameWorld.new(seed)
    manager = ask("Your manager name [Alex Ferguson-alike]: ", "The Boss")
    world.manager_name = manager
    print("\nChoose your club:")
    all_clubs = sorted(world.clubs.values(), key=lambda c: (c.division, -c.reputation))
    for i, c in enumerate(all_clubs, start=1):
        print(f"  {i:>2}) {c.name:<24} {data.DIVISION_NAMES[c.division]:<18}"
              f"rep {c.reputation}  budget £{c.transfer_budget:.0f}M")
    idx = ask_int("> ", 1, len(all_clubs))
    world.user_club_id = all_clubs[idx - 1].id
    print(f"\nWelcome to {world.user_club.name}, {manager}! The board expects "
          "steady progress. Good luck.")
    career_loop(world)


def spectator_sim() -> None:
    years = ask_int("Seasons to simulate (1-200): ", 1, 200)
    seed_raw = ask("World seed (blank for random): ")
    seed = int(seed_raw) if seed_raw.isdigit() else None
    world = GameWorld.new(seed)
    run_spectator(world, years)
    if ask("Save this world? (y/n): ").lower().startswith("y"):
        name = ask("Save name [world]: ", "world")
        print(f"  Saved to {save_world(world, name)}")


def run_spectator(world: GameWorld, years: int) -> None:
    print(f"\nSimulating {years} season(s) of the football pyramid...\n")
    world.simulate_years(years, progress=lambda s: print("  " + one_line_summary(s)))
    print(f"\n{LINE}\nAfter {years} more season(s):\n")
    print("Most successful clubs:")
    for name, lg, cup in records.title_counts(world)[:8]:
        print(f"  {name:<24} league titles: {lg:<3} cups: {cup}")
    print("\nAll-time top scorers:")
    for i, e in enumerate(records.all_time_scorers(world, 8), start=1):
        tag = "" if e["status"] == "active" else " (retired)"
        print(f"  {i}. {e['name']} — {e['goals']} goals{tag}")
    hof = records.hall_of_fame(world, 5)
    if hof:
        print("\nHall of Fame inductees:")
        for e in hof:
            print(f"  {e['name']} ({e['position']}) — {len(e['trophies'])} trophies, "
                  f"{e['career']['goals']} goals")


def main_menu() -> None:
    print(f"\n{LINE}\n            FM27 — FOOTBALL MANAGER 27\n"
          f"     Two divisions. One cup. Infinite seasons.\n{LINE}")
    while True:
        print("\n  1) New career\n  2) Load game\n  3) Spectator multi-year sim\n"
              "  0) Quit")
        c = ask_int("> ", 0, 3)
        if c == 0:
            print("Thanks for playing FM27.")
            return
        if c == 1:
            new_career()
        elif c == 2:
            saves = list_saves()
            if not saves:
                print("  No saves found.")
                continue
            for i, s in enumerate(saves, start=1):
                print(f"  {i}) {s}")
            idx = ask_int("> ", 1, len(saves))
            world = load_world(saves[idx - 1])
            if world.user_club_id:
                career_loop(world)
            else:
                years = ask_int("Seasons to simulate (1-200): ", 1, 200)
                run_spectator(world, years)
        elif c == 3:
            spectator_sim()
