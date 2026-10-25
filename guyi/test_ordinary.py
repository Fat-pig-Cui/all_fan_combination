#!/usr/bin/env python3
"""Regression checks for the ordinary ancient-yaku delta model."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'ordinary'))
from calc_fan import Context, Group, evaluate_shape, parse_tiles, score_hand
from enumerate_guyi import witness
from reachability import condition_certificate
from shape_solver import ShapeSolver
import z3


def win(completed, tile, **kwargs):
    hand = list(parse_tiles(completed))
    t = parse_tiles(tile)[0]
    hand.remove(t)
    return score_hand(hand, Context(t, **kwargs))


class OrdinaryGuyiTests(unittest.TestCase):
    def test_three_identical_sequences_replaces_one_peikou(self):
        groups = (Group(2, True),) * 3 + (Group(15, True),)
        s = evaluate_shape(groups, 23, 0, Context(2))
        self.assertIn('three_same_sequences', s.yaku)
        self.assertNotIn('iipeikou', s.yaku)
        self.assertNotIn('three_consecutive_triplets', s.yaku)

    def test_four_identical_sequences_coexists_two_peikou(self):
        s = evaluate_shape((Group(2, True),) * 4, 7, 0, Context(2))
        self.assertIn('three_same_sequences', s.yaku)
        self.assertIn('ryanpeikou', s.yaku)
        self.assertNotIn('iipeikou', s.yaku)

    def test_consecutive_triplets_and_sequences_not_cross_decomposed(self):
        scores = win('333444555m789p66s', '5m')
        self.assertTrue(scores)
        for s in scores:
            self.assertFalse({'three_same_sequences', 'three_consecutive_triplets'} <= set(s.yaku))

    def test_closed_triple_sequence_with_fourth_triplet_loses(self):
        # Even junchan (three han) cannot rescue this sequence reading.
        scores = win('111222333m999p11s', '2m')
        self.assertTrue(scores)
        for s in scores:
            self.assertNotIn('three_same_sequences', s.yaku)
            self.assertTrue({'toitoi', 'sanankou', 'three_consecutive_triplets'} <= set(s.yaku))
        scores = win('111222333m999p11s', '2m', tsumo=True)
        self.assertTrue(all(s.yakuman for s in scores))

    def test_closed_triple_sequences_outside_exception_is_kept(self):
        for kwargs in ({'tsumo': True}, {'event': 'chankan'}):
            scores = win('333444555m789p66s', '9p', **kwargs)
            self.assertTrue(all('three_same_sequences' not in s.yaku for s in scores))
            scores = win('111222333m789p11s', '9p', **kwargs)
            self.assertTrue(any({'three_same_sequences', 'junchan'} <= set(s.yaku) for s in scores))

    def test_no_sanankou_consecutive_reading_needs_a_fixed_kan(self):
        scores = win('333444555m789p66s', '4m')
        self.assertTrue(all('three_consecutive_triplets' not in s.yaku for s in scores))
        w = witness(dict(hand='44555m789p66s', win='4m', melds=[{'kind':'ankan','tiles':'3333m'}]))
        scores = score_hand(w.hand, w.context, w.melds)
        self.assertTrue(any('three_consecutive_triplets' in s.yaku and 'sanankou' not in s.yaku for s in scores))

    def test_four_identical_sequences_beat_unfixed_consecutive_triplets(self):
        for kwargs in ({}, {'tsumo': True}):
            scores = win('444455556666m77p', '4m', **kwargs)
            self.assertTrue(all({'ryanpeikou', 'three_same_sequences'} <= set(s.yaku) for s in scores))
            self.assertTrue(all('three_consecutive_triplets' not in s.yaku for s in scores))

    def test_three_consecutive_kans_count_as_triplets(self):
        groups = tuple(Group(t, open=True, kan=True) for t in (2, 3, 4)) + (Group(15, True),)
        s = evaluate_shape(groups, 23, 3, Context(15))
        self.assertIn('three_consecutive_triplets', s.yaku)
        self.assertIn('sankantsu', s.yaku)

    def test_four_calls_includes_tsumo_and_minkan(self):
        groups = (Group(0, open=True, kan=True), Group(3, True, True),
                  Group(12, True, True), Group(21, True, True))
        s = evaluate_shape(groups, 25, -1, Context(25, tsumo=True))
        self.assertIn('four_calls', s.yaku)

    def test_ankan_not_counted_as_open_call(self):
        groups = (Group(0, kan=True), Group(3, True, True),
                  Group(12, True, True), Group(21, True, True))
        s = evaluate_shape(groups, 25, -1, Context(25))
        self.assertNotIn('four_calls', s.yaku)

    def test_five_gates_with_seven_pairs(self):
        s, = win('11m22p33s11225566z', '6z')
        self.assertEqual(set(s.yaku), {'chiitoitsu', 'five_gates'})

    def test_five_gates_requires_wind_and_dragon(self):
        s, = win('11m22p33s44556677s', '7s')
        self.assertNotIn('five_gates', s.yaku)

    def test_ordinary_roles_can_be_only_source_of_yaku(self):
        self.assertFalse(win('234567m234567p11s', '1s'))
        s, = win('234567m234567p11s', '1s', tsubame=True)
        self.assertEqual(s.yaku, ('tsubame',))
        self.assertFalse(s.yakuman)

    def test_tsubame_and_kanburi_can_coexist(self):
        s, = win('234567m234567p55s', '5s', tsubame=True, kanburi=True)
        self.assertTrue({'tsubame', 'kanburi'} <= set(s.yaku))
        w = witness(dict(hand='234567m234567p5s', win='5s', tsubame=True, kanburi=True))
        self.assertIsNotNone(condition_certificate(w))

    def test_kanburi_interrupts_ippatsu(self):
        with self.assertRaises(ValueError):
            Context(4, riichi=1, ippatsu=True, kanburi=True)

    def test_tsubame_can_coexist_ippatsu(self):
        s, = win('234567m234567p55s', '5s', riichi=2, ippatsu=True, tsubame=True)
        self.assertTrue({'tsubame', 'double_riichi', 'ippatsu'} <= set(s.yaku))

    def test_tsubame_cannot_coexist_last_discard(self):
        with self.assertRaises(ValueError):
            Context(17, event='houtei', tsubame=True)

    def test_pin_moon_replaces_haitei(self):
        s, = win('234567m234567s11p', '1p', tsumo=True, event='haitei')
        self.assertEqual(set(s.yaku), {'menzen_tsumo', 'pin_moon'})
        self.assertEqual(s.han, 6)

    def test_pin_fish_replaces_houtei(self):
        s, = win('234567m234567s99p', '9p', event='houtei')
        self.assertEqual(set(s.yaku), {'pin_fish'})
        self.assertEqual(s.han, 5)

    def test_last_events_other_tiles_unchanged(self):
        s, = win('234567m234567s55p', '5p', event='houtei')
        self.assertEqual(set(s.yaku), {'houtei', 'tanyao'})

    def test_double_riichi_last_draw_becomes_natural_even_moon(self):
        s, = win('234567m234567s11p', '1p', tsumo=True, riichi=2, event='haitei')
        self.assertEqual(s.yaku, ())
        self.assertEqual(s.yakuman, ('shangshang',))

    def test_double_riichi_last_discard_becomes_natural_even_fish(self):
        s, = win('234567m234567s99p', '9p', riichi=2, event='houtei')
        self.assertEqual(s.yaku, ())
        self.assertEqual(s.yakuman, ('shangshang',))

    def test_wheels_suppress_other_standard_interpretations(self):
        for suit, yakuman in zip('mps', ('big_numbers', 'big_wheel', 'big_bamboo')):
            scores = win('22334455667788' + suit, '8' + suit)
            self.assertEqual(len(scores), 1)
            self.assertEqual(scores[0].yakuman, (yakuman,))
            self.assertFalse(scores[0].yaku)

    def test_wheel_is_closed_only(self):
        w = witness(dict(hand='2345678p', win='8p', melds=[{'kind':'chi','tiles':'234p'}, {'kind':'chi','tiles':'567p'}]))
        scores = score_hand(w.hand, w.context, w.melds)
        self.assertTrue(scores)
        self.assertTrue(all(not s.yakuman for s in scores))

    def test_seven_stars_replaces_all_honors(self):
        s, = win('11223344556677z', '7z')
        self.assertEqual(s.yakuman, ('big_seven_stars',))

    def test_solver_and_independent_single_decomposition_agree(self):
        solver = ShapeSolver(seed=19)
        from enumerate_ordinary_sharded import selected_score_constraints
        selected_score_constraints(solver)
        for _ in range(80):
            self.assertEqual(solver.check(), z3.sat)
            w = solver.decode()
            if w.kind == 'standard':
                s = evaluate_shape(w.groups, w.pair, w.win_group, w.context)
            else:
                from calc_fan import special_scores
                s, = special_scores(w.hand + (w.context.win,), w.context)
            self.assertFalse(s.yakuman)
            self.assertEqual((s.closed, s.mask), (w.closed, w.mask))
            solver.block_projection(w.closed, w.mask)


if __name__ == '__main__':
    unittest.main()
