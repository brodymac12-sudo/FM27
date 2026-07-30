"""Player model: attributes, ability, value, development, and career stats.

Players carry 17 attributes across four groups, FM-style:

- Technical: finishing, dribbling, passing, crossing, tackling, heading
- Mental:    vision, positioning, composure, work_rate
- Physical:  pace, stamina, strength
- Keeping:   reflexes, handling, aerial, kicking

Overall ability is a position-weighted blend. Physical attributes decline
fastest with age (pace first), mental ones barely at all.
"""

from __future__ import annotations

import random

from .names import random_identity

POSITIONS = ("GK", "DF", "MF", "FW")

TECHNICAL = ("finishing", "dribbling", "passing", "crossing", "tackling", "heading")
MENTAL = ("vision", "positioning", "composure", "work_rate")
PHYSICAL = ("pace", "stamina", "strength")
KEEPING = ("reflexes", "handling", "aerial", "kicking")
ATTRS = TECHNICAL + MENTAL + PHYSICAL + KEEPING

ATTR_GROUPS = {"Technical": TECHNICAL, "Mental": MENTAL,
               "Physical": PHYSICAL, "Keeping": KEEPING}

# How much each attribute contributes to overall ability in each position.
# Each mapping sums to 1.0; unlisted attributes don't affect the rating.
POS_WEIGHTS = {
    "GK": {"reflexes": 0.26, "handling": 0.20, "aerial": 0.13, "kicking": 0.07,
           "positioning": 0.10, "composure": 0.07, "strength": 0.05,
           "pace": 0.03, "passing": 0.05, "vision": 0.04},
    "DF": {"tackling": 0.22, "positioning": 0.18, "heading": 0.13,
           "strength": 0.13, "pace": 0.12, "passing": 0.08, "composure": 0.06,
           "work_rate": 0.06, "vision": 0.02},
    "MF": {"passing": 0.20, "vision": 0.16, "work_rate": 0.12, "stamina": 0.10,
           "dribbling": 0.10, "composure": 0.08, "positioning": 0.08,
           "finishing": 0.06, "tackling": 0.06, "pace": 0.04},
    "FW": {"finishing": 0.24, "pace": 0.16, "dribbling": 0.14, "composure": 0.12,
           "heading": 0.08, "strength": 0.08, "vision": 0.06, "passing": 0.06,
           "work_rate": 0.06},
}

PEAK_AGE = {"GK": 30, "DF": 28, "MF": 27, "FW": 26}


def _blank_stats() -> dict:
    return {"apps": 0, "goals": 0, "assists": 0, "yellows": 0, "reds": 0,
            "clean_sheets": 0, "rating_sum": 0.0}


def migrate_attrs(old: dict) -> dict:
    """Convert the legacy six-attribute format to the detailed system."""
    sho, pas, dfn = old["shooting"], old["passing"], old["defending"]
    phy, pac, gkp = old["physical"], old["pace"], old["goalkeeping"]
    return {
        "finishing": sho, "dribbling": (pac + sho) / 2, "passing": pas,
        "crossing": pas * 0.9, "tackling": dfn, "heading": (phy + dfn) / 2,
        "vision": pas, "positioning": dfn, "composure": (sho + pas) / 2,
        "work_rate": phy, "pace": pac, "stamina": phy, "strength": phy,
        "reflexes": gkp, "handling": gkp, "aerial": gkp * 0.9,
        "kicking": (gkp + pas) / 2,
    }


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
        score = sum(self.attrs[a] * wt for a, wt in w.items())
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
            delta = growth * (0.5 + 1.6 * w.get(a, 0.02)) + rng.uniform(-0.4, 0.4)
            if growth < 0:
                # Ageing profile: legs go first, the brain keeps its edge.
                if a == "pace":
                    delta *= 1.9
                elif a in PHYSICAL:
                    delta *= 1.6
                elif a in MENTAL:
                    delta *= 0.35
                elif a in KEEPING:
                    delta *= 0.6
                else:
                    delta *= 0.85
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
        attrs = d["attrs"]
        if "shooting" in attrs:          # legacy six-attribute save
            attrs = migrate_attrs(attrs)
        p = cls(d["id"], d["name"], d["nation"], d["position"], d["age"],
                attrs, d["potential"])
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
    weights = POS_WEIGHTS[position]
    avg_w = 1.0 / len(weights)
    attrs = {}
    for a in ATTRS:
        w = weights.get(a)
        if position != "GK" and a in KEEPING:
            attrs[a] = rng.uniform(3, 12)
        elif w is None:
            # Off-profile skills sit well below the player's level.
            attrs[a] = min(99.0, max(1.0, target - rng.uniform(10, 28)))
        else:
            skew = (w - avg_w) * 110
            attrs[a] = min(99.0, max(1.0, target + skew + rng.uniform(-7, 7)))
    p = Player(pid, name, nation, position, age, attrs, potential=0)
    ca = p.ability
    if age < 24:
        p.potential = int(min(97, ca + rng.uniform(2, (25 - age) * 3.2)))
    else:
        p.potential = int(min(97, ca + rng.uniform(0, 3)))
    return p
