"""In-game editor: modify any player in the world, FM-editor style.

Pure functions here; the interactive wrapper lives in the CLI so these can
be tested (and reused) directly.
"""

from __future__ import annotations

from .club import Club
from .player import ATTRS, POSITIONS, Player
from .world import GameWorld


def find_players(world: GameWorld, query: str, limit: int = 20) -> list[tuple[Player, Club]]:
    """Case-insensitive substring search over every player in the world."""
    q = query.lower().strip()
    hits = [(p, c) for c in world.clubs.values() for p in c.squad
            if q in p.name.lower()]
    hits.sort(key=lambda t: -t[0].ability)
    return hits[:limit]


def set_name(player: Player, name: str) -> str:
    name = name.strip()
    if not name:
        return "Name unchanged — cannot be empty."
    player.name = name
    return f"Renamed to {player.name}."


def set_age(player: Player, age: int) -> str:
    if not 15 <= age <= 45:
        return "Age must be 15-45."
    player.age = age
    return f"Age set to {age}."


def set_position(player: Player, position: str) -> str:
    position = position.upper()
    if position not in POSITIONS:
        return f"Position must be one of {', '.join(POSITIONS)}."
    player.position = position
    return f"Position set to {position}."


def set_attribute(player: Player, attr: str, value: float) -> str:
    attr = attr.lower()
    if attr not in ATTRS:
        return f"Attribute must be one of {', '.join(ATTRS)}."
    player.attrs[attr] = float(min(99.0, max(1.0, value)))
    return f"{attr} set to {player.attrs[attr]:.0f} (ability now {player.ability:.0f})."


def set_potential(player: Player, value: int) -> str:
    value = int(min(99, max(1, value)))
    player.potential = max(value, int(player.ability))
    note = "" if player.potential == value else " (raised to current ability)"
    return f"Potential set to {player.potential}{note}."


def heal(player: Player) -> str:
    player.injured_for = 0
    player.suspended_for = 0
    player.fitness = 100.0
    return "Injury cleared, suspension lifted, fitness restored."


def set_condition(player: Player, fitness: float | None = None,
                  morale: float | None = None) -> str:
    if fitness is not None:
        player.fitness = float(min(100.0, max(1.0, fitness)))
    if morale is not None:
        player.morale = float(min(100.0, max(1.0, morale)))
    return f"Fitness {player.fitness:.0f}, morale {player.morale:.0f}."


def move_player(world: GameWorld, player: Player, dest_club_id: int) -> str:
    """Editor-style free transfer: instantly move a player to any club."""
    if dest_club_id not in world.clubs:
        return "No such club."
    current = world.clubs.get(player.club_id)
    dest = world.clubs[dest_club_id]
    if current is not None and current.id == dest.id:
        return f"{player.name} is already at {dest.name}."
    if current is not None:
        if len(current.squad) <= 12:
            return f"{current.name} would be left with too few players."
        current.remove_player(player)
    player.loaned_from = None    # editor moves break any loan
    dest.add_player(player)
    return f"{player.name} moved to {dest.name}."
