"""Constructive condition-yaku reachability, with exact riichi-kan waits.

Only existence matters: prepare calls/kans before ordinary riichi; hold a
first-discard tenpai hand for double riichi; defer the winning tile to the
required draw/discard/kakan.  Post-riichi kans need an explicit wait proof.
"""
from __future__ import annotations

from itertools import permutations

from calc_fan import Group, compact_tiles, tile_name, waits, validate_inventory


def condition_certificate(witness):
    context = witness.context
    try:
        validate_inventory(witness.hand + (context.win,) + tuple(t for g in witness.melds for t in g.tiles),
                           witness.melds, context)
    except ValueError:
        return None
    closed_kans = tuple(group for group in witness.melds if group.kan and not group.open)
    certificate = {
        'method': 'tsumo' if context.tsumo else 'ron',
        'event': context.event,
        'riichi': context.riichi,
        'ippatsu': context.ippatsu,
        'players': context.players,
        'rules_fingerprint': context.rules.fingerprint,
        'riichi_min_live_tiles': context.rules.riichi_min_live_tiles,
        'north_count': context.north_count,
        'replacement_source': ('north' if context.win_source == 'north_replacement'
                               else 'kan' if context.event == 'rinshan' else None),
        'construction': [],
    }
    if context.north_count:
        if context.win_source == 'north_replacement':
            current = waits(tuple(sorted(witness.hand)), witness.melds, context.players)
            if context.win not in current:
                return None
            certificate['north_extraction'] = {
                'draw': '4z', 'uses_just_drawn_tile': True,
                'concealed_hand_unchanged': True,
                'waits_before': [tile_name(t) for t in sorted(current)],
                'waits_after': [tile_name(t) for t in sorted(current)],
                'live_tiles_before_extraction': context.live_tiles if context.live_tiles is not None else 2,
                'response_before_replacement': True,
                'ippatsu_interrupted': True,
            }
            certificate['construction'].append('Draw a fresh north, offer the extraction response, then complete nuki and win its replacement. The 13-tile hand is unchanged; no ippatsu or haitei is counted.')
        else:
            certificate['construction'].append('Place earlier north extractions before ordinary riichi; for double riichi they follow declaration and interrupt ippatsu.')
    if context.win_source == 'north_ron':
        certificate['construction'].append('Win on the opponent north declaration before its replacement; north ron provides no chankan yaku. Choose discards outside the structural wait set to avoid furiten.')
    if context.riichi == 2 and context.ippatsu and (closed_kans or context.north_count):
        return None
    if context.kanburi:
        if context.tsumo or context.event != 'none' or context.ippatsu or sum(g.kan for g in witness.melds) >= 4:
            return None
        certificate['construction'].append('Opponent declares a kan using a tile absent from our hand, then discards a harmless replacement tile completing our wait; the kan interrupts ippatsu. At most four total kans exist. Ron precedes any four-kan abort.')
    if context.tsubame:
        if context.tsumo or context.event != 'none':
            return None
        certificate['construction'].append('Opponent declares ordinary riichi on the winning discard, with at least four live tiles remaining; if kanburi also holds, this follows an ankan and replacement on that same first-discard turn. The winning player has already drawn before and is not renhou.')
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
            if not context.rules.ippatsu_haitei_possible:
                return None
            certificate['last_cycle'] = {'live_tiles_at_riichi': context.players,
                                         'opponent_draws': context.players - 1,
                                         'declarer_draw_is_last': True,
                                         'calls_kans_nuki': 0}
            certificate['construction'].append(f'Ordinary riichi leaves {context.players} live tiles: {context.players - 1} opponents draw, then declarer wins the final normal draw within ippatsu.')
    if context.event == 'houtei':
        certificate['construction'].append('An opponent discards the final normal draw; winner has no ippatsu flag.')
    if context.riichi == 2 and closed_kans:
        # Every ankan must follow the first-discard declaration.  Find an
        # order of drawing each fourth copy which preserves ALL waits.
        for order in permutations(closed_kans):
            remaining = list(order)
            fixed = []
            initial = tuple(sorted(witness.hand + tuple(group.tile for group in remaining for _ in range(3))))
            before = waits(initial, (), context.players)
            if context.win not in before:
                continue
            proof = []
            for group in order:
                remaining.remove(group)
                fixed.append(group)
                after_hand = tuple(sorted(witness.hand + tuple(other.tile for other in remaining for _ in range(3))))
                after = waits(after_hand, tuple(fixed), context.players)
                if before != after:
                    break
                proof.append({'draw_fourth': tile_name(group.tile), 'waits': [tile_name(tile) for tile in sorted(after)]})
            else:
                certificate['initial_tenpai'] = compact_tiles(initial)
                certificate['post_riichi_kans'] = proof
                certificate['construction'].append('Declare on first discard; draw the fourth copy for each ankan in the recorded order, discarding harmless replacement draws until the winning event.')
                return certificate
        return None
    if context.riichi == 1 and context.event == 'rinshan' and context.win_source != 'north_replacement':
        # Other kans can precede ordinary riichi.  The final ankan must be
        # triggered by a newly drawn fourth copy and preserve the wait set.
        after = waits(tuple(sorted(witness.hand)), witness.melds, context.players)
        for last in closed_kans:
            previous = list(witness.melds)
            previous.remove(last)
            before_hand = tuple(sorted(witness.hand + (last.tile,) * 3))
            before = waits(before_hand, tuple(previous), context.players)
            if context.win in before and before == after:
                certificate['initial_tenpai'] = compact_tiles(before_hand)
                certificate['post_riichi_kans'] = [{'draw_fourth': tile_name(last.tile), 'waits': [tile_name(tile) for tile in sorted(after)]}]
                certificate['construction'].append('Earlier ankans precede ordinary riichi; draw the recorded fourth copy, declare the final ankan and win its replacement draw.')
                return certificate
        return None
    if context.riichi:
        certificate['construction'].append('Declare with this tenpai hand; any own kans precede ordinary riichi, or no kans exist for first-discard ippatsu.')
    if context.event == 'rinshan' and context.win_source != 'north_replacement':
        certificate['construction'].append('Complete a recorded kan immediately before the winning replacement draw; no ippatsu survives that kan.')
    if not certificate['construction']:
        certificate['construction'].append('Arrange a non-first-turn winning draw/discard after the declared melds; avoid furiten by discarding outside the wait set.')
    return certificate
