"""Entry point.

Interactive career mode:
    python -m fm27

Headless multi-year simulation (no prompts, prints a season-by-season report):
    python -m fm27 --sim 25 --seed 7
    python -m fm27 --sim 10 --load saves/world.json --save-to world
"""

from __future__ import annotations

import argparse

from .cli import main_menu, run_spectator
from .save import load_world, save_world
from .world import GameWorld


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fm27",
                                description="FM27 — Football Manager 27")
    p.add_argument("--sim", type=int, metavar="YEARS",
                   help="run a headless multi-year simulation and exit")
    p.add_argument("--seed", type=int, help="world seed for reproducible sims")
    p.add_argument("--load", metavar="SAVE",
                   help="load an existing save instead of creating a new world")
    p.add_argument("--save-to", metavar="NAME",
                   help="save the world after a headless sim")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sim:
        world = load_world(args.load) if args.load else GameWorld.new(args.seed)
        run_spectator(world, args.sim)
        if args.save_to:
            path = save_world(world, args.save_to)
            print(f"\nWorld saved to {path}")
        return 0
    main_menu()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
