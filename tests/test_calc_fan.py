import unittest

from calc_fan import Context, Group, base_points, evaluate_shape, parse_tiles, score_hand, score_request, waits


def before_win(groups, pair, context):
    melds = tuple(group for group in groups if group.fixed)
    hand = list(tile for group in groups if not group.fixed for tile in group.tiles) + [pair, pair]
    hand.remove(context.win)
    return tuple(hand), melds


class CalcFanTests(unittest.TestCase):
    def setUp(self):
        self.sequences = (Group(0, True), Group(12, True), Group(24, True), Group(21, True))

    def test_compact_red_notation_and_bad_honors(self):
        self.assertEqual(parse_tiles('05m 5p'), (4, 4, 13))
        for text in ('0z', '8z', '123', '12x', '1m junk'):
            with self.assertRaises(ValueError):
                parse_tiles(text)

    def test_low_end_of_123_is_ryanmen(self):
        result = evaluate_shape(self.sequences, 16, 0, Context(0))
        self.assertIn('pinfu', result.yaku)
        self.assertEqual(result.fu, 30)

    def test_high_end_of_123_is_penchan(self):
        result = evaluate_shape(self.sequences, 16, 0, Context(2, riichi=1))
        self.assertNotIn('pinfu', result.yaku)
        self.assertEqual(result.fu, 40)

    def test_high_end_of_789_is_ryanmen(self):
        result = evaluate_shape(self.sequences, 16, 2, Context(26))
        self.assertIn('pinfu', result.yaku)

    def test_low_end_of_789_is_penchan(self):
        result = evaluate_shape(self.sequences, 16, 2, Context(24, riichi=1))
        self.assertNotIn('pinfu', result.yaku)

    def test_middle_tile_is_kanchan(self):
        result = evaluate_shape(self.sequences, 16, 0, Context(1, riichi=1))
        self.assertNotIn('pinfu', result.yaku)

    def test_nonvalue_honor_pair_can_be_pinfu(self):
        result = evaluate_shape(self.sequences, 30, 0, Context(0, seat=27, round_wind=28))
        self.assertIn('pinfu', result.yaku)

    def test_value_pair_prevents_pinfu(self):
        result = evaluate_shape(self.sequences, 27, 0, Context(0, riichi=1))
        self.assertNotIn('pinfu', result.yaku)

    def test_tanki_winning_pair_does_not_borrow_a_sequence(self):
        groups = (Group(0, True), Group(3, True), Group(9, True), Group(21, True))
        result = evaluate_shape(groups, 0, -1, Context(0, riichi=1))
        self.assertNotIn('pinfu', result.yaku)

    def test_pinfu_tsumo_is_twenty_fu(self):
        result = evaluate_shape(self.sequences, 16, 0, Context(0, tsumo=True))
        self.assertEqual(result.fu, 20)
        self.assertEqual(result.yaku, ('menzen_tsumo', 'pinfu'))

    def test_open_ittsuu_reduction(self):
        groups = (Group(0, True, True), Group(3, True), Group(6, True), Group(9, True))
        result = evaluate_shape(groups, 13, 1, Context(3))
        self.assertEqual(result.yaku, ('ittsuu',))
        self.assertEqual(result.han, 1)

    def test_ryanpeikou_suppresses_iipeikou(self):
        groups = (Group(0, True), Group(0, True), Group(12, True), Group(12, True))
        result = evaluate_shape(groups, 25, 0, Context(0))
        self.assertIn('ryanpeikou', result.yaku)
        self.assertNotIn('iipeikou', result.yaku)

    def test_seven_pairs_loses_to_ten_han_standard_interpretation(self):
        result = score_request({'hand': '1122334455667m', 'win': '7m'})
        self.assertEqual(result['results'][0]['han'], 10)
        self.assertEqual({item['slug'] for item in result['results'][0]['yaku']}, {'ryanpeikou', 'chinitsu', 'pinfu'})

    def test_chiitoitsu_has_seven_different_pairs_and_fixed_fu(self):
        result = score_request({'hand': '11m 22m 33p 44p 55s 66s 7z', 'win': '7z'})
        self.assertEqual(result['results'][0]['fu'], 25)
        self.assertEqual(result['results'][0]['kind'], 'chiitoitsu')

    def test_four_of_a_tile_is_not_two_chiitoi_pairs(self):
        result = score_request({'hand': '1111m 22p 44p 66s 88s 5z', 'win': '5z'})
        self.assertFalse(result['legal_win'])

    def test_shousangen_automatically_adds_two_dragon_yaku(self):
        groups = (Group(31), Group(32), Group(0, True), Group(12, True))
        result = evaluate_shape(groups, 33, 2, Context(0))
        self.assertEqual(set(result.yaku), {'haku', 'hatsu', 'shousangen'})
        self.assertEqual(result.han, 4)

    def test_double_wind_adds_two_yaku(self):
        groups = (Group(27), Group(0, True), Group(12, True), Group(21, True))
        result = evaluate_shape(groups, 16, 1, Context(0))
        self.assertEqual(set(result.yaku), {'seat_wind', 'round_wind'})

    def test_ron_completed_triplet_is_not_concealed(self):
        groups = (Group(0), Group(10), Group(20), Group(12))
        result = evaluate_shape(groups, 33, 3, Context(12))
        self.assertFalse(result.yakuman)
        self.assertEqual(set(result.yaku), {'toitoi', 'sanankou'})

    def test_four_concealed_triplets_tsumo_is_natural(self):
        groups = (Group(0), Group(10), Group(20), Group(12))
        result = evaluate_shape(groups, 33, 3, Context(12, tsumo=True))
        self.assertEqual(result.yaku, ())
        self.assertIn('suuankou', result.yakuman)

    def test_four_concealed_triplets_tanki_is_double(self):
        groups = (Group(0), Group(10), Group(20), Group(12))
        result = evaluate_shape(groups, 33, -1, Context(33))
        self.assertEqual(result.yakuman_multiple, 2)

    def test_three_ankans_keep_menzen_and_count_sankantsu(self):
        groups = (Group(0, kan=True), Group(10, kan=True), Group(20, kan=True), Group(21, True))
        context = Context(21, tsumo=True, event='rinshan')
        hand, melds = before_win(groups, 13, context)
        result = score_hand(hand, context, melds)[0]
        self.assertTrue(result.closed)
        self.assertEqual(set(result.yaku), {'sankantsu', 'sanankou', 'rinshan', 'menzen_tsumo'})

    def test_three_terminal_ankans_can_exceed_110_fu(self):
        groups = (Group(0, kan=True), Group(8, kan=True), Group(9, kan=True), Group(17))
        result = evaluate_shape(groups, 31, 3, Context(17))
        self.assertEqual(result.fu, 140)
        self.assertFalse(result.yakuman)

    def test_daisangen_suppresses_ordinary_yaku(self):
        result = evaluate_shape((Group(31), Group(32), Group(33), Group(0, True)), 16, 3, Context(0, riichi=1))
        self.assertEqual(result.yaku, ())
        self.assertEqual(result.yakuman, ('daisangen',))

    def test_natural_yakuman_stack(self):
        result = evaluate_shape((Group(31), Group(32), Group(33), Group(27)), 28, -1, Context(28))
        self.assertEqual(result.yakuman_multiple, 4)  # daisangen + all honors + suuankou tanki

    def test_green_and_non_green_color_are_not_blindly_identified(self):
        green = (Group(19, True), Group(19, True), Group(23), Group(25))
        self.assertIn('ryuuiisou', evaluate_shape(green, 32, 0, Context(19)).yakuman)
        other = tuple(Group(group.tile - 18, group.sequence) for group in green)
        self.assertFalse(evaluate_shape(other, 32, 0, Context(1)).yakuman)

    def test_nine_gates_and_pure_nine_gates(self):
        pure = score_request({'hand': '1112345678999m', 'win': '5m'})
        self.assertIn('junsei_chuuren', [item['slug'] for item in pure['results'][0]['yakuman']])
        ordinary = score_request({'hand': '1123455678999m', 'win': '1m'})
        self.assertIn('chuuren', [item['slug'] for item in ordinary['results'][0]['yakuman']])

    def test_kokushi_thirteen_wait(self):
        result = score_request({'hand': '19m 19p 19s 1234567z', 'win': '1m'})
        self.assertEqual(result['results'][0]['yakuman'][0]['multiple'], 2)

    def test_chankan_needs_opponent_three_copies(self):
        with self.assertRaises(ValueError):
            score_request({'hand': '11m 22m 33p 44p 55s 66s 7z', 'win': '7z', 'event': 'chankan'})

    def test_no_yaku_cannot_win_with_only_dora(self):
        groups = (Group(0, True), Group(12, True), Group(24, True), Group(10))
        context = Context(2, dora=10)
        hand, melds = before_win(groups, 22, context)
        self.assertEqual(score_hand(hand, context, melds), ())

    def test_explicit_dora_changes_payment_but_not_yaku_set(self):
        request = {'hand': '11m 22m 33p 44p 55s 66s 7z', 'win': '7z', 'dora': 11}
        result = score_request(request)['results'][0]
        self.assertEqual(result['han'], 2)
        self.assertEqual(result['total_han'], 13)
        self.assertEqual(result['base_points'], 8000)
        self.assertEqual([item['slug'] for item in result['yaku']], ['chiitoitsu'])

    def test_wrong_before_win_length_is_rejected(self):
        with self.assertRaises(ValueError):
            score_request({'hand': '123m123p123s456s88p', 'win': '1m'})

    def test_five_physical_copies_are_rejected(self):
        with self.assertRaises(ValueError):
            score_request({'hand': '1111m234p567s777p', 'win': '1m'})

    def test_fixed_melds_cannot_be_repartitioned(self):
        result = score_request({'hand': '123m 456p 789s 7z', 'win': '7z', 'melds': [{'kind': 'pon', 'tiles': '555p'}]})
        self.assertFalse(result['legal_win'])

    def test_cumulative_yakuman_is_single_even_at_twenty_six_han(self):
        self.assertEqual(base_points(25, 13), 8000)
        self.assertEqual(base_points(25, 26), 8000)
        self.assertEqual(base_points(30, 4), 1920)

    def test_natural_yakuman_dominates_alternate_counted_yakuman(self):
        result = score_request({'hand': '1112223334445m', 'win': '5m', 'tsumo': True, 'dora': 20})
        self.assertTrue(all(item['yakuman'] for item in result['results']))
        self.assertTrue(all(not item['yaku'] for item in result['results']))

    def test_double_riichi_chankan_is_not_banned_without_ippatsu(self):
        result = score_request({'hand': '12m 123p 123s 456s 77p', 'win': '3m', 'riichi': 2, 'event': 'chankan'})
        names = {item['slug'] for item in result['results'][0]['yaku']}
        self.assertTrue({'double_riichi', 'chankan'} <= names)

    def test_invalid_condition_flags_raise(self):
        for kwargs in ({'ippatsu': True}, {'event': 'haitei'}, {'event': 'chankan', 'tsumo': True}, {'event': 'rinshan', 'tsumo': True, 'riichi': 1, 'ippatsu': True}, {'event': 'haitei', 'tsumo': True, 'riichi': 2, 'ippatsu': True}):
            with self.assertRaises(ValueError):
                Context(0, **kwargs)

    def test_first_turn_yakuman_is_distinct_from_double_riichi(self):
        hand, melds = before_win(self.sequences, 16, Context(0, tsumo=True))
        result = score_hand(hand, Context(0, tsumo=True, first_turn=True), melds)[0]
        self.assertIn('tenhou', result.yakuman)

    def test_waits_ignore_yaku(self):
        self.assertEqual(waits(parse_tiles('11m 22m 33p 44p 55s 66s 7z')), frozenset({33}))


if __name__ == '__main__':
    unittest.main()
