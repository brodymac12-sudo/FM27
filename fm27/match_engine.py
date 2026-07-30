"""Probabilistic match engine.

Team strengths are computed from the selected XI (attributes, fitness,
morale, tactics), expected goals are derived from the attack/defence
matchup, and goals are sampled from a Poisson process. The engine also
produces scorers, assists, cards, injuries, player ratings, and — for
knockout ties — extra time and penalty shootouts. Player season/career
stats and physical condition are updated as a side effect.
"""

from __future__ import annotations

import math
import random

from .club import Club
from .player import Player

HOME_ADVANTAGE = 1.12
BASE_XG = 1.30

MENTALITY_MODS = {          # (attack multiplier, defence multiplier)
    "defensive": (0.88, 1.08),
    "balanced": (1.0, 1.0),
    "attacking": (1.10, 0.92),
}


class MatchReport:
    def __init__(self, home: Club, away: Club, competition: str):
        self.home = home
        self.away = away
        self.competition = competition
        self.home_goals = 0
        self.away_goals = 0
        self.events: list[dict] = []      # {minute, type, club_id, player, detail}
        self.ratings: dict[int, float] = {}
        self.went_to_extra_time = False
        self.penalties: tuple[int, int] | None = None
        self.winner_id: int | None = None  # only set for knockout ties

    @property
    def score_line(self) -> str:
        s = f"{self.home.short} {self.home_goals}-{self.away_goals} {self.away.short}"
        if self.penalties:
            s += f" ({self.penalties[0]}-{self.penalties[1]} pens)"
        elif self.went_to_extra_time:
            s += " (aet)"
        return s

    def result_for(self, club_id: int) -> str:
        """'W', 'D' or 'L' from the given club's perspective (90/120 mins)."""
        mine = self.home_goals if club_id == self.home.id else self.away_goals
        theirs = self.away_goals if club_id == self.home.id else self.home_goals
        if mine > theirs:
            return "W"
        if mine < theirs:
            return "L"
        return "D"


def _poisson(rng: random.Random, lam: float) -> int:
    """Knuth's algorithm; adequate for lambdas in the 0.1-5 range used here."""
    threshold = math.exp(-lam)
    k, p = 0, 1.0
    while True:
        p *= rng.random()
        if p <= threshold:
            return k
        k += 1


def _unit_strength(player: Player, weights: dict[str, float]) -> float:
    raw = sum(player.attrs[a] * w for a, w in weights.items())
    condition = 0.72 + 0.28 * (player.fitness / 100.0)
    form = 0.95 + 0.10 * (player.morale / 100.0)
    return raw * condition * form


def _team_strengths(club: Club, slots: list[tuple[str, Player]]) -> tuple[float, float, float]:
    """Return (attack, midfield, defence) strengths for the assigned XI."""
    gk_s, df_s, mf_s, fw_s = 30.0, [], [], []
    for pos, p in slots:
        penalty = 1.0 if p.position == pos else 0.78
        if pos == "GK":
            gk_s = _unit_strength(p, {"reflexes": 0.45, "handling": 0.30,
                                      "aerial": 0.15, "positioning": 0.10}) * penalty
        elif pos == "DF":
            df_s.append(_unit_strength(p, {"tackling": 0.30, "positioning": 0.25,
                                           "strength": 0.15, "pace": 0.15,
                                           "heading": 0.15}) * penalty)
        elif pos == "MF":
            mf_s.append(_unit_strength(p, {"passing": 0.28, "vision": 0.20,
                                           "work_rate": 0.14, "dribbling": 0.14,
                                           "stamina": 0.12, "composure": 0.12}) * penalty)
        else:
            fw_s.append(_unit_strength(p, {"finishing": 0.32, "pace": 0.20,
                                           "dribbling": 0.16, "composure": 0.14,
                                           "heading": 0.10, "strength": 0.08}) * penalty)
    df_avg = sum(df_s) / len(df_s) if df_s else 30.0
    mf_avg = sum(mf_s) / len(mf_s) if mf_s else 30.0
    fw_avg = sum(fw_s) / len(fw_s) if fw_s else mf_avg * 0.8
    att_mod, def_mod = MENTALITY_MODS[club.tactics.mentality]
    attack = (fw_avg * 0.65 + mf_avg * 0.35) * att_mod
    defence = (df_avg * 0.62 + gk_s * 0.38) * def_mod
    return attack, mf_avg, defence


def _expected_goals(attack: float, opp_defence: float, mid: float, opp_mid: float,
                    home: bool, neutral: bool) -> float:
    ratio = attack / max(20.0, opp_defence)
    mid_share = 0.85 + 0.30 * (mid / max(1.0, mid + opp_mid))
    xg = BASE_XG * (ratio ** 1.6) * mid_share
    if home and not neutral:
        xg *= HOME_ADVANTAGE
    return max(0.12, min(4.8, xg))


def _pick_scorer(rng: random.Random, slots: list[tuple[str, Player]]) -> tuple[Player, Player | None]:
    """Weighted scorer + optional assister from the outfield players.

    The steep exponent concentrates goals on elite finishers — a 95-finishing
    striker takes a much bigger share than an 75-rated teammate.
    """
    outfield = [(pos, p) for pos, p in slots if pos != "GK"]
    pos_bias = {"DF": 0.35, "MF": 1.0, "FW": 2.7}
    weights = [max(1.0, p.attrs["finishing"] * 0.6 + p.attrs["composure"] * 0.25
                   + p.attrs["heading"] * 0.15) ** 2.6 * pos_bias[pos]
               for pos, p in outfield]
    scorer = rng.choices([p for _, p in outfield], weights=weights)[0]
    assister = None
    if rng.random() < 0.72:
        others = [(pos, p) for pos, p in outfield if p is not scorer]
        a_weights = [max(1.0, p.attrs["passing"] * 0.5 + p.attrs["vision"] * 0.5) ** 2
                     * {"DF": 0.5, "MF": 2.2, "FW": 1.2}[pos]
                     for pos, p in others]
        assister = rng.choices([p for _, p in others], weights=a_weights)[0]
    return scorer, assister


def simulate_match(rng: random.Random, home: Club, away: Club, competition: str = "league",
                   neutral: bool = False, knockout: bool = False) -> MatchReport:
    report = MatchReport(home, away, competition)
    h_xi = home.pick_lineup(rng)
    a_xi = away.pick_lineup(rng)
    h_slots = home.lineup_positions(h_xi)
    a_slots = away.lineup_positions(a_xi)

    h_att, h_mid, h_def = _team_strengths(home, h_slots)
    a_att, a_mid, a_def = _team_strengths(away, a_slots)

    h_xg = _expected_goals(h_att, a_def, h_mid, a_mid, home=True, neutral=neutral)
    a_xg = _expected_goals(a_att, h_def, a_mid, h_mid, home=False, neutral=neutral)

    report.home_goals = _poisson(rng, h_xg)
    report.away_goals = _poisson(rng, a_xg)

    _add_goal_events(rng, report, h_slots, home, report.home_goals, 90)
    _add_goal_events(rng, report, a_slots, away, report.away_goals, 90)

    if knockout and report.home_goals == report.away_goals:
        _resolve_knockout_draw(rng, report, h_slots, a_slots, h_xg, a_xg)
    elif knockout:
        report.winner_id = home.id if report.home_goals > report.away_goals else away.id

    _add_discipline_and_injuries(rng, report, h_slots + a_slots)
    _compute_ratings(rng, report, home, h_slots, away, a_slots)
    _apply_player_updates(report, home, h_slots, away, a_slots)
    report.events.sort(key=lambda e: e["minute"])
    return report


def _add_goal_events(rng: random.Random, report: MatchReport,
                     slots: list[tuple[str, Player]], club: Club,
                     n_goals: int, max_minute: int, from_minute: int = 1) -> None:
    for _ in range(n_goals):
        scorer, assister = _pick_scorer(rng, slots)
        report.events.append({
            "minute": rng.randint(from_minute, max_minute),
            "type": "goal", "club_id": club.id, "player": scorer.name,
            "player_id": scorer.id,
            "detail": f"assist: {assister.name}" if assister else "",
        })
        scorer.season["goals"] += 1
        if assister:
            assister.season["assists"] += 1


def _resolve_knockout_draw(rng: random.Random, report: MatchReport,
                           h_slots, a_slots, h_xg: float, a_xg: float) -> None:
    report.went_to_extra_time = True
    et_h = _poisson(rng, h_xg / 3.2)
    et_a = _poisson(rng, a_xg / 3.2)
    report.home_goals += et_h
    report.away_goals += et_a
    _add_goal_events(rng, report, h_slots, report.home, et_h, 120, from_minute=91)
    _add_goal_events(rng, report, a_slots, report.away, et_a, 120, from_minute=91)
    if report.home_goals != report.away_goals:
        report.winner_id = (report.home.id if report.home_goals > report.away_goals
                           else report.away.id)
        return
    # Penalty shootout: keeper quality tilts the coin.
    h_gk = next(p for pos, p in h_slots if pos == "GK")
    a_gk = next(p for pos, p in a_slots if pos == "GK")
    edge = 0.5 + (h_gk.attrs["reflexes"] - a_gk.attrs["reflexes"]) / 400.0
    home_won = rng.random() < edge
    win_pens = rng.choice([(5, 4), (4, 3), (4, 2), (5, 3), (3, 1), (6, 5)])
    report.penalties = win_pens if home_won else (win_pens[1], win_pens[0])
    report.winner_id = report.home.id if home_won else report.away.id


def _add_discipline_and_injuries(rng: random.Random, report: MatchReport,
                                 all_slots: list[tuple[str, Player]]) -> None:
    for pos, p in all_slots:
        club_id = p.club_id
        aggression = p.attrs["strength"] / 100.0
        if rng.random() < 0.035 + 0.05 * aggression:
            p.season["yellows"] += 1
            report.events.append({"minute": rng.randint(10, 90), "type": "yellow",
                                  "club_id": club_id, "player": p.name,
                                  "player_id": p.id, "detail": ""})
            if p.season["yellows"] % 5 == 0:      # totting up
                p.suspended_for = max(p.suspended_for, 1)
        if rng.random() < 0.004:
            p.season["reds"] += 1
            p.suspended_for = max(p.suspended_for, rng.randint(1, 3))
            report.events.append({"minute": rng.randint(20, 90), "type": "red",
                                  "club_id": club_id, "player": p.name,
                                  "player_id": p.id, "detail": ""})
        injury_p = 0.015 if p.fitness > 60 else 0.045
        if rng.random() < injury_p:
            p.injured_for = rng.randint(1, 8)
            report.events.append({"minute": rng.randint(1, 90), "type": "injury",
                                  "club_id": club_id, "player": p.name,
                                  "player_id": p.id,
                                  "detail": f"out ~{p.injured_for} matchdays"})


def _compute_ratings(rng: random.Random, report: MatchReport,
                     home: Club, h_slots, away: Club, a_slots) -> None:
    goal_counts: dict[int, int] = {}
    assist_names: dict[str, int] = {}
    for e in report.events:
        if e["type"] == "goal":
            goal_counts[e["player_id"]] = goal_counts.get(e["player_id"], 0) + 1
            if e["detail"].startswith("assist: "):
                name = e["detail"][8:]
                assist_names[name] = assist_names.get(name, 0) + 1
    for club, slots, conceded in ((home, h_slots, report.away_goals),
                                  (away, a_slots, report.home_goals)):
        res = report.result_for(club.id)
        team_adj = {"W": 0.45, "D": 0.0, "L": -0.45}[res]
        for pos, p in slots:
            r = 6.4 + rng.uniform(-0.5, 0.5) + team_adj
            r += goal_counts.get(p.id, 0) * 1.0
            r += assist_names.get(p.name, 0) * 0.55
            if conceded == 0 and pos in ("GK", "DF"):
                r += 0.8 if pos == "GK" else 0.45
                if pos == "GK":
                    p.season["clean_sheets"] += 1
            report.ratings[p.id] = round(max(3.0, min(10.0, r)), 1)


def _apply_player_updates(report: MatchReport, home: Club, h_slots,
                          away: Club, a_slots) -> None:
    for club, slots in ((home, h_slots), (away, a_slots)):
        res = report.result_for(club.id)
        morale_delta = {"W": 4.0, "D": 0.5, "L": -4.0}[res]
        minutes_factor = 1.33 if report.went_to_extra_time else 1.0
        for _, p in slots:
            p.season["apps"] += 1
            p.season["rating_sum"] += report.ratings.get(p.id, 6.0)
            # High-stamina players shrug off a match; low-stamina ones drain.
            cost = 16.0 - p.attrs["stamina"] * 0.06
            p.fitness = max(20.0, p.fitness - cost * minutes_factor)
            p.morale = max(5.0, min(100.0, p.morale + morale_delta))
