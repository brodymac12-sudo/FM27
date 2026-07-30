"""Test suite for the FM27 simulation engine."""

import json
import random
import unittest

from fm27 import data
from fm27.club import FORMATIONS
from fm27.competition import round_robin_rounds
from fm27.match_engine import simulate_match
from fm27.player import generate_player
from fm27.world import GameWorld


class TestScheduling(unittest.TestCase):
    def test_double_round_robin(self):
        ids = list(range(1, 15))
        rounds = round_robin_rounds(ids)
        self.assertEqual(len(rounds), 26)
        games = [g for rnd in rounds for g in rnd]
        self.assertEqual(len(games), 26 * 7)
        # Every ordered pair (home, away) appears exactly once.
        self.assertEqual(len(set(games)), len(games))
        for a in ids:
            apps = sum(1 for h, w in games if a in (h, w))
            homes = sum(1 for h, _ in games if h == a)
            self.assertEqual(apps, 26)
            self.assertEqual(homes, 13)
        # No club plays twice in one round.
        for rnd in rounds:
            seen = [c for g in rnd for c in g]
            self.assertEqual(len(seen), len(set(seen)))


class TestWorldCreation(unittest.TestCase):
    def test_new_world_shape(self):
        world = GameWorld.new(seed=1)
        self.assertEqual(len(world.clubs), 28)
        self.assertEqual(len(world.leagues), 2)
        for league in world.leagues:
            self.assertEqual(len(league.club_ids), 14)
        for club in world.clubs.values():
            self.assertGreaterEqual(len(club.squad), 20)
            self.assertTrue(any(p.position == "GK" for p in club.squad))
        # Calendar: 26 league rounds + 5 cup rounds + 2 playoff events.
        self.assertEqual(len(world.calendar), 33)

    def test_seed_reproducibility(self):
        w1 = GameWorld.new(seed=42)
        w2 = GameWorld.new(seed=42)
        names1 = [p.name for c in w1.clubs.values() for p in c.squad]
        names2 = [p.name for c in w2.clubs.values() for p in c.squad]
        self.assertEqual(names1, names2)


class TestMatchEngine(unittest.TestCase):
    def setUp(self):
        self.world = GameWorld.new(seed=3)

    def test_stronger_team_usually_wins(self):
        clubs = sorted(self.world.clubs.values(), key=lambda c: c.reputation)
        weak, strong = clubs[0], clubs[-1]
        rng = random.Random(9)
        strong_pts = weak_pts = 0
        for _ in range(150):
            for p in strong.squad + weak.squad:
                p.fitness = 100.0
            rep = simulate_match(rng, weak, strong, neutral=True)
            res = rep.result_for(strong.id)
            strong_pts += {"W": 3, "D": 1, "L": 0}[res]
            weak_pts += {"W": 0, "D": 1, "L": 3}[res]
        self.assertGreater(strong_pts, weak_pts * 1.5)

    def test_home_advantage(self):
        club_a = self.world.clubs[5]
        club_b = self.world.clubs[6]
        rng = random.Random(11)
        home_goals = away_goals = 0
        for _ in range(300):
            for p in club_a.squad + club_b.squad:
                p.fitness = 100.0
            rep = simulate_match(rng, club_a, club_b)
            home_goals += rep.home_goals
            away_goals += rep.away_goals
            rep2 = simulate_match(rng, club_b, club_a)
            home_goals += rep2.home_goals
            away_goals += rep2.away_goals
        self.assertGreater(home_goals, away_goals)

    def test_knockout_always_has_winner(self):
        rng = random.Random(4)
        a, b = self.world.clubs[1], self.world.clubs[2]
        for _ in range(60):
            for p in a.squad + b.squad:
                p.fitness = 100.0
            rep = simulate_match(rng, a, b, knockout=True)
            self.assertIn(rep.winner_id, (a.id, b.id))


class TestSeason(unittest.TestCase):
    def test_full_season(self):
        world = GameWorld.new(seed=7)
        # Run up to (but not through) the playoff semis to inspect final tables.
        while world.next_event()["type"] != "playoff_semis":
            world.advance()
        for league in world.leagues:
            table = league.table()
            self.assertEqual(len(table), 14)
            for row in table:
                self.assertEqual(row["P"], 26)
                self.assertEqual(row["Pts"], row["W"] * 3 + row["D"])
        self.assertTrue(world.cup.finished)

        summary = world.simulate_rest_of_season()
        self.assertEqual(summary["season"], "2026/27")
        self.assertEqual(len(summary["promoted"]), 3)
        self.assertEqual(len(summary["relegated"]), 3)
        self.assertIn(summary["cup_winner"],
                      [c.name for c in world.clubs.values()])
        self.assertGreater(summary["awards"]["top_scorer"]["goals"], 5)
        # Division sizes intact after promotion/relegation.
        self.assertEqual(len(world.division_clubs(0)), 14)
        self.assertEqual(len(world.division_clubs(1)), 14)
        # New season began automatically.
        self.assertEqual(world.year, data.START_YEAR + 1)
        self.assertEqual(world.calendar_pos, 0)


class TestMultiYear(unittest.TestCase):
    def test_five_season_sim(self):
        world = GameWorld.new(seed=13)
        summaries = world.simulate_years(5)
        self.assertEqual(len(summaries), 5)
        self.assertEqual(len(world.history), 5)
        self.assertEqual(world.year, data.START_YEAR + 5)
        seasons = [s["season"] for s in summaries]
        self.assertEqual(seasons, ["2026/27", "2027/28", "2028/29",
                                   "2029/30", "2030/31"])
        # The world stays healthy: squads stocked, some players retired.
        for club in world.clubs.values():
            self.assertGreaterEqual(len(club.squad), 16)
        self.assertGreater(len(world.retired), 20)
        # Trophy history accrues.
        total_titles = sum(len(v) for c in world.clubs.values()
                           for v in c.trophies.values())
        self.assertEqual(total_titles, 5 * 3)  # 2 league titles + 1 cup per year

    def test_development_and_aging(self):
        world = GameWorld.new(seed=21)
        young = [p for c in world.clubs.values() for p in c.squad if p.age <= 19]
        sample = {p.id: (p.age, p.ability) for p in young[:30]}
        world.simulate_years(3)
        grew = aged = found = 0
        for club in world.clubs.values():
            for p in club.squad:
                if p.id in sample:
                    found += 1
                    old_age, old_ca = sample[p.id]
                    if p.age == old_age + 3:
                        aged += 1
                    if p.ability > old_ca:
                        grew += 1
        self.assertGreater(found, 5)
        self.assertEqual(aged, found)
        self.assertGreater(grew / found, 0.8)  # teenagers overwhelmingly improve


class TestPlayerGeneration(unittest.TestCase):
    def test_generated_ability_near_target(self):
        rng = random.Random(2)
        for target in (50, 70, 85):
            for pos in ("GK", "DF", "MF", "FW"):
                p = generate_player(rng, 1, pos, 24, target)
                self.assertLess(abs(p.ability - target), 15)
                self.assertGreaterEqual(p.potential, int(p.ability))

    def test_value_peaks_before_decline(self):
        rng = random.Random(5)
        young = generate_player(rng, 1, "FW", 24, 80)
        old = generate_player(rng, 2, "FW", 34, 80)
        self.assertGreater(young.value, old.value)


class TestSaveLoad(unittest.TestCase):
    def test_roundtrip_preserves_state_and_determinism(self):
        world = GameWorld.new(seed=17)
        for _ in range(8):
            world.advance()
        blob = json.dumps(world.to_dict())
        clone = GameWorld.from_dict(json.loads(blob))

        self.assertEqual(clone.year, world.year)
        self.assertEqual(clone.calendar_pos, world.calendar_pos)
        self.assertEqual(len(clone.clubs), len(world.clubs))
        for cid, club in world.clubs.items():
            self.assertEqual(len(clone.clubs[cid].squad), len(club.squad))
        self.assertEqual([r["Pts"] for r in clone.leagues[0].table()],
                         [r["Pts"] for r in world.leagues[0].table()])

        # Restored RNG state ⇒ identical futures.
        r1 = world.advance()
        r2 = clone.advance()
        self.assertEqual([rep.score_line for rep in r1["reports"]],
                         [rep.score_line for rep in r2["reports"]])

    def test_roundtrip_mid_multiyear(self):
        world = GameWorld.new(seed=23)
        world.simulate_years(2)
        blob = json.dumps(world.to_dict())
        clone = GameWorld.from_dict(json.loads(blob))
        s1 = world.simulate_years(1)[0]
        s2 = clone.simulate_years(1)[0]
        self.assertEqual(s1["champions"], s2["champions"])
        self.assertEqual(s1["cup_winner"], s2["cup_winner"])


class TestTransfers(unittest.TestCase):
    def test_ai_window_moves_players_legally(self):
        world = GameWorld.new(seed=29)
        world.simulate_years(1)  # window runs at the start of season 2
        # Squad integrity: every player's club_id matches the club holding them.
        for club in world.clubs.values():
            for p in club.squad:
                self.assertEqual(p.club_id, club.id)
        all_ids = [p.id for c in world.clubs.values() for p in c.squad]
        self.assertEqual(len(all_ids), len(set(all_ids)))


class TestFormations(unittest.TestCase):
    def test_all_formations_field_eleven(self):
        world = GameWorld.new(seed=31)
        club = world.clubs[1]
        for formation in FORMATIONS:
            club.tactics.formation = formation
            xi = club.pick_lineup()
            self.assertEqual(len(xi), 11)
            slots = club.lineup_positions(xi)
            self.assertEqual(len(slots), 11)
            self.assertEqual(sum(1 for pos, _ in slots if pos == "GK"), 1)


if __name__ == "__main__":
    unittest.main()
