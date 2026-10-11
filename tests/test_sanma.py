from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import z3
from calc_fan import Context, Group, evaluate_shape, parse_tiles, score_hand, score_request, special_scores, waits
from enumerate_combinations import enumerate_sets
from reachability import condition_certificate
from rules import THREE_PLAYER, FOUR_PLAYER
from shape_solver import ShapeSolver


class SanmaTests(unittest.TestCase):
    def nuki(self, hand='22446688p22446s', win='6s', **kwargs):
        data = dict(players=3, hand=hand, win=win, tsumo=True,
                    event='rinshan', win_source='north_replacement', north_count=1)
        data.update(kwargs)
        return score_request(data)

    def test_108_tile_configuration_and_three_live_tile_riichi(self):
        self.assertEqual(len(THREE_PLAYER.available_tiles) * 4, 108)
        self.assertEqual(THREE_PLAYER.riichi_min_live_tiles, 3)
        self.assertNotEqual(THREE_PLAYER.fingerprint, FOUR_PLAYER.fingerprint)

    def test_nuki_seven_pairs_does_not_add_dora_or_chankan(self):
        r = self.nuki()['results'][0]
        self.assertEqual({y['slug'] for y in r['yaku']}, {'chiitoitsu', 'tanyao', 'menzen_tsumo', 'rinshan'})
        self.assertEqual((r['han'], r['dora'], r['fu']), (5, 0, 25))

    def test_nuki_pinfu_and_ryanpeikou(self):
        for hand, win, role in [('123456789p23s55s', '1s', 'pinfu'), ('112233p4455667s', '7s', 'ryanpeikou')]:
            yaku = {y['slug'] for y in self.nuki(hand, win)['results'][0]['yaku']}
            self.assertIn(role, yaku)
            self.assertIn('rinshan', yaku)

    def test_four_player_nuki_is_rejected(self):
        with self.assertRaises(ValueError):
            self.nuki(players=4)

    def test_interior_manzu_and_chi_are_rejected(self):
        with self.assertRaises(ValueError):
            self.nuki('123m456789p23s55s', '1s')
        with self.assertRaises(ValueError):
            self.nuki('456789p23s55s', '1s', melds=[{'kind': 'chi', 'tiles': '123p'}])

    def test_no_north_seat_or_north_round(self):
        for field in ('seat', 'round_wind'):
            with self.assertRaises(ValueError):
                self.nuki(**{field: '4z'})

    def test_north_is_not_yakuhai(self):
        r = score_request(dict(players=3, hand='111p999p111s44z55z', win='4z'))['results'][0]
        self.assertFalse(r['yakuman'])
        self.assertNotIn('seat_wind', {y['slug'] for y in r['yaku']})
        self.assertNotIn('round_wind', {y['slug'] for y in r['yaku']})

    def test_north_four_copy_inventory(self):
        with self.assertRaises(ValueError):
            self.nuki('123456789p44z23s', '1s', north_count=3)
        self.assertTrue(self.nuki('123456789p44z23s', '1s', north_count=2)['legal_win'])

    def test_north_capacity_with_ankan(self):
        with self.assertRaises(ValueError):
            self.nuki('123456p23s55s', '1s', melds=[{'kind': 'ankan', 'tiles': '4444z'}])

    def test_last_live_tile_and_ippatsu_are_rejected_for_nuki(self):
        with self.assertRaises(ValueError):
            self.nuki(live_tiles=1)
        with self.assertRaises(ValueError):
            self.nuki(riichi=1, ippatsu=True)

    def test_last_live_tile_also_rejects_kan_and_opponent_nuki(self):
        with self.assertRaises(ValueError):
            score_request(dict(players=3, hand='2345678999p', win='2p', tsumo=True,
                               event='rinshan', live_tiles=1, melds=[{'kind': 'ankan', 'tiles': '1111p'}]))
        with self.assertRaises(ValueError):
            score_request(dict(players=3, hand='123456p789s555z4z', win='4z',
                               win_source='north_ron', live_tiles=1))

    def test_nuki_after_ordinary_riichi_does_not_retroactively_restrict_earlier_kan(self):
        hand = parse_tiles('2345678999p')
        melds = (Group(9, kan=True),)
        c = Context(win=10, tsumo=True, riichi=1, players=3, event='rinshan')
        self.assertIsNone(condition_certificate(SimpleNamespace(hand=hand, melds=melds, context=c)))
        c = replace(c, north_count=1, win_source='north_replacement')
        self.assertIsNotNone(condition_certificate(SimpleNamespace(hand=hand, melds=melds, context=c)))

    def test_double_riichi_nuki_keeps_declaration_and_waits(self):
        c = Context(win=23, tsumo=True, players=3, riichi=2, event='rinshan',
                    north_count=1, win_source='north_replacement')
        hand = parse_tiles('22446688p22446s')
        certificate = condition_certificate(SimpleNamespace(hand=hand, melds=(), context=c))
        self.assertEqual(certificate['north_extraction']['waits_before'], certificate['north_extraction']['waits_after'])
        self.assertTrue(certificate['north_extraction']['uses_just_drawn_tile'])
        self.assertEqual(certificate['riichi'], 2)

    def test_three_player_ippatsu_haitei_cycle(self):
        c = Context(win=23, tsumo=True, players=3, riichi=1, ippatsu=True, event='haitei')
        certificate = condition_certificate(SimpleNamespace(hand=parse_tiles('22446688p22446s'), melds=(), context=c))
        self.assertEqual(certificate['last_cycle']['live_tiles_at_riichi'], 3)
        self.assertEqual(certificate['last_cycle']['opponent_draws'], 2)

    def test_rob_north_is_not_chankan_and_needs_another_yaku(self):
        r = score_request(dict(players=3, hand='123456p789s555z4z', win='4z', win_source='north_ron'))
        self.assertTrue(r['legal_win'])
        self.assertNotIn('chankan', {y['slug'] for y in r['results'][0]['yaku']})
        r = score_request(dict(players=3, hand='123456p789s111p4z', win='4z', win_source='north_ron'))
        self.assertFalse(r['legal_win'])

    def test_extracted_north_reserves_opponent_kan_copies(self):
        with self.assertRaises(ValueError):
            score_request(dict(players=3, hand='19m19p19s1235677z', win='4z',
                               event='chankan', north_count=1))

    def test_sanma_structural_waits_exclude_missing_manzu(self):
        self.assertTrue(waits(parse_tiles('123456789p23s55s'), players=3))
        with self.assertRaises(ValueError):
            waits(parse_tiles('123m456789p23s55s'), players=3)

    def test_natural_yakuman_still_suppresses_nuki_roles(self):
        r = self.nuki('1122334455667z', '7z')['results'][0]
        self.assertTrue(r['yakuman'])
        self.assertFalse(r['yaku'])

    def test_sanshoku_doukou_remains_but_doujun_is_impossible(self):
        for role, status in [('sanshoku_doukou', z3.sat), ('sanshoku_doujun', z3.unsat)]:
            solver = ShapeSolver(players=3, timeout_ms=15000)
            solver.require_yaku({role})
            self.assertEqual(solver.check(), status)

    def test_solver_independent_equations_on_forty_sanma_models(self):
        solver = ShapeSolver(players=3, timeout_ms=15000)
        for _ in range(40):
            self.assertEqual(solver.check(), z3.sat)
            w = solver.decode()
            score = (evaluate_shape(w.groups, w.pair, w.win_group, w.context) if w.kind == 'standard'
                     else special_scores(w.hand + (w.context.win,), w.context)[0])
            self.assertEqual((score.mask, score.closed), (w.mask, w.closed))
            self.assertFalse(score.yakuman)
            solver.block_model()

    def test_resume_does_not_mix_player_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            summary = enumerate_sets(path, players=3, limit=2, timeout_ms=15000, log_every=100)
            self.assertFalse(summary['complete'])
            with self.assertRaisesRegex(ValueError, 'Player count'):
                enumerate_sets(path, players=4, resume=True)


if __name__ == '__main__':
    unittest.main()
