"""All-time record queries across active and retired players."""

from __future__ import annotations

from . import data
from .world import GameWorld


def all_time_scorers(world: GameWorld, top: int = 10) -> list[dict]:
    """Career goals leaderboard including current-season goals for actives."""
    entries = []
    for club in world.clubs.values():
        for p in club.squad:
            goals = p.career["goals"] + p.season["goals"]
            apps = p.career["apps"] + p.season["apps"]
            if goals:
                entries.append({"name": p.name, "club": club.name, "goals": goals,
                                "apps": apps, "status": "active"})
    for r in world.retired:
        if r["career"]["goals"]:
            entries.append({"name": r["name"], "club": r["last_club"],
                            "goals": r["career"]["goals"],
                            "apps": r["career"]["apps"], "status": "retired"})
    entries.sort(key=lambda e: (-e["goals"], e["apps"]))
    return entries[:top]


def most_decorated_players(world: GameWorld, top: int = 10) -> list[dict]:
    entries = []
    for club in world.clubs.values():
        for p in club.squad:
            if p.trophies:
                entries.append({"name": p.name, "club": club.name,
                                "trophies": len(p.trophies), "status": "active"})
    for r in world.retired:
        if r["trophies"]:
            entries.append({"name": r["name"], "club": r["last_club"],
                            "trophies": len(r["trophies"]), "status": "retired"})
    entries.sort(key=lambda e: -e["trophies"])
    return entries[:top]


def title_counts(world: GameWorld) -> list[tuple[str, int, int]]:
    """(club name, league titles, cup wins) sorted by total honours."""
    rows = []
    for club in world.clubs.values():
        league_titles = len(club.trophies.get(data.DIVISION_NAMES[0], []))
        cups = len(club.trophies.get(data.CUP_NAME, []))
        if league_titles or cups:
            rows.append((club.name, league_titles, cups))
    rows.sort(key=lambda r: (-(r[1] + r[2]), -r[1]))
    return rows


def hall_of_fame(world: GameWorld, top: int = 15) -> list[dict]:
    """Retired greats ranked by a blend of longevity, goals, and honours."""
    ranked = []
    for r in world.retired:
        career = r["career"]
        score = career["apps"] * 0.5 + career["goals"] * 2 + len(r["trophies"]) * 25
        if score >= 120:
            ranked.append({**r, "score": round(score)})
    ranked.sort(key=lambda e: -e["score"])
    return ranked[:top]
