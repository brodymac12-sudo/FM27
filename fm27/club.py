"""Club model: squad, tactics, lineup selection, and finances."""

from __future__ import annotations

import random

from .player import Player, generate_player

# formation -> (defenders, midfielders, forwards)
FORMATIONS = {
    "4-4-2": (4, 4, 2),
    "4-3-3": (4, 3, 3),
    "4-2-3-1": (4, 5, 1),
    "3-5-2": (3, 5, 2),
    "5-3-2": (5, 3, 2),
    "4-5-1": (4, 5, 1),
}
MENTALITIES = ("defensive", "balanced", "attacking")

# Squad template used when seeding a new game world.
SQUAD_TEMPLATE = [("GK", 3), ("DF", 8), ("MF", 7), ("FW", 5)]


class Tactics:
    def __init__(self, formation: str = "4-4-2", mentality: str = "balanced"):
        self.formation = formation
        self.mentality = mentality

    def shape(self) -> tuple[int, int, int]:
        return FORMATIONS[self.formation]

    def to_dict(self) -> dict:
        return {"formation": self.formation, "mentality": self.mentality}

    @classmethod
    def from_dict(cls, d: dict) -> "Tactics":
        return cls(d["formation"], d["mentality"])


class Club:
    def __init__(self, cid: int, name: str, short: str, reputation: int,
                 capacity: int, division: int):
        self.id = cid
        self.name = name
        self.short = short
        self.reputation = reputation
        self.capacity = capacity
        self.division = division            # 0 = Premier Division, 1 = Championship
        self.squad: list[Player] = []
        self.tactics = Tactics()
        self.balance = round(reputation * 0.9, 2)       # £M
        self.transfer_budget = round(reputation * 0.45, 2)
        self.wage_budget = round(reputation * 1.1, 2)
        self.trophies: dict[str, list[str]] = {}        # competition -> seasons won
        self.season_finishes: list[tuple[str, int, int]] = []  # (season, division, position)

    # -------------------------------------------------------------- squad ops

    def add_player(self, player: Player) -> None:
        player.club_id = self.id
        self.squad.append(player)

    def remove_player(self, player: Player) -> None:
        self.squad.remove(player)
        player.club_id = None

    def players_at(self, position: str) -> list[Player]:
        return [p for p in self.squad if p.position == position]

    @property
    def wage_bill(self) -> float:
        return round(sum(p.wage for p in self.squad), 2)

    @property
    def training_quality(self) -> float:
        return self.reputation

    def pick_lineup(self, rng: random.Random | None = None) -> list[Player]:
        """Best available XI for the current formation.

        Players compete for their *natural* position's slots first — a star
        forward is never repurposed as a defender just because the back line
        is weak. Out-of-position filling only happens when a position runs
        out of fit bodies. Fitness nudges selection but never benches a
        clearly better player.
        """
        df, mf, fw = self.tactics.shape()
        need = {"GK": 1, "DF": df, "MF": mf, "FW": fw}
        available = sorted(
            (p for p in self.squad if p.available),
            key=lambda p: p.ability * (0.9 + 0.1 * p.fitness / 100),
            reverse=True)
        chosen: list[Player] = []
        counts = {pos: 0 for pos in need}
        leftovers: list[Player] = []
        for p in available:
            if counts[p.position] < need[p.position]:
                chosen.append(p)
                counts[p.position] += 1
            else:
                leftovers.append(p)
        for pos, count in need.items():
            while counts[pos] < count and leftovers:
                best = max(leftovers,
                           key=lambda q: q.rating_at(pos) * (0.9 + 0.1 * q.fitness / 100))
                leftovers.remove(best)
                chosen.append(best)
                counts[pos] += 1
        # Emergency: fewer than 11 fit players — field whoever exists.
        if len(chosen) < 11:
            rest = [p for p in self.squad if p not in chosen]
            rest.sort(key=lambda p: p.ability, reverse=True)
            chosen.extend(rest[: 11 - len(chosen)])
        return chosen[:11]

    def lineup_positions(self, lineup: list[Player]) -> list[tuple[str, Player]]:
        """Assign each lineup player to a slot of the formation."""
        df, mf, fw = self.tactics.shape()
        need = [("GK", 1), ("DF", df), ("MF", mf), ("FW", fw)]
        slots: list[tuple[str, Player]] = []
        remaining = list(lineup)
        for pos, count in need:
            natural = [p for p in remaining if p.position == pos]
            natural.sort(key=lambda p: p.rating_at(pos), reverse=True)
            take = natural[:count]
            for p in take:
                remaining.remove(p)
            slots.extend((pos, p) for p in take)
            for _ in range(count - len(take)):
                if remaining:
                    filler = max(remaining, key=lambda p: p.rating_at(pos))
                    remaining.remove(filler)
                    slots.append((pos, filler))
        return slots

    @property
    def squad_strength(self) -> float:
        """Mean ability of the best XI, ignoring fitness. Used for AI decisions."""
        xi = sorted(self.squad, key=lambda p: p.ability, reverse=True)[:11]
        return sum(p.ability for p in xi) / max(1, len(xi))

    def add_trophy(self, competition: str, season: str) -> None:
        self.trophies.setdefault(competition, []).append(season)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Club {self.name}>"

    # ------------------------------------------------------------ serialization

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "short": self.short,
            "reputation": self.reputation, "capacity": self.capacity,
            "division": self.division, "tactics": self.tactics.to_dict(),
            "balance": self.balance, "transfer_budget": self.transfer_budget,
            "wage_budget": self.wage_budget, "trophies": self.trophies,
            "season_finishes": [list(t) for t in self.season_finishes],
            "squad": [p.to_dict() for p in self.squad],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Club":
        c = cls(d["id"], d["name"], d["short"], d["reputation"], d["capacity"],
                d["division"])
        c.tactics = Tactics.from_dict(d["tactics"])
        c.balance = d["balance"]
        c.transfer_budget = d["transfer_budget"]
        c.wage_budget = d["wage_budget"]
        c.trophies = d["trophies"]
        c.season_finishes = [tuple(t) for t in d["season_finishes"]]
        for pd in d["squad"]:
            c.add_player(Player.from_dict(pd))
        return c


# ----------------------------------------------------------------- seeding

def build_initial_squad(rng: random.Random, club: Club, next_pid) -> None:
    """Fill a fresh club with a squad sized/skilled according to reputation."""
    base = club.reputation * 0.92
    for pos, count in SQUAD_TEMPLATE:
        for i in range(count):
            # First-choice players are near base quality; depth falls away.
            drop = 0.0 if i < max(1, count // 2) else rng.uniform(4, 12)
            age = rng.choices(
                population=[rng.randint(17, 20), rng.randint(21, 25),
                            rng.randint(26, 29), rng.randint(30, 34)],
                weights=[20, 35, 30, 15])[0]
            youth_malus = max(0, (22 - age)) * 1.8
            target = base - drop - youth_malus + rng.uniform(-3, 3)
            club.add_player(generate_player(rng, next_pid(), pos, age, target))
