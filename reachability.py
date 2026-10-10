"""Constructive condition-yaku reachability, with exact riichi-kan waits.

Only existence matters: prepare calls/kans before ordinary riichi; hold a
first-discard tenpai hand for double riichi; defer the winning tile to the
required draw/discard/kakan.  Post-riichi kans need an explicit wait proof.
"""
from __future__ import annotations

from itertools import permutations

from calc_fan import Group, compact_tiles, tile_name, waits


def condition_certificate(witness):
    context = witness.context
    closed_kans = tuple(group for group in witness.melds if group.kan and not group.open)
    certificate = {
        'method': 'tsumo' if context.tsumo else 'ron',
        'event': context.event,
        'riichi': context.riichi,
        'ippatsu': context.ippatsu,
        'riichi_min_live_tiles': 4,
        'construction': [],
    }
    if context.riichi == 2 and context.ippatsu and closed_kans:
        return None
    if context.riichi == 2 and context.event == 'chankan':
        # This certificate covers ordinary yaku, not kokushi robbing ankan.
        # A post-declaration pon requires passing the winning discard;
        # permanent riichi furiten prevents robbing the later kakan.
        return None
    if context.event == 'chankan':
        certificate['construction'].append('Opponent keeps three copies of the winning tile in a pon; rob the remaining copy at kakan declaration.')
        if context.riichi:
            certificate['construction'].append('Opponent pon precedes ordinary riichi; kakan is robbed before completing and therefore before its kan interruption.')
    if context.event == 'haitei':
        certificate['construction'].append('Place winning tile at the final normal draw; any previous kans have already completed.')
        if context.ippatsu:
            certificate['construction'].append('Ordinary riichi leaves four live tiles: three opponents draw, then declarer wins the final normal draw within ippatsu.')
    if context.event == 'houtei':
        certificate['construction'].append('An opponent discards the final normal draw; winner has no ippatsu flag.')
    if context.riichi == 2 and closed_kans:
        # Every ankan must follow the first-discard declaration.  Find an
        # order of drawing each fourth copy which preserves ALL waits.
        for order in permutations(closed_kans):
            remaining = list(order)
            fixed = []
            initial = tuple(sorted(witness.hand + tuple(group.tile for group in remaining for _ in range(3))))
            before = waits(initial, ())
            if context.win not in before:
                continue
            proof = []
            for group in order:
                remaining.remove(group)
                fixed.append(group)
                after_hand = tuple(sorted(witness.hand + tuple(other.tile for other in remaining for _ in range(3))))
                after = waits(after_hand, tuple(fixed))
                if before != after:
                    break
                proof.append({'draw_fourth': tile_name(group.tile), 'waits': [tile_name(tile) for tile in sorted(after)]})
            else:
                certificate['initial_tenpai'] = compact_tiles(initial)
                certificate['post_riichi_kans'] = proof
                certificate['construction'].append('Declare on first discard; draw the fourth copy for each ankan in the recorded order, discarding harmless replacement draws until the winning event.')
                return certificate
        return None
    if context.riichi == 1 and context.event == 'rinshan':
        # Other kans can precede ordinary riichi.  The final ankan must be
        # triggered by a newly drawn fourth copy and preserve the wait set.
        after = waits(tuple(sorted(witness.hand)), witness.melds)
        for last in closed_kans:
            previous = list(witness.melds)
            previous.remove(last)
            before_hand = tuple(sorted(witness.hand + (last.tile,) * 3))
            before = waits(before_hand, tuple(previous))
            if context.win in before and before == after:
                certificate['initial_tenpai'] = compact_tiles(before_hand)
                certificate['post_riichi_kans'] = [{'draw_fourth': tile_name(last.tile), 'waits': [tile_name(tile) for tile in sorted(after)]}]
                certificate['construction'].append('Earlier ankans precede ordinary riichi; draw the recorded fourth copy, declare the final ankan and win its replacement draw.')
                return certificate
        return None
    if context.riichi:
        certificate['construction'].append('Declare with this tenpai hand; any own kans precede ordinary riichi, or no kans exist for first-discard ippatsu.')
    if context.event == 'rinshan':
        certificate['construction'].append('Complete a recorded kan immediately before the winning replacement draw; no ippatsu survives that kan.')
    if not certificate['construction']:
        certificate['construction'].append('Arrange a non-first-turn winning draw/discard after the declared melds; avoid furiten by discarding outside the wait set.')
    return certificate
