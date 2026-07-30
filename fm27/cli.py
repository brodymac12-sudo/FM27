"""Interactive terminal interface for FM27 career mode and spectator sims."""

from __future__ import annotations

from . import data, editor, records
from .club import FORMATIONS, MENTALITIES, Club
from .match_engine import MatchReport
from .player import ATTRS, ATTR_GROUPS
from .save import list_saves, load_world, save_world
from .transfers import (ai_offer_for, execute_loan, execute_transfer,
                        find_loan_host, loan_prospects, loans_in_count,
                        scout_targets, user_bid, would_get_minutes)
from .world import GameWorld

LINE = "─" * 74


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

ATTR_SHORT = {"finishing": "FIN", "dribbling": "DRI", "passing": "PAS",
              "crossing": "CRO", "tackling": "TAC", "heading": "HEA",
              "vision": "VIS", "positioning": "POS", "composure": "COM",
              "work_rate": "WRK", "pace": "PAC", "stamina": "STA",
              "strength": "STR", "reflexes": "REF", "handling": "HAN",
              "aerial": "AER", "kicking": "KIC"}


def print_attr_sheet(attrs: dict, indent: str = "  ") -> None:
    for group, names in ATTR_GROUPS.items():
        row = "  ".join(f"{ATTR_SHORT[a]} {attrs[a]:>2.0f}" for a in names)
        print(f"{indent}{group:<10} {row}")


def player_sheet(world: GameWorld, p) -> None:
    holder = world.clubs.get(p.club_id)
    where = f" — {holder.name}" if holder else ""
    loan = (f" (on loan from {world.clubs[p.loaned_from].name})"
            if p.loaned_from is not None else "")
    print(f"\n  {p.name} — {p.position}, {p.age}, {p.nation}{where}{loan}")
    print(f"  Overall {p.ability:.0f} | Potential {pot_band(p)} | "
          f"Value £{p.value:.1f}M | Wage £{p.wage:.1f}M")
    print(f"  Fitness {p.fitness:.0f} | Morale {p.morale:.0f} | "
          f"This season: {p.season['apps']} apps, {p.season['goals']} goals, "
          f"{p.season['assists']} assists")
    print_attr_sheet(p.attrs)
    if p.trophies:
        print(f"  Honours: {len(p.trophies)} ({', '.join(p.trophies[-3:])})")


def pot_band(p) -> str:
    pot = p.potential
    return "A" if pot >= 85 else "B" if pot >= 75 else "C" if pot >= 65 else "D"


def ca_band(p) -> str:
    lo = int(p.ability) // 5 * 5
    return f"{lo}-{lo + 5}"


def market_line(world: GameWorld, i: int, p) -> str:
    """One row of a market listing — exact numbers only if scouted."""
    owner = world.clubs[p.club_id]
    rep = world.scout_reports.get(p.id)
    if rep:
        ca = f"{rep['ability']:.0f}"
        pot = f"{rep['potential_est']}"
        tag = "★" * rep["stars"]
    else:
        ca, pot, tag = ca_band(p), pot_band(p), "unscouted"
    short = "SL " if p.id in world.shortlist else "   "
    return (f"{i:>3} {short}{p.position:<4}{p.name:<22}{p.age:>3}{ca:>7}{pot:>5}"
            f"{p.value:>8.1f}  {owner.short:<4} {tag}")


def print_table(world: GameWorld, tier: int, highlight: int | None = None) -> None:
    league = world.leagues[tier]
    print(f"\n{league.name} — {world.season_label}")
    print(f"{'':3}{'Club':<26}{'P':>3}{'W':>3}{'D':>3}{'L':>3}"
          f"{'GF':>4}{'GA':>4}{'GD':>4}{'Pts':>5}")
    for pos, row in enumerate(league.table(), start=1):
        club = world.clubs[row["club_id"]]
        marker = "▶" if club.id == highlight else " "
        print(f"{marker}{pos:>2} {club.name:<26}{row['P']:>3}{row['W']:>3}"
              f"{row['D']:>3}{row['L']:>3}{row['GF']:>4}{row['GA']:>4}"
              f"{row['GD']:>4}{row['Pts']:>5}")


def print_squad(world: GameWorld, club: Club) -> None:
    print(f"\n{club.name} squad — formation {club.tactics.formation}, "
          f"{club.tactics.mentality}")
    print(f"{'#':>3} {'Pos':<4}{'Name':<22}{'Age':>3} {'Nat':<12}{'CA':>4}"
          f"{'Pot':>4} {'£M':>6}{'Fit':>4}{'Apps':>5}{'G':>3}{'A':>3}{'Rtg':>5}")
    order = {"GK": 0, "DF": 1, "MF": 2, "FW": 3}
    squad = sorted(club.squad, key=lambda p: (order[p.position], -p.ability))
    for i, p in enumerate(squad, start=1):
        note = ""
        if p.loaned_from is not None:
            note += f" (L:{world.clubs[p.loaned_from].short})"
        if p.injured_for > 0:
            note += f" INJ({p.injured_for})"
        elif p.suspended_for > 0:
            note += f" SUS({p.suspended_for})"
        rtg = f"{p.avg_rating:.2f}" if p.season["apps"] else "  -"
        print(f"{i:>3} {p.position:<4}{p.name:<22}{p.age:>3} {p.nation:<12}"
              f"{p.ability:>4.0f}{pot_band(p):>4} {p.value:>6.1f}"
              f"{p.fitness:>4.0f}{p.season['apps']:>5}{p.season['goals']:>3}"
              f"{p.season['assists']:>3}{rtg:>5}{note}")
    out = world.loaned_out(club)
    if out:
        print("  Out on loan: " + ", ".join(f"{p.name} (at {host.short})"
                                            for p, host in out))
    idx = ask_int("View player # for full attributes (0 to back): ", 0, len(squad))
    if idx:
        player_sheet(world, squad[idx - 1])


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


def event_title(world: GameWorld, ev: dict) -> str:
    if ev["type"] == "league":
        return f"Matchday {ev['round'] + 1} — {world.leagues[ev['tier']].name}"
    if ev["type"] == "cup":
        return f"{data.CUP_NAME}"
    if ev["type"] == "playoff_semis":
        return "Promotion Playoff — Semi-finals"
    return "Promotion Playoff — Final"


def describe_event_results(world: GameWorld, result: dict) -> None:
    ev = result["event"]
    reports = result["reports"]
    print(f"\n{LINE}\n{event_title(world, ev)} — {world.season_label}\n{LINE}")
    uid = world.user_club_id
    user_report = next((r for r in reports if uid in (r.home.id, r.away.id)), None)
    if user_report:
        describe_match(user_report, detailed=True)
        club = world.user_club
        own = [(next((p for p in club.squad if p.id == pid), None), r)
               for pid, r in user_report.ratings.items()]
        own = [(p, r) for p, r in own if p]
        if own:
            star = max(own, key=lambda t: t[1])
            print(f"  Star performer: {star[0].name} ({star[1]:.1f})")
    others = [r for r in reports if r is not user_report]
    if others:
        print("\n  Results:")
        lines = [r.score_line for r in others]
        for i in range(0, len(lines), 4):
            print("    " + " | ".join(lines[i:i + 4]))


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


def next_user_fixture(world: GameWorld) -> str:
    club = world.user_club
    league = world.league_of(club.id)
    for r, h, a in league.fixtures_for(club.id):
        if not any((hh, aa) == (h, a) for hh, aa, _, _ in league.results[r]):
            opp = world.clubs[a if h == club.id else h]
            venue = "H" if h == club.id else "A"
            return f"{opp.name} ({venue})"
    return "—"


# ------------------------------------------------------- transfers and loans

def transfer_menu(world: GameWorld) -> None:
    club = world.user_club
    while True:
        status = "OPEN" if world.window_open else f"CLOSED ({world.next_window_hint()})"
        print(f"\nTransfers & loans — window {status}")
        print(f"  Budget £{club.transfer_budget:.1f}M | wage room "
              f"£{club.wage_budget - club.wage_bill:.1f}M")
        print("  1) Browse market & bid\n  2) Sell a player\n  3) Loan a player in\n"
              "  4) Loan a player out\n  5) Current loans\n  6) Transfer news\n  0) Back")
        choice = ask_int("> ", 0, 6)
        if choice == 0:
            return
        if choice in (1, 2, 3, 4) and not world.window_open:
            print(f"  The transfer window is closed — {world.next_window_hint()}.")
            continue
        if choice == 1:
            _buy_flow(world, club)
        elif choice == 2:
            _sell_flow(world, club)
        elif choice == 3:
            _loan_in_flow(world, club)
        elif choice == 4:
            _loan_out_flow(world, club)
        elif choice == 5:
            _view_loans(world, club)
        else:
            print("\nRecent deals around the league:")
            for line in world.last_window_transfers[:15] or ["  (quiet window)"]:
                print(f"  • {line}")


def _market_filters(world: GameWorld, club: Club):
    pos = ask("Position filter (GK/DF/MF/FW, blank for all): ").upper()
    pos = pos if pos in ("GK", "DF", "MF", "FW") else None
    age_raw = ask("Max age (blank for any): ")
    max_age = int(age_raw) if age_raw.isdigit() else None
    return scout_targets(list(world.clubs.values()), club, pos,
                         max_value=club.transfer_budget * 1.3, max_age=max_age)


def _buy_flow(world: GameWorld, club: Club) -> None:
    targets = _market_filters(world, club)
    if not targets:
        print("  No affordable targets found.")
        return
    print(f"\n{'#':>3}    {'Pos':<4}{'Name':<22}{'Age':>3}{'CA':>7}{'Pot':>5}"
          f"{'£M':>8}  Club")
    for i, p in enumerate(targets, start=1):
        print(market_line(world, i, p))
    print("  (Exact ratings show only for scouted players — see Scouting menu.)")
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
    own = [p for p in club.squad if p.loaned_from is None]
    squad = sorted(own, key=lambda p: -p.value)
    for i, p in enumerate(squad, start=1):
        print(f"{i:>3} {p.position:<4}{p.name:<22} age {p.age}  "
              f"CA {p.ability:.0f}  value £{p.value:.1f}M")
    idx = ask_int("List player # for sale (0 to cancel): ", 0, len(squad))
    if idx == 0:
        return
    player = squad[idx - 1]
    if len(club.squad) <= 15:
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


def _loan_in_flow(world: GameWorld, club: Club) -> None:
    if loans_in_count(club) >= 3:
        print("  You already have three players on loan.")
        return
    candidates = []
    for parent in sorted(world.clubs.values(), key=lambda c: -c.reputation):
        if parent.id == club.id:
            continue
        for p in loan_prospects(parent):
            if would_get_minutes(club, p) or p.ability >= club.squad_strength - 6:
                candidates.append((parent, p))
    candidates.sort(key=lambda t: -t[1].potential)
    candidates = candidates[:20]
    if not candidates:
        print("  No clubs are offering suitable loan players right now.")
        return
    print("\nAvailable on loan (young players needing minutes):")
    print(f"{'#':>3}    {'Pos':<4}{'Name':<22}{'Age':>3}{'CA':>7}{'Pot':>5}"
          f"{'£M':>8}  Club")
    for i, (parent, p) in enumerate(candidates, start=1):
        print(market_line(world, i, p))
    idx = ask_int("Sign # on a season loan (0 to cancel): ", 0, len(candidates))
    if idx == 0:
        return
    parent, player = candidates[idx - 1]
    if club.wage_bill + player.wage > club.wage_budget:
        print("  You can't cover their wages.")
        return
    print(f"  {execute_loan(parent, club, player)}")


def _loan_out_flow(world: GameWorld, club: Club) -> None:
    own = [p for p in club.squad if p.loaned_from is None]
    young = sorted(own, key=lambda p: (p.age, -p.potential))
    for i, p in enumerate(young, start=1):
        print(f"{i:>3} {p.position:<4}{p.name:<22} age {p.age}  CA {p.ability:.0f}  "
              f"pot {pot_band(p)}  apps {p.season['apps']}")
    idx = ask_int("Loan out # for the season (0 to cancel): ", 0, len(young))
    if idx == 0:
        return
    player = young[idx - 1]
    if len(club.squad) <= 15:
        print("  Squad too thin for loans out.")
        return
    host = find_loan_host(world.rng, list(world.clubs.values()), club, player,
                          user_club_id=club.id)
    if host is None:
        print(f"  No club wants {player.name} on loan — he may be too good, "
              "or not good enough, for the clubs below you.")
        return
    print(f"  {host.name} would take {player.name} and play him regularly.")
    if ask("Agree the loan? (y/n): ").lower().startswith("y"):
        print(f"  {execute_loan(club, host, player)}")


def _view_loans(world: GameWorld, club: Club) -> None:
    out = world.loaned_out(club)
    ins = [p for p in club.squad if p.loaned_from is not None]
    if not out and not ins:
        print("  No active loans.")
    for p, host in out:
        print(f"  OUT: {p.name} at {host.name} — {p.season['apps']} apps, "
              f"{p.season['goals']} goals, rating "
              f"{p.avg_rating:.2f}" if p.season["apps"] else
              f"  OUT: {p.name} at {host.name} — no games yet")
    for p in ins:
        parent = world.clubs[p.loaned_from]
        print(f"  IN:  {p.name} from {parent.name} — {p.season['apps']} apps")


# ------------------------------------------------------------------ scouting

def scouting_menu(world: GameWorld) -> None:
    club = world.user_club
    while True:
        print(f"\nScouting network — {world.num_scouts} scouts | "
              f"{len(world.scout_queue)} reports in progress | "
              f"{len(world.scout_reports)} completed")
        print("  1) Search players\n  2) Completed reports\n  3) Shortlist\n"
              "  0) Back")
        c = ask_int("> ", 0, 3)
        if c == 0:
            return
        if c == 1:
            _scout_search(world, club)
        elif c == 2:
            _scout_reports_view(world)
        else:
            _shortlist_view(world)


def _scout_search(world: GameWorld, club: Club) -> None:
    pos = ask("Position (GK/DF/MF/FW, blank any): ").upper()
    pos = pos if pos in ("GK", "DF", "MF", "FW") else None
    age_raw = ask("Max age (blank any): ")
    max_age = int(age_raw) if age_raw.isdigit() else None
    val_raw = ask("Max value £M (blank any): ")
    max_val = float(val_raw) if val_raw.replace(".", "", 1).isdigit() else None
    tier_raw = ask("Division (1=PL, 2=Championship, blank both): ")
    tier = int(tier_raw) - 1 if tier_raw in ("1", "2") else None
    found = scout_targets(list(world.clubs.values()), club, pos,
                          max_value=max_val, max_age=max_age, tier=tier, limit=25)
    if not found:
        print("  Nobody matches those filters.")
        return
    print(f"\n{'#':>3}    {'Pos':<4}{'Name':<22}{'Age':>3}{'CA':>7}{'Pot':>5}"
          f"{'£M':>8}  Club")
    for i, p in enumerate(found, start=1):
        print(market_line(world, i, p))
    while True:
        print("  1) Send scout to watch #   2) Add # to shortlist   0) Back")
        c = ask_int("> ", 0, 2)
        if c == 0:
            return
        idx = ask_int("Player #: ", 1, len(found))
        p = found[idx - 1]
        if c == 1:
            if p.id in world.scout_reports:
                print(f"  Already scouted — check completed reports.")
            elif world.queue_scout(p.id):
                print(f"  Scout dispatched to watch {p.name}. The report lands "
                      "after the next matchday.")
            else:
                print("  Already on a scouting mission.")
        else:
            if p.id not in world.shortlist:
                world.shortlist.append(p.id)
            print(f"  {p.name} shortlisted.")


def _print_report(rep: dict) -> None:
    print(f"\n  Scout report: {rep['name']} ({rep['position']}, {rep['age']}) — "
          f"{rep['club']}{' [on loan]' if rep.get('on_loan') else ''}")
    print(f"  Filed {rep['season']} | Rating {'★' * rep['stars']}"
          f"{'☆' * (5 - rep['stars'])}")
    print(f"  Current ability {rep['ability']:.0f} | Potential est. "
          f"{rep['potential_est']} | Value £{rep['value']:.1f}M | "
          f"Wage £{rep['wage']:.1f}M")
    print_attr_sheet(rep["attrs"])


def _scout_reports_view(world: GameWorld) -> None:
    if not world.scout_reports:
        print("  No completed reports. Send scouts out from Search.")
        return
    reps = sorted(world.scout_reports.values(), key=lambda r: -r["stars"])
    for i, rep in enumerate(reps, start=1):
        print(f"  {i:>2}) {'★' * rep['stars']:<5} {rep['name']:<22} "
              f"{rep['position']} {rep['age']}y — {rep['club']}")
    idx = ask_int("View report # (0 to back): ", 0, len(reps))
    if idx:
        _print_report(reps[idx - 1])


def _shortlist_view(world: GameWorld) -> None:
    if not world.shortlist:
        print("  Shortlist is empty.")
        return
    for i, pid in enumerate(world.shortlist, start=1):
        p, holder = world.find_player(pid)
        if p is None:
            continue
        scouted = "scouted" if pid in world.scout_reports else "unscouted"
        print(f"  {i:>2}) {p.position:<4}{p.name:<22} age {p.age} "
              f"£{p.value:.1f}M — {holder.name} ({scouted})")
    idx = ask_int("Remove # from shortlist (0 to back): ", 0, len(world.shortlist))
    if idx:
        world.shortlist.pop(idx - 1)


# -------------------------------------------------------------------- editor

def editor_menu(world: GameWorld) -> None:
    print("\nIn-game editor — changes apply instantly, no questions asked.")
    query = ask("Search player name (blank to cancel): ")
    if not query:
        return
    hits = editor.find_players(world, query)
    if not hits:
        print("  No players match.")
        return
    for i, (p, c) in enumerate(hits, start=1):
        print(f"  {i:>2}) {p.position:<4}{p.name:<22} age {p.age} "
              f"CA {p.ability:.0f} pot {p.potential} — {c.name}")
    idx = ask_int("Edit # (0 to cancel): ", 0, len(hits))
    if idx == 0:
        return
    player, _ = hits[idx - 1]
    while True:
        print(f"\nEditing {player.name} — {player.position}, age {player.age}, "
              f"CA {player.ability:.0f}, pot {player.potential}")
        print("  1) Rename          5) Set potential")
        print("  2) Set age         6) Heal & restore")
        print("  3) Set position    7) Fitness / morale")
        print("  4) Set attribute   8) Move to another club")
        print("  0) Done")
        c = ask_int("> ", 0, 8)
        if c == 0:
            return
        if c == 1:
            print("  " + editor.set_name(player, ask("New name: ")))
        elif c == 2:
            print("  " + editor.set_age(player, ask_int("New age (15-45): ", 15, 45)))
        elif c == 3:
            print("  " + editor.set_position(player, ask("Position (GK/DF/MF/FW): ")))
        elif c == 4:
            print_attr_sheet(player.attrs)
            attr = ask("Which attribute (full name, e.g. finishing): ").lower()
            if attr not in ATTRS:
                print("  Unknown attribute.")
                continue
            val = ask_int(f"New {attr} (1-99): ", 1, 99)
            print("  " + editor.set_attribute(player, attr, val))
        elif c == 5:
            print("  " + editor.set_potential(player, ask_int("Potential (1-99): ", 1, 99)))
        elif c == 6:
            print("  " + editor.heal(player))
        elif c == 7:
            fit = ask_int("Fitness (1-100): ", 1, 100, default=int(player.fitness))
            mor = ask_int("Morale (1-100): ", 1, 100, default=int(player.morale))
            print("  " + editor.set_condition(player, fit, mor))
        elif c == 8:
            clubs = sorted(world.clubs.values(), key=lambda cl: (cl.division, -cl.reputation))
            for i, cl in enumerate(clubs, start=1):
                end = "\n" if i % 2 == 0 else ""
                print(f"  {i:>2}) {cl.name:<26}", end=end)
            if len(clubs) % 2:
                print()
            di = ask_int("Destination club #: ", 1, len(clubs))
            print("  " + editor.move_player(world, player, clubs[di - 1].id))


# ------------------------------------------------------------- other screens

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
                print(f"  {name:<26} league titles: {lg:<3} cups: {cup}")
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
        print(f"  MD{r + 1:>2} ({venue}) {opp.name:<26} {score}")


# ------------------------------------------------------------------ main loop

def continue_to_next_match(world: GameWorld) -> None:
    """Advance the world until the user's club plays (or the season ends)."""
    scout_msgs: list[str] = []
    uid = world.user_club_id
    while True:
        result = world.advance()
        scout_msgs += result["scout_completed"]
        involved = any(uid in (r.home.id, r.away.id) for r in result["reports"])
        if involved or result["season_summary"]:
            describe_event_results(world, result)
            if result["season_summary"]:
                print_season_summary(result["season_summary"])
            break
    for name in scout_msgs:
        print(f"  📋 Scout report ready: {name} (see Scouting → Completed reports)")
    if world.window_open:
        print("  💷 The transfer window is open.")


def career_loop(world: GameWorld) -> None:
    while True:
        club = world.user_club
        league = world.league_of(club.id)
        pos = league.position_of(club.id)
        print(f"\n{LINE}")
        print(f"{world.season_label} | {club.name} | "
              f"{data.DIVISION_NAMES[club.division]} pos {pos or '-'} | "
              f"Next: {next_user_fixture(world)}")
        print(LINE)
        print("  1) Continue (to your next match)   8) Scouting")
        print("  2) Sim to end of season            9) Tactics")
        print("  3) Sim multiple seasons           10) Finances")
        print("  4) Squad                          11) Club page")
        print("  5) League tables                  12) History & records")
        print("  6) Fixtures & results             13) Player editor")
        print("  7) Transfers & loans              14) Save game")
        print("  0) Quit to main menu")
        choice = ask_int("> ", 0, 14)
        if choice == 0:
            if ask("Quit without saving? (y/n): ").lower().startswith("y"):
                return
        elif choice == 1:
            continue_to_next_match(world)
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
            print_squad(world, club)
        elif choice == 5:
            print_table(world, 0, highlight=club.id)
            print_table(world, 1, highlight=club.id)
        elif choice == 6:
            show_fixtures(world)
        elif choice == 7:
            transfer_menu(world)
        elif choice == 8:
            scouting_menu(world)
        elif choice == 9:
            tactics_menu(club)
        elif choice == 10:
            finances_view(club)
        elif choice == 11:
            club_page(world)
        elif choice == 12:
            history_menu(world)
        elif choice == 13:
            editor_menu(world)
        elif choice == 14:
            name = ask("Save name [career]: ", "career")
            path = save_world(world, name)
            print(f"  Saved to {path}")


def new_career() -> None:
    seed_raw = ask("World seed (blank for random): ")
    seed = int(seed_raw) if seed_raw.isdigit() else None
    print("\nBuilding the world...")
    world = GameWorld.new(seed)
    manager = ask("Your manager name: ", "The Boss")
    world.manager_name = manager
    print("\nChoose your club:")
    all_clubs = sorted(world.clubs.values(), key=lambda c: (c.division, -c.reputation))
    for i, c in enumerate(all_clubs, start=1):
        print(f"  {i:>2}) {c.name:<26} {data.DIVISION_NAMES[c.division]:<15}"
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
        print(f"  {name:<26} league titles: {lg:<3} cups: {cup}")
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
          f"   The English pyramid. Real clubs. Infinite seasons.\n{LINE}")
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
