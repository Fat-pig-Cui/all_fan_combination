import unittest
from types import SimpleNamespace

from calc_fan import Context, Group, parse_tiles
from reachability import condition_certificate


class ReachabilityTests(unittest.TestCase):
    def witness(self, hand, melds, context):
        return SimpleNamespace(hand=parse_tiles(hand), melds=melds, context=context)

    def test_three_ankans_after_double_riichi_with_unchanged_waits(self):
        witness = self.witness('12m 55p', (Group(8, kan=True), Group(31, kan=True), Group(32, kan=True)), Context(2, riichi=2))
        proof = condition_certificate(witness)
        self.assertIsNotNone(proof)
        self.assertEqual(len(proof['post_riichi_kans']), 3)

    def test_double_riichi_ankan_changing_waits_is_rejected(self):
        witness = self.witness('2345678999m', (Group(0, kan=True),), Context(1, riichi=2))
        self.assertIsNone(condition_certificate(witness))

    def test_ordinary_riichi_rinshan_ankan_changing_waits_is_rejected(self):
        witness = self.witness('2345678999m', (Group(0, kan=True),), Context(1, tsumo=True, riichi=1, event='rinshan'))
        self.assertIsNone(condition_certificate(witness))

    def test_ordinary_riichi_can_follow_an_earlier_ankan(self):
        witness = self.witness('2345678999m', (Group(0, kan=True),), Context(1, riichi=1))
        self.assertIsNotNone(condition_certificate(witness))

    def test_ordinary_riichi_rinshan_has_a_fourth_tile_certificate(self):
        witness = self.witness('12m 456p 789s 55p', (Group(8, kan=True),), Context(2, tsumo=True, riichi=1, event='rinshan'))
        proof = condition_certificate(witness)
        self.assertIsNotNone(proof)
        self.assertEqual(proof['post_riichi_kans'][0]['draw_fourth'], '9m')

    def test_ippatsu_chankan_uses_preexisting_opponent_pon(self):
        witness = self.witness('12m 123p 123s 456s 77p', (), Context(2, riichi=1, ippatsu=True, event='chankan'))
        proof = condition_certificate(witness)
        self.assertIn('Opponent pon precedes ordinary riichi', ' '.join(proof['construction']))

    def test_double_riichi_chankan_has_no_ordinary_reachability_certificate(self):
        witness = self.witness('12m 123p 123s 456s 77p', (), Context(2, riichi=2, event='chankan'))
        self.assertIsNone(condition_certificate(witness))

    def test_ordinary_riichi_chankan_without_ippatsu_can_use_earlier_pon(self):
        witness = self.witness('12m 123p 123s 456s 77p', (), Context(2, riichi=1, event='chankan'))
        proof = condition_certificate(witness)
        self.assertIsNotNone(proof)
        self.assertIn('Opponent pon precedes ordinary riichi', ' '.join(proof['construction']))


if __name__ == '__main__':
    unittest.main()
