"""Save/load game worlds as JSON files under ./saves/."""

from __future__ import annotations

import json
import os

from .world import GameWorld

SAVE_DIR = "saves"


def _path_for(name: str) -> str:
    if name.endswith(".json"):
        return name if os.sep in name or name.startswith("saves") else os.path.join(SAVE_DIR, name)
    return os.path.join(SAVE_DIR, f"{name}.json")


def save_world(world: GameWorld, name: str) -> str:
    os.makedirs(SAVE_DIR, exist_ok=True)
    path = _path_for(name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(world.to_dict(), fh)
    return path


def load_world(name: str) -> GameWorld:
    path = _path_for(name)
    with open(path, encoding="utf-8") as fh:
        return GameWorld.from_dict(json.load(fh))


def list_saves() -> list[str]:
    if not os.path.isdir(SAVE_DIR):
        return []
    return sorted(f for f in os.listdir(SAVE_DIR) if f.endswith(".json"))
