"""Test suite for the FM27 simulation engine."""

import json
import random
import unittest

from fm27 import data, editor
from fm27.club import FORMATIONS
from fm27.competition import Cup, round_robin_rounds
from fm27.match_engine import simulate_match
from fm27.player import ATTRS, Player, generate_player, migrate_attrs
from fm27.world import GameWorld


def plant_star(world, club_id):
    """Turn a club's best forward into a 99-rated superstar."""
    club = world.clubs[club_id]
    star = max((p for p in club.squad if p.position == "FW"),
               key=lambda p: p.ability)
    for a in star.attrs:
        star.attrs[a] = 90.0
    for a in ("finishing", "composure", "pace", "dribbling", "heading"):
        star.attrs[a] = 99.0
    star.age = 25
    star.potential = 99
    return star


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
        self.assertEqual(len(world.clubs), 44)
        self.assertEqual(len(world.leagues), 2)
        self.assertEqual(len(world.leagues[0].club_ids), 20)
        self.assertEqual(len(world.leagues[1].club_ids), 24)
        names = {c.name for c in world.clubs.values()}
        self.assertIn("Liverpool", names)
        self.assertIn("Wrexham", names)
        for club in world.clubs.values():
            self.assertGreaterEqual(len(club.squad), 18)
            self.assertTrue(any(p.position == "GK" for p in club.squad))
        # Calendar: 38 PL + 46 Championship rounds + 6 cup rounds + 2 playoffs.
        self.assertEqual(Cup.rounds_needed(44), 6)
        self.assertEqual(len(world.calendar), 38 + 46 + 6 + 2)
        # Cup final is scheduled after every league round, before the playoffs.
        types = [(e["type"], e.get("round")) for e in world.calendar]
        self.assertEqual(types[-3], ("cup", 5))
        self.assertEqual(types[-2], ("playoff_semis", None))

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
        for league, size, games in ((world.leagues[0], 20, 38),
                                    (world.leagues[1], 24, 46)):
            table = league.table()
            self.assertEqual(len(table), size)
            for row in table:
                self.assertEqual(row["P"], games)
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
        self.assertEqual(len(world.division_clubs(0)), 20)
        self.assertEqual(len(world.division_clubs(1)), 24)
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


class TestLoans(unittest.TestCase):
    def test_ai_loans_exist_and_are_consistent(self):
        world = GameWorld.new(seed=29)
        loanees = [(p, c) for c in world.clubs.values() for p in c.squad
                   if p.loaned_from is not None]
        self.assertGreater(len(loanees), 0)
        for p, host in loanees:
            self.assertNotEqual(p.loaned_from, host.id)
            self.assertIn(p.loaned_from, world.clubs)
            self.assertLessEqual(p.age, 22)
            # The loanee is not simultaneously in the parent's squad.
            parent = world.clubs[p.loaned_from]
            self.assertNotIn(p, parent.squad)
        loan_news = [line for line in world.last_window_transfers
                     if line.startswith("LOAN:")]
        self.assertEqual(len(loan_news), len(loanees))

    def test_loans_survive_seasons_and_windows(self):
        world = GameWorld.new(seed=31)
        world.simulate_years(2)  # covers January windows and loan returns
        for club in world.clubs.values():
            for p in club.squad:
                self.assertEqual(p.club_id, club.id)
                if p.loaned_from is not None:
                    self.assertIn(p.loaned_from, world.clubs)
        all_ids = [p.id for c in world.clubs.values() for p in c.squad]
        self.assertEqual(len(all_ids), len(set(all_ids)))


class TestWindowsAndScouting(unittest.TestCase):
    def test_window_schedule(self):
        world = GameWorld.new(seed=37)
        self.assertTrue(world.window_open)          # pre-season
        world.advance()
        self.assertFalse(world.window_open)         # season underway
        while world.calendar_pos < world.mid_window_start:
            world.advance()
        self.assertTrue(world.window_open)          # January

    def test_scout_report_pipeline(self):
        world = GameWorld.new(seed=41)
        world.user_club_id = 20                     # take over a modest club
        target = next(p for c in world.clubs.values() if c.id != 20
                      for p in c.squad)
        self.assertTrue(world.queue_scout(target.id))
        self.assertFalse(world.queue_scout(target.id))   # no duplicates
        result = world.advance()
        self.assertIn(target.name, result["scout_completed"])
        rep = world.scout_reports[target.id]
        self.assertGreaterEqual(rep["potential_est"], int(rep["ability"]))
        self.assertEqual(rep["attrs"].keys(), target.attrs.keys())
        self.assertTrue(1 <= rep["stars"] <= 5)

    def test_reports_survive_save_load(self):
        world = GameWorld.new(seed=43)
        world.user_club_id = 1
        target = next(p for c in world.clubs.values() if c.id != 1
                      for p in c.squad)
        world.queue_scout(target.id)
        world.advance()
        clone = GameWorld.from_dict(json.loads(json.dumps(world.to_dict())))
        self.assertIn(target.id, clone.scout_reports)   # int keys restored


class TestStarPlayers(unittest.TestCase):
    def test_star_striker_plays_and_scores(self):
        # A 99-OVR forward at a modest club must start almost every game and
        # rack up an elite goal tally (regression: greedy slot-filling used
        # to field him as a defender; weak scorer weighting starved his tally).
        world = GameWorld.new(seed=12)
        star = plant_star(world, 30)
        world.simulate_rest_of_season()
        self.assertGreaterEqual(star.career["apps"], 35)
        self.assertGreaterEqual(star.career["goals"], 30)

    def test_star_keeps_natural_position(self):
        # Even in a defender-heavy formation at a weak club, an elite forward
        # is picked as a forward — never repurposed to patch the back line.
        world = GameWorld.new(seed=11)
        club = world.clubs[20]
        star = plant_star(world, 20)
        club.tactics.formation = "5-3-2"
        xi = club.pick_lineup()
        self.assertIn(star, xi)
        slots = club.lineup_positions(xi)
        slot = next(pos for pos, p in slots if p.id == star.id)
        self.assertEqual(slot, "FW")

    def test_best_players_start_across_the_league(self):
        world = GameWorld.new(seed=13)
        for club in world.clubs.values():
            xi = set(club.pick_lineup())
            for pos in ("GK", "DF", "MF", "FW"):
                group = sorted(club.players_at(pos), key=lambda p: -p.ability)
                if group and group[0].available:
                    self.assertIn(group[0], xi,
                                  f"{club.name}: best fit {pos} not starting")


class TestLeagueQuality(unittest.TestCase):
    def test_on_pitch_quality_does_not_inflate(self):
        world = GameWorld.new(seed=99)
        baseline = world.baseline_xi
        world.simulate_years(10)
        drift = world._avg_xi_strength() - baseline
        self.assertLess(abs(drift), 3.5)
        # Turnover keeps happening: new blood arrives as veterans leave
        # (some by retirement, others released into free agency).
        self.assertGreater(len(world.retired), 200)
        self.assertGreater(world.next_pid, 44 * 23 + 500)


class TestAttributeSystem(unittest.TestCase):
    def test_seventeen_attributes(self):
        world = GameWorld.new(seed=3)
        p = world.clubs[1].squad[0]
        self.assertEqual(set(p.attrs), set(ATTRS))
        self.assertEqual(len(ATTRS), 17)

    def test_legacy_save_migration(self):
        old = {"pace": 80, "shooting": 85, "passing": 70, "defending": 40,
               "physical": 75, "goalkeeping": 10}
        attrs = migrate_attrs(old)
        self.assertEqual(set(attrs), set(ATTRS))
        self.assertEqual(attrs["finishing"], 85)
        self.assertEqual(attrs["pace"], 80)
        self.assertEqual(attrs["reflexes"], 10)
        d = {"id": 1, "name": "Old Timer", "nation": "England",
             "position": "FW", "age": 28, "attrs": old, "potential": 88,
             "fitness": 90.0, "morale": 70.0, "injured_for": 0,
             "suspended_for": 0, "season": {"apps": 0, "goals": 0, "assists": 0,
                                            "yellows": 0, "reds": 0,
                                            "clean_sheets": 0, "rating_sum": 0.0},
             "career": {"apps": 100, "goals": 50, "assists": 20, "yellows": 5,
                        "reds": 0, "clean_sheets": 0, "rating_sum": 700.0,
                        "seasons": 5},
             "trophies": [], "club_id": 1}
        p = Player.from_dict(d)
        self.assertIn("finishing", p.attrs)
        self.assertGreater(p.ability, 60)


class TestContractsAndFreeAgency(unittest.TestCase):
    def test_contract_lifecycle(self):
        world = GameWorld.new(seed=51)
        for club in world.clubs.values():
            for p in club.squad:
                self.assertGreaterEqual(p.contract_years, 1)
        world.simulate_years(1)
        # Nobody employed is out of contract; releases went to the pool.
        for club in world.clubs.values():
            for p in club.squad:
                self.assertGreaterEqual(p.contract_years, 1)
        self.assertGreater(len(world.free_agents), 0)
        for p in world.free_agents:
            self.assertIsNone(p.club_id)
        # Free agents get signed in the next windows.
        pool_before = {p.id for p in world.free_agents}
        world.simulate_years(1)
        signed = [p for c in world.clubs.values() for p in c.squad
                  if p.id in pool_before]
        self.assertGreater(len(signed), 0)

    def test_expiring_contract_cuts_value(self):
        rng = random.Random(1)
        p = generate_player(rng, 1, "MF", 26, 75)
        p.contract_years = 4
        long_value = p.value
        p.contract_years = 1
        self.assertLess(p.value, long_value * 0.9)


class TestBoardAndSackings(unittest.TestCase):
    def test_sack_and_new_job(self):
        world = GameWorld.new(seed=53)
        world.start_career(20, "Doomed Manager")     # Burnley
        world.user_confidence = 0.0
        result = world.simulate_rest_of_season()      # halts on the sack
        self.assertIsNone(result)
        self.assertTrue(world.pending_sack)
        offers = world.job_offers()
        self.assertTrue(1 <= len(offers) <= 3)
        self.assertNotIn(20, [c.id for c in offers])
        world.accept_job(offers[0].id)
        self.assertFalse(world.pending_sack)
        self.assertEqual(world.user_club_id, offers[0].id)
        self.assertEqual(len(world.manager_stints), 2)
        self.assertEqual(world.manager_stints[0]["reason"], "sacked")
        # Career continues at the new club.
        self.assertIsNotNone(world.simulate_rest_of_season())

    def test_good_season_builds_confidence(self):
        world = GameWorld.new(seed=57)
        world.start_career(1, "Safe Hands")           # Liverpool, high expectation
        world.simulate_rest_of_season()
        if not world.pending_sack:                    # met expectations
            self.assertGreater(world.user_confidence, 30)
        self.assertIn("board", world.history[0])

    def test_unsackable_mode(self):
        world = GameWorld.new(seed=53)
        world.start_career(20, "Untouchable")
        world.unsackable = True
        world.user_confidence = 0.0
        summary = world.simulate_rest_of_season()     # runs to completion
        self.assertIsNotNone(summary)
        self.assertFalse(world.pending_sack)
        self.assertEqual(world.user_club_id, 20)


class TestAutopilot(unittest.TestCase):
    def test_assistant_manages_user_club_in_sims(self):
        world = GameWorld.new(seed=61)
        world.start_career(20, "Delegator")           # Burnley
        original_ids = {p.id for p in world.user_club.squad}
        outside_ids = {p.id for c in world.clubs.values() if c.id != 20
                       for p in c.squad}
        world.autopilot = True
        world.simulate_years(3)
        world.autopilot = False
        club = world.user_club
        if world.pending_sack:                        # autopilot can't stop the axe
            return
        # Contracts were renewed rather than everyone walking for free.
        for p in club.squad:
            self.assertGreaterEqual(p.contract_years, 1)
        # The assistant brought players in from elsewhere in the league.
        arrivals = {p.id for p in club.squad if p.loaned_from is None} & outside_ids
        self.assertGreater(len(arrivals), 0)
        self.assertGreaterEqual(len(club.squad), 16)

    def test_manual_mode_still_protects_user_club_from_ai_raids(self):
        # The AI transfer window must never buy or sell for the user's club
        # when the exclusion is set (contract expiries walking is separate).
        from fm27.transfers import run_ai_window
        world = GameWorld.new(seed=63)
        user_club = world.clubs[1]                    # Liverpool: prime raid target
        deals = run_ai_window(world.rng, list(world.clubs.values()),
                              user_club_id=user_club.id)
        for t in deals:
            self.assertNotEqual(t.from_club, user_club.name)
            self.assertNotEqual(t.to_club, user_club.name)
        # With autopilot (no exclusion) the same club is free to trade.
        world2 = GameWorld.new(seed=63)
        deals2 = run_ai_window(world2.rng, list(world2.clubs.values()),
                               user_club_id=None)
        self.assertGreater(len(deals2), 0)


class TestTrainingFocus(unittest.TestCase):
    def test_focus_shapes_growth(self):
        base = generate_player(random.Random(9), 1, "MF", 18, 55)
        base.potential = 90
        clone = Player.from_dict(base.to_dict())
        base.training_focus = "Physical"
        phys = ("pace", "stamina", "strength")
        before_a = sum(base.attrs[a] for a in phys)
        before_b = sum(clone.attrs[a] for a in phys)
        base.develop(random.Random(5), 1.0, 80)
        clone.develop(random.Random(5), 1.0, 80)
        gain_focused = sum(base.attrs[a] for a in phys) - before_a
        gain_balanced = sum(clone.attrs[a] for a in phys) - before_b
        self.assertGreater(gain_focused, gain_balanced)


class TestEditor(unittest.TestCase):
    def setUp(self):
        self.world = GameWorld.new(seed=47)

    def test_find_and_edit(self):
        player = self.world.clubs[1].squad[0]
        hits = editor.find_players(self.world, player.name[:6].lower())
        self.assertTrue(any(p.id == player.id for p, _ in hits))
        editor.set_name(player, "Test Legend")
        self.assertEqual(player.name, "Test Legend")
        editor.set_attribute(player, "finishing", 150)   # clamped
        self.assertEqual(player.attrs["finishing"], 99.0)
        editor.set_position(player, "fw")
        self.assertEqual(player.position, "FW")
        editor.set_potential(player, 1)                 # can't go below ability
        self.assertGreaterEqual(player.potential, int(player.ability))
        player.injured_for = 5
        editor.heal(player)
        self.assertEqual(player.injured_for, 0)

    def test_move_player(self):
        src, dst = self.world.clubs[1], self.world.clubs[30]
        player = src.squad[0]
        msg = editor.move_player(self.world, player, dst.id)
        self.assertIn(dst.name, msg)
        self.assertIn(player, dst.squad)
        self.assertNotIn(player, src.squad)
        self.assertEqual(player.club_id, dst.id)
        # Moving to the same club is a no-op with a friendly message.
        self.assertIn("already", editor.move_player(self.world, player, dst.id))


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
