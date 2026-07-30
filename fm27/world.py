"""The game world: two divisions, a cup, a calendar, and the passage of years.

``GameWorld`` owns every club and player, runs the season calendar one event
at a time (league matchdays, cup rounds, promotion playoffs), performs all
end-of-season processing — awards, promotion/relegation, finances, player
development, retirements, youth intake — and can simulate any number of
seasons in a row while recording history.
"""

from __future__ import annotations

import random

from . import data
from .club import Club, FORMATIONS, build_initial_squad
from .competition import Cup, League, Playoff
from .match_engine import MatchReport
from .player import Player, generate_player
from .transfers import MIN_DEPTH, run_ai_loans, run_ai_window

SQUAD_CAP = 28          # clubs release surplus players beyond this
JAN_WINDOW_LENGTH = 5   # calendar events the mid-season window stays open


class GameWorld:
    def __init__(self, seed: int | None = None):
        self.rng = random.Random(seed)
        self.year = data.START_YEAR
        self.next_pid = 1
        self.clubs: dict[int, Club] = {}
        self.leagues: list[League] = []
        self.cup = Cup(data.CUP_NAME)
        self.playoff = Playoff()
        self.calendar: list[dict] = []
        self.calendar_pos = 0
        self.mid_window_start = 0
        self.user_club_id: int | None = None
        self.manager_name: str | None = None
        self.scout_queue: list[int] = []
        self.scout_reports: dict[int, dict] = {}
        self.shortlist: list[int] = []
        self.history: list[dict] = []
        self.retired: list[dict] = []
        self.records: dict = {"biggest_win": None, "best_season_points": None,
                              "most_goals_in_season": None}
        self.last_window_transfers: list[str] = []

    # ------------------------------------------------------------- world setup

    @classmethod
    def new(cls, seed: int | None = None) -> "GameWorld":
        world = cls(seed)
        cid = 1
        for division, roster in enumerate((data.PREMIER_CLUBS, data.CHAMPIONSHIP_CLUBS)):
            for name, short, rep, cap in roster:
                club = Club(cid, name, short, rep, cap, division)
                build_initial_squad(world.rng, club, world._take_pid)
                club.tactics.formation = world.rng.choice(list(FORMATIONS))
                world.clubs[cid] = club
                cid += 1
        world._start_season(first=True)
        return world

    def _take_pid(self) -> int:
        pid = self.next_pid
        self.next_pid += 1
        return pid

    @property
    def season_label(self) -> str:
        return f"{self.year}/{str(self.year + 1)[2:]}"

    @property
    def user_club(self) -> Club | None:
        return self.clubs.get(self.user_club_id) if self.user_club_id else None

    def division_clubs(self, tier: int) -> list[Club]:
        return [c for c in self.clubs.values() if c.division == tier]

    def league_of(self, club_id: int) -> League:
        tier = self.clubs[club_id].division
        return self.leagues[tier]

    # ------------------------------------------------------------ season start

    def _start_season(self, first: bool = False) -> None:
        news: list[str] = []
        if not first:
            news += [str(t) for t in run_ai_window(self.rng, list(self.clubs.values()),
                                                   self.user_club_id)]
        news += run_ai_loans(self.rng, list(self.clubs.values()), self.user_club_id)
        self.last_window_transfers = news
        self.leagues = []
        for tier, name in enumerate(data.DIVISION_NAMES):
            league = League(name, tier, [c.id for c in self.division_clubs(tier)])
            league.schedule(self.rng)
            self.leagues.append(league)
        self.cup.draw(self.rng, self.clubs)
        self.playoff = Playoff()
        self._build_calendar()
        self.calendar_pos = 0
        for club in self.clubs.values():
            for p in club.squad:
                p.fitness = 100.0
                p.morale = self.rng.uniform(62, 78)
                p.injured_for = 0
                p.suspended_for = 0

    def _build_calendar(self) -> None:
        """Interleave both divisions' matchdays (they differ in length), cup
        rounds, and the promotion playoff into a single event stream."""
        timed: list[tuple[float, int, dict]] = []
        for tier, league in enumerate(self.leagues):
            n = league.num_rounds
            for r in range(n):
                timed.append(((r + 0.5) / n, 1 + tier,
                              {"type": "league", "tier": tier, "round": r}))
        n_cup = Cup.rounds_needed(len(self.clubs))
        for i in range(n_cup - 1):      # early rounds spread through the season
            timed.append((0.10 + 0.72 * i / max(1, n_cup - 2), 0,
                          {"type": "cup", "round": i}))
        timed.append((1.01, 0, {"type": "cup", "round": n_cup - 1}))  # the final
        timed.sort(key=lambda t: (t[0], t[1]))
        cal = [e for _, _, e in timed]
        cal.append({"type": "playoff_semis"})
        cal.append({"type": "playoff_final"})
        self.calendar = cal
        self.mid_window_start = len(cal) // 2

    @property
    def window_open(self) -> bool:
        """Transfers/loans are allowed pre-season and during January."""
        return (self.calendar_pos == 0
                or self.mid_window_start <= self.calendar_pos
                < self.mid_window_start + JAN_WINDOW_LENGTH)

    def next_window_hint(self) -> str:
        if self.window_open:
            return "open now"
        if self.calendar_pos < self.mid_window_start:
            return f"opens in January ({self.mid_window_start - self.calendar_pos} events away)"
        return "opens pre-season"

    # --------------------------------------------------------------- advancing

    @property
    def season_events_left(self) -> int:
        return len(self.calendar) - self.calendar_pos

    def next_event(self) -> dict | None:
        if self.calendar_pos < len(self.calendar):
            return self.calendar[self.calendar_pos]
        return None

    def advance(self) -> dict:
        """Process the next calendar event.

        Returns {"event", "reports", "scout_completed", "season_summary"} —
        the summary is only present when this event closed out the season
        (the next season is started automatically).
        """
        if self.calendar_pos == self.mid_window_start:
            # January: a quieter AI window, plus loan moves.
            deals = [str(t) for t in run_ai_window(
                self.rng, list(self.clubs.values()), self.user_club_id, max_buys=1)]
            deals += run_ai_loans(self.rng, list(self.clubs.values()),
                                  self.user_club_id, max_out=1)
            self.last_window_transfers = deals + self.last_window_transfers
        ev = self.calendar[self.calendar_pos]
        if ev["type"] == "league":
            reports = self.leagues[ev["tier"]].play_round(self.rng, ev["round"],
                                                          self.clubs)
        elif ev["type"] == "cup":
            reports = self.cup.play_round(self.rng, self.clubs)
        elif ev["type"] == "playoff_semis":
            self.playoff.seed(self.leagues[1].table())
            reports = self.playoff.play_semis(self.rng, self.clubs)
        else:
            reports = [self.playoff.play_final(self.rng, self.clubs)]
        self.calendar_pos += 1
        self._track_records(reports)
        self._post_event_recovery({r.home.id for r in reports} | {r.away.id for r in reports})
        completed = self._complete_scout_reports()
        summary = None
        if self.calendar_pos >= len(self.calendar):
            summary = self._finish_season()
            self.year += 1
            self._start_season()
        return {"event": ev, "reports": reports, "scout_completed": completed,
                "season_summary": summary}

    # ---------------------------------------------------------------- scouting

    def find_player(self, pid: int) -> tuple[Player | None, Club | None]:
        for club in self.clubs.values():
            for p in club.squad:
                if p.id == pid:
                    return p, club
        return None, None

    @property
    def num_scouts(self) -> int:
        """Scouting staff size scales with the user club's stature."""
        club = self.user_club
        if club is None:
            return 0
        return max(2, min(4, 1 + club.reputation // 25))

    def queue_scout(self, pid: int) -> bool:
        if pid in self.scout_queue or self.user_club is None:
            return False
        self.scout_queue.append(pid)
        return True

    def _complete_scout_reports(self) -> list[str]:
        """Each matchday, each scout finishes one queued report."""
        done: list[str] = []
        for _ in range(min(self.num_scouts, len(self.scout_queue))):
            pid = self.scout_queue.pop(0)
            p, club = self.find_player(pid)
            if p is None:
                continue
            user = self.user_club
            pot_est = max(int(p.ability),
                          p.potential + self.rng.randint(-3, 3))
            gap = p.ability - user.squad_strength
            upside = pot_est - user.squad_strength
            stars = 1 + (gap > -8) + (gap > -2) + (gap > 4 or upside > 8) + (upside > 14)
            self.scout_reports[pid] = {
                "pid": pid, "name": p.name, "position": p.position,
                "age": p.age, "club": club.name,
                "season": self.season_label,
                "ability": round(p.ability, 1),
                "potential_est": pot_est,
                "attrs": {k: round(v) for k, v in p.attrs.items()},
                "value": p.value, "wage": p.wage,
                "stars": min(5, stars),
                "on_loan": p.loaned_from is not None,
            }
            done.append(p.name)
        return done

    # ------------------------------------------------------------------- loans

    def loaned_out(self, club: Club) -> list[tuple[Player, Club]]:
        """Players owned by ``club`` currently playing elsewhere."""
        out = []
        for host in self.clubs.values():
            for p in host.squad:
                if p.loaned_from == club.id:
                    out.append((p, host))
        return out

    def _return_loans(self) -> None:
        for host in self.clubs.values():
            for p in [p for p in host.squad if p.loaned_from is not None]:
                parent = self.clubs[p.loaned_from]
                host.remove_player(p)
                p.loaned_from = None
                parent.add_player(p)

    def _post_event_recovery(self, played_club_ids: set[int]) -> None:
        for club in self.clubs.values():
            for p in club.squad:
                p.fitness = min(100.0, p.fitness + 9.0)
                if p.injured_for > 0:
                    p.injured_for -= 1
                elif p.suspended_for > 0 and club.id in played_club_ids:
                    p.suspended_for -= 1

    def _track_records(self, reports: list[MatchReport]) -> None:
        for rep in reports:
            margin = abs(rep.home_goals - rep.away_goals)
            best = self.records["biggest_win"]
            if margin >= 4 and (best is None or margin > best["margin"]):
                self.records["biggest_win"] = {"margin": margin,
                                               "line": rep.score_line,
                                               "season": self.season_label}

    # ------------------------------------------------------------- season end

    def _finish_season(self) -> dict:
        label = self.season_label
        summary: dict = {"season": label, "champions": {}, "champion_points": {},
                         "promoted": [], "relegated": [], "awards": {},
                         "transfers": self.last_window_transfers[:6]}

        tables = [lg.table() for lg in self.leagues]
        for league, table in zip(self.leagues, tables):
            champ = self.clubs[table[0]["club_id"]]
            champ.add_trophy(league.name, label)
            summary["champions"][league.name] = champ.name
            summary["champion_points"][league.name] = table[0]["Pts"]
            for pos, row in enumerate(table, start=1):
                club = self.clubs[row["club_id"]]
                club.season_finishes.append((label, league.tier, pos))
            self._award_squad_trophy(champ, f"{label} {league.name}")

        cup_winner = self.clubs[self.cup.winner_id]
        cup_winner.add_trophy(self.cup.name, label)
        self._award_squad_trophy(cup_winner, f"{label} {self.cup.name}")
        summary["cup_winner"] = cup_winner.name

        best_pts = self.records["best_season_points"]
        top_pts = summary["champion_points"][data.DIVISION_NAMES[0]]
        if best_pts is None or top_pts > best_pts["points"]:
            self.records["best_season_points"] = {
                "points": top_pts, "club": summary["champions"][data.DIVISION_NAMES[0]],
                "season": label}

        summary["awards"] = self._season_awards(label)
        self._promotion_relegation(tables, summary)
        self._settle_finances(tables)
        self._develop_and_age()      # loanees develop on their loan-club minutes
        self._return_loans()
        summary["retired"] = self._process_retirements()
        self._youth_intake()
        summary["released"] = self._trim_squads()
        self.shortlist = [pid for pid in self.shortlist if self.find_player(pid)[0]]
        self.scout_queue = [pid for pid in self.scout_queue if self.find_player(pid)[0]]
        if self.user_club:
            summary["user_club"] = self.user_club.name
            summary["user_division"] = data.DIVISION_NAMES[self.user_club.division]
        self.history.append(summary)
        return summary

    def _award_squad_trophy(self, club: Club, title: str) -> None:
        for p in club.squad:
            if p.season["apps"] >= 5:
                p.trophies.append(title)

    def _season_awards(self, label: str) -> dict:
        players = [(p, c) for c in self.clubs.values() for p in c.squad]
        awards: dict = {}
        scorer, s_club = max(players, key=lambda t: (t[0].season["goals"],
                                                     t[0].season["assists"]))
        awards["top_scorer"] = {"name": scorer.name, "club": s_club.name,
                                "goals": scorer.season["goals"]}
        record = self.records["most_goals_in_season"]
        if record is None or scorer.season["goals"] > record["goals"]:
            self.records["most_goals_in_season"] = {
                "name": scorer.name, "club": s_club.name,
                "goals": scorer.season["goals"], "season": label}
        eligible = [(p, c) for p, c in players if p.season["apps"] >= 15]
        if eligible:
            best, b_club = max(eligible, key=lambda t: t[0].avg_rating)
            awards["player_of_season"] = {"name": best.name, "club": b_club.name,
                                          "rating": round(best.avg_rating, 2)}
        young = [(p, c) for p, c in players if p.age <= 21 and p.season["apps"] >= 10]
        if young:
            wonder, w_club = max(young, key=lambda t: t[0].avg_rating)
            awards["young_player"] = {"name": wonder.name, "club": w_club.name,
                                      "rating": round(wonder.avg_rating, 2),
                                      "age": wonder.age}
        return awards

    def _promotion_relegation(self, tables: list[list[dict]], summary: dict) -> None:
        prem_table, champ_table = tables
        relegated = [self.clubs[row["club_id"]] for row in prem_table[-3:]]
        promoted = [self.clubs[row["club_id"]] for row in champ_table[:2]]
        playoff_club = self.clubs[self.playoff.winner_id]
        if playoff_club not in promoted:
            promoted.append(playoff_club)
        else:  # playoff winner already auto-promoted can't happen (3rd-6th), guard anyway
            promoted.append(self.clubs[champ_table[2]["club_id"]])
        summary["playoff_winner"] = playoff_club.name
        summary["relegated"] = [c.name for c in relegated]
        summary["promoted"] = [c.name for c in promoted]
        for club in relegated:
            club.division = 1
            club.reputation = max(40, club.reputation - 2)
        for club in promoted:
            club.division = 0
            club.reputation = min(95, club.reputation + 2)
        champion = self.clubs[prem_table[0]["club_id"]]
        champion.reputation = min(95, champion.reputation + 1)

    def _settle_finances(self, tables: list[list[dict]]) -> None:
        cup_prize = {self.cup.winner_id: 6.0}
        # TV deals grow over time, offsetting gradual wage inflation.
        tv_growth = 1.010 ** (self.year - data.START_YEAR)
        for tier, table in enumerate(tables):
            for pos, row in enumerate(table, start=1):
                club = self.clubs[row["club_id"]]
                if tier == 0:
                    tv = (85.0 + (len(table) - pos) * 4.0) * tv_growth
                    prize_money = max(0.0, (len(table) - pos) * 1.5)
                    # Parachute payment cushions the drop for relegated clubs.
                    if pos > len(table) - 3:
                        prize_money += 15.0
                else:
                    tv = (12.0 + (len(table) - pos) * 1.0) * tv_growth
                    prize_money = 8.0 + max(0.0, (len(table) - pos) * 0.25)
                fill = min(1.0, 0.45 + club.reputation / 130.0)
                gate = club.capacity * fill * 32 * 13 / 1_000_000
                revenue = tv + gate + prize_money + cup_prize.get(club.id, 0.0)
                # Wealthy clubs spend more on facilities/operations — a soft
                # damper that stops cash piles compounding forever.
                op_rate = 0.24 + min(0.30, max(0.0, club.balance) / 1500.0)
                net = revenue * (1 - op_rate) - club.wage_bill
                club.balance = round(club.balance + net, 2)
                if club.balance < 0:
                    # The board refinances most of the deficit; the squeeze
                    # shows up as a tiny transfer budget instead.
                    club.balance = round(club.balance * 0.4, 2)
                club.transfer_budget = round(
                    min(160.0, max(2.0, club.balance * 0.25 + revenue * 0.15)), 2)
                club.wage_budget = round(max(12.0, revenue * 0.62), 2)

    def _develop_and_age(self) -> None:
        for club in self.clubs.values():
            max_apps = max((p.season["apps"] for p in club.squad), default=1)
            for p in club.squad:
                share = p.season["apps"] / max(1, max_apps)
                p.develop(self.rng, share, club.training_quality)
                p.age_one_year()

    def _process_retirements(self) -> list[str]:
        notes = []
        for club in self.clubs.values():
            for p in list(club.squad):
                chance = 0.0
                if p.age >= 33:
                    chance = (p.age - 32) * 0.28
                if p.age >= 30 and p.ability < 45:
                    chance = max(chance, 0.5)
                if p.age >= 40 or self.rng.random() < chance:
                    club.remove_player(p)
                    self.retired.append({
                        "name": p.name, "nation": p.nation, "position": p.position,
                        "retired_age": p.age, "last_club": club.name,
                        "career": dict(p.career), "trophies": list(p.trophies),
                        "season": self.season_label,
                    })
                    if p.career["goals"] >= 100 or p.career["apps"] >= 350:
                        notes.append(f"{p.name} ({club.short}) retires — "
                                     f"{p.career['goals']} goals in "
                                     f"{p.career['apps']} games")
        return notes[:8]

    def _youth_intake(self) -> None:
        for club in self.clubs.values():
            for _ in range(self.rng.randint(3, 4)):
                pos = self.rng.choices(["GK", "DF", "MF", "FW"],
                                       weights=[1, 3, 3, 2])[0]
                age = self.rng.randint(16, 18)
                target = club.reputation * 0.55 + self.rng.uniform(-6, 6)
                youth = generate_player(self.rng, self._take_pid(), pos, age, target)
                youth.potential = int(min(97, max(
                    youth.potential,
                    club.reputation + self.rng.uniform(-12, 10))))
                club.add_player(youth)
            # Emergency depth so a selling club can always field a team.
            while len(club.squad) < 16:
                pos = self.rng.choice(["GK", "DF", "MF", "FW"])
                filler = generate_player(self.rng, self._take_pid(), pos,
                                         self.rng.randint(19, 23),
                                         club.reputation * 0.7)
                club.add_player(filler)

    def _trim_squads(self) -> dict[str, int]:
        """Release surplus players so squads (and wage bills) stay bounded.

        The weakest players go first, but promising youngsters are protected
        by valuing their potential upside. Returns {club name: released count}
        for clubs that let anyone go.
        """
        released: dict[str, int] = {}
        for club in self.clubs.values():
            while len(club.squad) > SQUAD_CAP:
                candidates = sorted(
                    (p for p in club.squad if p.loaned_from is None),
                    key=lambda p: p.ability + max(0, p.potential - p.ability) * 0.6)
                for p in candidates:
                    if len(club.players_at(p.position)) > MIN_DEPTH[p.position]:
                        club.remove_player(p)
                        released[club.name] = released.get(club.name, 0) + 1
                        break
                else:
                    break  # nobody can be spared without gutting a position
        return released

    # --------------------------------------------------------- bulk simulation

    def simulate_rest_of_season(self) -> dict:
        """Run every remaining event this season; returns the season summary."""
        summary = None
        while summary is None:
            summary = self.advance()["season_summary"]
        return summary

    def simulate_years(self, n: int, progress=None) -> list[dict]:
        """Simulate ``n`` full seasons (finishing the current one first).

        ``progress`` is an optional callback receiving each season summary as
        it completes — handy for streaming output during long sims.
        """
        summaries = []
        for _ in range(n):
            summary = self.simulate_rest_of_season()
            summaries.append(summary)
            if progress:
                progress(summary)
        return summaries

    # ------------------------------------------------------------ serialization

    def to_dict(self) -> dict:
        state = self.rng.getstate()
        return {
            "version": 1,
            "year": self.year,
            "next_pid": self.next_pid,
            "user_club_id": self.user_club_id,
            "manager_name": self.manager_name,
            "clubs": [c.to_dict() for c in self.clubs.values()],
            "leagues": [lg.to_dict() for lg in self.leagues],
            "cup": self.cup.to_dict(),
            "playoff": self.playoff.to_dict(),
            "calendar": self.calendar,
            "calendar_pos": self.calendar_pos,
            "mid_window_start": self.mid_window_start,
            "scout_queue": self.scout_queue,
            "scout_reports": self.scout_reports,
            "shortlist": self.shortlist,
            "history": self.history,
            "retired": self.retired,
            "records": self.records,
            "last_window_transfers": self.last_window_transfers,
            "rng_state": [state[0], list(state[1]), state[2]],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GameWorld":
        world = cls()
        world.year = d["year"]
        world.next_pid = d["next_pid"]
        world.user_club_id = d["user_club_id"]
        world.manager_name = d["manager_name"]
        world.clubs = {c["id"]: Club.from_dict(c) for c in d["clubs"]}
        world.leagues = [League.from_dict(lg) for lg in d["leagues"]]
        world.cup = Cup.from_dict(d["cup"])
        world.playoff = Playoff.from_dict(d["playoff"])
        world.calendar = d["calendar"]
        world.calendar_pos = d["calendar_pos"]
        world.mid_window_start = d.get("mid_window_start", len(d["calendar"]) // 2)
        world.scout_queue = d.get("scout_queue", [])
        world.scout_reports = {int(k): v for k, v in d.get("scout_reports", {}).items()}
        world.shortlist = d.get("shortlist", [])
        world.history = d["history"]
        world.retired = d["retired"]
        world.records = d["records"]
        world.last_window_transfers = d["last_window_transfers"]
        s = d["rng_state"]
        world.rng.setstate((s[0], tuple(s[1]), s[2]))
        return world
