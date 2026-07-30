"""Competitions: round-robin leagues, the national knockout cup, and playoffs."""

from __future__ import annotations

import random

from .club import Club
from .match_engine import MatchReport, simulate_match


def round_robin_rounds(club_ids: list[int]) -> list[list[tuple[int, int]]]:
    """Double round-robin schedule via the circle method.

    Returns a list of rounds; each round is a list of (home_id, away_id).
    """
    ids = list(club_ids)
    n = len(ids)
    assert n % 2 == 0, "league size must be even"
    half = n // 2
    first_leg: list[list[tuple[int, int]]] = []
    rotation = ids[1:]
    for r in range(n - 1):
        pairs = []
        line = [ids[0]] + rotation
        for i in range(half):
            a, b = line[i], line[n - 1 - i]
            # Alternate the fixed club's venue so home/away balance out.
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        first_leg.append(pairs)
        rotation = rotation[-1:] + rotation[:-1]
    second_leg = [[(b, a) for a, b in rnd] for rnd in first_leg]
    return first_leg + second_leg


class League:
    def __init__(self, name: str, tier: int, club_ids: list[int]):
        self.name = name
        self.tier = tier
        self.club_ids = list(club_ids)
        self.rounds: list[list[tuple[int, int]]] = []
        # results[round_index] -> list of (home_id, away_id, home_goals, away_goals)
        self.results: list[list[tuple[int, int, int, int]]] = []

    def schedule(self, rng: random.Random) -> None:
        ids = list(self.club_ids)
        rng.shuffle(ids)
        self.rounds = round_robin_rounds(ids)
        self.results = [[] for _ in self.rounds]

    @property
    def num_rounds(self) -> int:
        return len(self.rounds)

    def play_round(self, rng: random.Random, round_idx: int,
                   clubs: dict[int, Club]) -> list[MatchReport]:
        reports = []
        for home_id, away_id in self.rounds[round_idx]:
            rep = simulate_match(rng, clubs[home_id], clubs[away_id], competition=self.name)
            self.results[round_idx].append((home_id, away_id, rep.home_goals, rep.away_goals))
            reports.append(rep)
        return reports

    def table(self) -> list[dict]:
        """Standings sorted by points, goal difference, goals for, name order."""
        rows = {cid: {"club_id": cid, "P": 0, "W": 0, "D": 0, "L": 0,
                      "GF": 0, "GA": 0, "GD": 0, "Pts": 0}
                for cid in self.club_ids}
        for rnd in self.results:
            for h, a, hg, ag in rnd:
                for cid, gf, ga in ((h, hg, ag), (a, ag, hg)):
                    row = rows[cid]
                    row["P"] += 1
                    row["GF"] += gf
                    row["GA"] += ga
                    if gf > ga:
                        row["W"] += 1
                        row["Pts"] += 3
                    elif gf == ga:
                        row["D"] += 1
                        row["Pts"] += 1
                    else:
                        row["L"] += 1
        for row in rows.values():
            row["GD"] = row["GF"] - row["GA"]
        return sorted(rows.values(),
                      key=lambda r: (-r["Pts"], -r["GD"], -r["GF"], r["club_id"]))

    def position_of(self, club_id: int) -> int:
        for i, row in enumerate(self.table(), start=1):
            if row["club_id"] == club_id:
                return i
        return 0

    def fixtures_for(self, club_id: int) -> list[tuple[int, int, int]]:
        """All (round_idx, home_id, away_id) involving the club."""
        out = []
        for r, rnd in enumerate(self.rounds):
            for h, a in rnd:
                if club_id in (h, a):
                    out.append((r, h, a))
        return out

    def to_dict(self) -> dict:
        return {"name": self.name, "tier": self.tier, "club_ids": self.club_ids,
                "rounds": [[list(p) for p in rnd] for rnd in self.rounds],
                "results": [[list(m) for m in rnd] for rnd in self.results]}

    @classmethod
    def from_dict(cls, d: dict) -> "League":
        lg = cls(d["name"], d["tier"], d["club_ids"])
        lg.rounds = [[tuple(p) for p in rnd] for rnd in d["rounds"]]
        lg.results = [[tuple(m) for m in rnd] for rnd in d["results"]]
        return lg


class Cup:
    """Straight knockout for all 28 clubs.

    Round 1 has 12 ties; the four best-reputation clubs receive byes into the
    last 16. Ties level after 90 minutes go to extra time and penalties.
    """

    ROUND_NAMES = ["First Round", "Last 16", "Quarter-final", "Semi-final", "Final"]

    def __init__(self, name: str):
        self.name = name
        self.alive: list[int] = []          # club ids still in the cup
        self.byes: list[int] = []
        self.current_round = 0
        self.pairings: list[tuple[int, int]] = []
        self.round_results: list[list[str]] = []   # score lines per round, for history
        self.winner_id: int | None = None

    def draw(self, rng: random.Random, clubs: dict[int, Club]) -> None:
        ids = sorted(clubs.keys(), key=lambda c: clubs[c].reputation, reverse=True)
        self.byes = ids[:4]
        entrants = ids[4:]
        rng.shuffle(entrants)
        self.alive = list(ids)
        self.current_round = 0
        self.round_results = []
        self.winner_id = None
        self.pairings = [(entrants[i], entrants[i + 1]) for i in range(0, len(entrants), 2)]

    @property
    def finished(self) -> bool:
        return self.winner_id is not None

    def round_name(self) -> str:
        return self.ROUND_NAMES[min(self.current_round, len(self.ROUND_NAMES) - 1)]

    def play_round(self, rng: random.Random, clubs: dict[int, Club]) -> list[MatchReport]:
        if self.finished:
            return []
        neutral = self.round_name() in ("Semi-final", "Final")
        reports, winners, lines = [], [], []
        for home_id, away_id in self.pairings:
            rep = simulate_match(rng, clubs[home_id], clubs[away_id],
                                 competition=self.name, neutral=neutral, knockout=True)
            reports.append(rep)
            winners.append(rep.winner_id)
            lines.append(rep.score_line)
        self.round_results.append(lines)
        survivors = winners + ([] if self.current_round > 0 else self.byes)
        self.alive = survivors
        self.current_round += 1
        if len(survivors) == 1:
            self.winner_id = survivors[0]
            self.pairings = []
        else:
            rng.shuffle(survivors)
            self.pairings = [(survivors[i], survivors[i + 1])
                             for i in range(0, len(survivors), 2)]
        return reports

    def to_dict(self) -> dict:
        return {"name": self.name, "alive": self.alive, "byes": self.byes,
                "current_round": self.current_round,
                "pairings": [list(p) for p in self.pairings],
                "round_results": self.round_results, "winner_id": self.winner_id}

    @classmethod
    def from_dict(cls, d: dict) -> "Cup":
        cup = cls(d["name"])
        cup.alive = d["alive"]
        cup.byes = d["byes"]
        cup.current_round = d["current_round"]
        cup.pairings = [tuple(p) for p in d["pairings"]]
        cup.round_results = d["round_results"]
        cup.winner_id = d["winner_id"]
        return cup


class Playoff:
    """Championship promotion playoff: 3rd-6th battle for the final spot.

    Semi-finals (3v6, 4v5, single leg at the better-placed club) then a
    neutral-venue final.
    """

    def __init__(self):
        self.semi_pairings: list[tuple[int, int]] = []
        self.finalists: list[int] = []
        self.winner_id: int | None = None
        self.result_lines: list[str] = []

    def seed(self, standings: list[dict]) -> None:
        ids = [row["club_id"] for row in standings[2:6]]
        self.semi_pairings = [(ids[0], ids[3]), (ids[1], ids[2])]
        self.finalists = []
        self.winner_id = None
        self.result_lines = []

    def play_semis(self, rng: random.Random, clubs: dict[int, Club]) -> list[MatchReport]:
        reports = []
        for home_id, away_id in self.semi_pairings:
            rep = simulate_match(rng, clubs[home_id], clubs[away_id],
                                 competition="Promotion Playoff", knockout=True)
            self.finalists.append(rep.winner_id)
            self.result_lines.append(rep.score_line)
            reports.append(rep)
        return reports

    def play_final(self, rng: random.Random, clubs: dict[int, Club]) -> MatchReport:
        a, b = self.finalists
        rep = simulate_match(rng, clubs[a], clubs[b], competition="Promotion Playoff",
                             neutral=True, knockout=True)
        self.winner_id = rep.winner_id
        self.result_lines.append(rep.score_line)
        return rep

    def to_dict(self) -> dict:
        return {"semi_pairings": [list(p) for p in self.semi_pairings],
                "finalists": self.finalists, "winner_id": self.winner_id,
                "result_lines": self.result_lines}

    @classmethod
    def from_dict(cls, d: dict) -> "Playoff":
        po = cls()
        po.semi_pairings = [tuple(p) for p in d["semi_pairings"]]
        po.finalists = d["finalists"]
        po.winner_id = d["winner_id"]
        po.result_lines = d["result_lines"]
        return po
