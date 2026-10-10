import unittest

import z3

from calc_fan import BIT, ORDER, evaluate_shape, score_hand, special_scores
from shape_solver import ShapeSolver


class SolverTests(unittest.TestCase):
    def solver(self, **kwargs):
        return ShapeSolver(timeout_ms=15000, **kwargs)

    def test_independent_equations_match_python_on_eighty_models(self):
        solver = self.solver()
        for _ in range(80):
            self.assertEqual(solver.check(), z3.sat)
            witness = solver.decode()
            if witness.kind == 'standard':
                score = evaluate_shape(witness.groups, witness.pair, witness.win_group, witness.context)
            else:
                score = special_scores(witness.hand + (witness.context.win,), witness.context)[0]
            self.assertFalse(score.yakuman)
            self.assertEqual(score.mask, witness.mask)
            self.assertEqual(score.closed, witness.closed)
            solver.block_model()

    def test_open_riichi_is_impossible(self):
        solver = self.solver(closed=False)
        solver.require_yaku({'riichi'})
        self.assertEqual(solver.check(), z3.unsat)

    def test_three_dragon_yaku_are_natural_yakuman(self):
        solver = self.solver()
        solver.require_yaku({'haku', 'hatsu', 'chun'})
        self.assertEqual(solver.check(), z3.unsat)

    def test_chiitoitsu_does_not_combine_with_ryanpeikou(self):
        solver = self.solver()
        solver.require_yaku({'chiitoitsu', 'ryanpeikou'})
        self.assertEqual(solver.check(), z3.unsat)

    def test_riichi_double_riichi_are_exclusive(self):
        solver = self.solver()
        solver.require_yaku({'riichi', 'double_riichi'})
        self.assertEqual(solver.check(), z3.unsat)

    def test_sankantsu_double_riichi_ippatsu_are_incompatible(self):
        solver = self.solver()
        solver.require_yaku({'sankantsu', 'double_riichi', 'ippatsu'})
        self.assertEqual(solver.check(), z3.unsat)

    def test_rinshan_pinfu_is_impossible_in_four_players(self):
        solver = self.solver()
        solver.require_yaku({'rinshan', 'pinfu'})
        self.assertEqual(solver.check(), z3.unsat)

    def test_haitei_and_rinshan_are_exclusive(self):
        solver = self.solver()
        solver.require_yaku({'haitei', 'rinshan'})
        self.assertEqual(solver.check(), z3.unsat)

    def test_ranked_round_does_not_reach_north(self):
        solver = self.solver()
        solver.solver.add(solver.round == 30)
        self.assertEqual(solver.check(), z3.unsat)

    def test_double_riichi_chankan_has_a_non_yakuman_witness(self):
        solver = self.solver(closed=True, kind='standard')
        solver.require_yaku({'double_riichi', 'chankan'})
        solver.solver.add(*(z3.Not(flag) for flag in solver.kan))
        self.assertEqual(solver.check(), z3.sat)
        witness = solver.decode()
        selected = score_hand(witness.hand, witness.context, witness.melds)
        self.assertTrue(any(score.mask & BIT['double_riichi'] and score.mask & BIT['chankan'] for score in selected))

    def test_projection_blocking_keeps_other_sets(self):
        solver = self.solver()
        self.assertEqual(solver.check(), z3.sat)
        first = solver.decode()
        solver.block_projection(first.closed, first.mask)
        self.assertEqual(solver.check(), z3.sat)
        second = solver.decode()
        self.assertNotEqual((first.closed, first.mask), (second.closed, second.mask))

    def test_every_ordinary_yaku_has_a_structural_witness(self):
        for name in ORDER:
            with self.subTest(yaku=name):
                solver = self.solver()
                solver.require_yaku({name})
                self.assertEqual(solver.check(), z3.sat)
                witness = solver.decode()
                if witness.kind == 'standard':
                    score = evaluate_shape(witness.groups, witness.pair, witness.win_group, witness.context)
                else:
                    score = special_scores(witness.hand + (witness.context.win,), witness.context)[0]
                self.assertIn(name, score.yaku)
                self.assertEqual(score.mask, witness.mask)


if __name__ == '__main__':
    unittest.main()
