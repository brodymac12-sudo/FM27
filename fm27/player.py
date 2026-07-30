"""Player model: attributes, ability, value, development, and career stats."""

from __future__ import annotations

import random

from .names import random_identity

POSITIONS = ("GK", "DF", "MF", "FW")
ATTRS = ("pace", "shooting", "passing", "defending", "physical", "goalkeeping")

# How much each attribute contributes to ability in each position.
POS_WEIGHTS = {
    "GK": {"goalkeeping": 0.55, "physical": 0.15, "passing": 0.10, "defending": 0.10, "pace": 0.05, "shooting": 0.05},
    "DF": {"defending": 0.40, "physical": 0.25, "pace": 0.15, "passing": 0.15, "shooting": 0.03, "goalkeeping": 0.02},
    "MF": {"passing": 0.40, "physical": 0.20, "pace": 0.15, "shooting": 0.15, "defending": 0.08, "goalkeeping": 0.02},
    "FW": {"shooting": 0.40, "pace": 0.25, "physical": 0.15, "passing": 0.15, "defending": 0.03, "goalkeeping": 0.02},
}

PEAK_AGE = {"GK": 30, "DF": 28, "MF": 27, "FW": 26}


def _blank_stats() -> dict:
    return {"apps": 0, "goals": 0, "assists": 0, "yellows": 0, "reds": 0,
            "clean_sheets": 0, "rating_sum": 0.0}


class Player:
    """A footballer with visible attributes and a hidden potential ceiling."""

    def __init__(self, pid: int, name: str, nation: str, position: str, age: int,
                 attrs: dict, potential: int):
        self.id = pid
        self.name = name
        self.nation = nation
        self.position = position
        self.age = age
        self.attrs = dict(attrs)
        self.potential = potential
        self.fitness = 100.0
        self.morale = 70.0
        self.injured_for = 0      # matchdays remaining out injured
        self.suspended_for = 0    # matchdays remaining suspended
        self.season = _blank_stats()
        self.career = _blank_stats()
        self.career["seasons"] = 0
        self.trophies: list[str] = []
        self.club_id: int | None = None
        self.loaned_from: int | None = None   # parent club id while on loan

    # ------------------------------------------------------------------ rating

    @property
    def ability(self) -> float:
        """Current ability 1-99, weighted for the player's natural position."""
        return self.rating_at(self.position)

    def rating_at(self, position: str) -> float:
        w = POS_WEIGHTS[position]
        score = sum(self.attrs[a] * w[a] for a in ATTRS)
        if position != self.position:
            score *= 0.72  # out-of-position penalty
        return score

    @property
    def available(self) -> bool:
        return self.injured_for <= 0 and self.suspended_for <= 0

    # ------------------------------------------------------------------- value

    @property
    def value(self) -> float:
        """Transfer value in £M."""
        ca = self.ability
        base = (max(ca, 30) / 100.0) ** 3.2 * 110.0
        peak = PEAK_AGE[self.position]
        if self.age <= peak:
            age_f = 0.75 + 0.25 * min(1.0, (self.age - 15) / (peak - 18))
            # Promising youngsters carry a potential premium.
            upside = max(0.0, self.potential - ca)
            base *= age_f + upside * 0.012
        else:
            age_f = max(0.12, 1.0 - 0.16 * (self.age - peak))
            base *= age_f
        return round(max(0.05, base), 2)

    @property
    def wage(self) -> float:
        """Annual wage in £M."""
        return round(max(0.1, self.value * 0.10 + self.ability * 0.007), 2)

    # ------------------------------------------------------------- development

    def develop(self, rng: random.Random, minutes_share: float, training_quality: float) -> None:
        """Grow or decline one season's worth. Called at end of season (before aging)."""
        peak = PEAK_AGE[self.position]
        gap = max(0.0, self.potential - self.ability)
        if self.age < peak - 3:
            growth = rng.uniform(0.8, 2.4) + gap * 0.22
            growth *= 0.55 + 0.45 * minutes_share            # playing time matters
            growth *= 0.85 + 0.30 * (training_quality / 100)  # club facilities matter
        elif self.age <= peak:
            growth = rng.uniform(0.0, 1.0) + gap * 0.08
        else:
            over = self.age - peak
            growth = -rng.uniform(0.4, 1.4) * over * 0.55
            if self.position == "GK":
                growth *= 0.6
        self._apply_growth(rng, growth)

    def _apply_growth(self, rng: random.Random, growth: float) -> None:
        w = POS_WEIGHTS[self.position]
        for a in ATTRS:
            delta = growth * (0.5 + 1.6 * w[a]) + rng.uniform(-0.4, 0.4)
            if growth < 0 and a == "pace":
                delta *= 1.5  # legs go first
            self.attrs[a] = min(99.0, max(1.0, self.attrs[a] + delta))

    def age_one_year(self) -> None:
        self.age += 1
        self.career["seasons"] += 1
        for k, v in self.season.items():
            self.career[k] = self.career.get(k, 0) + v
        self.season = _blank_stats()

    # ------------------------------------------------------------ presentation

    @property
    def avg_rating(self) -> float:
        return self.season["rating_sum"] / self.season["apps"] if self.season["apps"] else 0.0

    def __repr__(self) -> str:  # pragma: no cover
        return f"<{self.position} {self.name} ({self.age}) CA {self.ability:.0f}>"

    # ------------------------------------------------------------ serialization

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "nation": self.nation,
            "position": self.position, "age": self.age, "attrs": self.attrs,
            "potential": self.potential, "fitness": self.fitness,
            "morale": self.morale, "injured_for": self.injured_for,
            "suspended_for": self.suspended_for, "season": self.season,
            "career": self.career, "trophies": self.trophies,
            "club_id": self.club_id, "loaned_from": self.loaned_from,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Player":
        p = cls(d["id"], d["name"], d["nation"], d["position"], d["age"],
                d["attrs"], d["potential"])
        p.fitness = d["fitness"]
        p.morale = d["morale"]
        p.injured_for = d["injured_for"]
        p.suspended_for = d["suspended_for"]
        p.season = d["season"]
        p.career = d["career"]
        p.trophies = d["trophies"]
        p.club_id = d["club_id"]
        p.loaned_from = d.get("loaned_from")
        return p


# ---------------------------------------------------------------- generation

def generate_player(rng: random.Random, pid: int, position: str, age: int,
                    target_ability: float) -> Player:
    """Create a player whose weighted ability lands near ``target_ability``."""
    name, nation = random_identity(rng)
    target = max(25.0, min(96.0, target_ability + rng.uniform(-4, 4)))
    w = POS_WEIGHTS[position]
    attrs = {}
    for a in ATTRS:
        # Attributes central to the position sit above target, fringe ones below.
        skew = (w[a] - 1 / len(ATTRS)) * 55
        attrs[a] = min(99.0, max(1.0, target + skew + rng.uniform(-7, 7)))
    if position != "GK":
        attrs["goalkeeping"] = rng.uniform(5, 15)
    p = Player(pid, name, nation, position, age, attrs, potential=0)
    ca = p.ability
    if age < 24:
        p.potential = int(min(97, ca + rng.uniform(2, (25 - age) * 3.2)))
    else:
        p.potential = int(min(97, ca + rng.uniform(0, 3)))
    return p
