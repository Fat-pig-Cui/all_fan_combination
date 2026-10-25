"""Regression checks for the sanma selected-interpretation pruning."""
import unittest
from collections import Counter
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'ordinary'))
from calc_fan import Context, Group, parse_tiles, score_hand, evaluate_shape


class SanmaSelectedInterpretationTests(unittest.TestCase):
    def test_closed_three_same_sequences_is_possible(self):
        scores = score_hand(parse_tiles('33344455p789s66z'), Context(13, players=3))
        self.assertTrue(any('three_same_sequences' in score.yaku for score in scores))

    def test_open_three_sequences_lose_for_both_suits_and_all_starts(self):
        checked = 0
        for suit in (9, 18):
            for rank in range(7):
                start = suit + rank
                for fixed_tile, pair in ((27, 31), (0, 8), (17, 26), (32, 29)):
                    for kan in (False, True):
                        fixed = Group(fixed_tile, False, True, kan)
                        seq_groups = (Group(start, True),) * 3 + (fixed,)
                        completed = tuple(tile for g in seq_groups[:3] for tile in g.tiles) + (pair, pair)
                        physical = completed + fixed.tiles
                        if max(Counter(physical).values()) > 4:
                            continue
                        for tsumo in (False, True):
                            for win in (start, start + 1, start + 2, pair):
                                context = Context(win, players=3, tsumo=tsumo)
                                hand = list(completed); hand.remove(win)
                                old = evaluate_shape(seq_groups, pair, -1 if win == pair else 0, context)
                                scores = score_hand(hand, context, (fixed,))
                                self.assertTrue(scores)
                                self.assertFalse(any('three_same_sequences' in score.yaku for score in scores))
                                self.assertTrue(scores[0].yakuman or scores[0].comparison_key > old.comparison_key)
                                checked += 1
        self.assertGreater(checked, 500)

    def test_terminal_three_suit_triplets_survive_sanma(self):
        scores = score_hand(parse_tiles('111m111p11s222p55z'), Context(18, players=3))
        self.assertTrue(any('sanshoku_doukou' in score.yaku for score in scores))

    def test_three_same_sequences_with_two_identical_sequence_pairs(self):
        scores = score_hand(parse_tiles('111122223333p5s'), Context(22, players=3))
        self.assertTrue(any({'three_same_sequences', 'ryanpeikou'} <= set(score.yaku) for score in scores))


if __name__ == '__main__':
    unittest.main()
