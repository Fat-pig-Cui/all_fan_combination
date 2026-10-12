#!/usr/bin/env python3
"""Recalculate the published natural-yakuman witness projections."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from calc_fan import Context, YAKUMAN, one_tile, parse_meld, parse_tiles, score_hand


def verify(directory: Path = ROOT / 'results/yakuman'):
    payload = json.loads((directory / 'summary.json').read_text(encoding='utf-8'))
    if payload.get('schema_version') != 1:
        raise ValueError('Unsupported natural-yakuman schema')
    checked = 0
    seen = set()
    expected_records = []
    for profile_name, profile in payload['profiles'].items():
        players = int(profile_name)
        if players not in (3, 4) or profile['players'] != players:
            raise ValueError('invalid natural-yakuman profile')
        catalog = {name: {'name': label, 'multiple': multiple}
                   for name, (label, multiple) in YAKUMAN.items()}
        if profile['yakuman_catalog'] != catalog:
            raise ValueError('natural-yakuman catalog mismatch')
        combinations = profile['combinations']
        if len(combinations) != profile['combination_count']:
            raise ValueError(f'{players}-player combination count mismatch')
        multiples = Counter()
        for item in combinations:
            names = tuple(item['yakuman'])
            if names != tuple(sorted(set(names))):
                raise ValueError('natural-yakuman names must be sorted and unique')
            key = (players, names)
            if key in seen:
                raise ValueError(f'duplicate natural-yakuman projection: {key}')
            seen.add(key)
            witness = item['witness']
            if witness['players'] != players:
                raise ValueError('witness player count mismatch')
            hand = parse_tiles(witness['hand'])
            win = one_tile(witness['win'])
            melds = tuple(parse_meld(meld) for meld in witness.get('melds', ()))
            context = Context(win=win, tsumo=witness['tsumo'], seat=one_tile(witness['seat']),
                              round_wind=27, first_turn=witness['first_turn'], players=players)
            scores = score_hand(hand, context, melds)
            projections = {tuple(sorted(score.yakuman)) for score in scores if score.yakuman}
            if names not in projections:
                raise ValueError(f'witness does not reproduce {names}: {witness}')
            multiple = sum(YAKUMAN[name][1] for name in names)
            if multiple != item['multiple']:
                raise ValueError(f'multiple mismatch for {names}')
            multiples[str(multiple)] += 1
            expected_records.append({'players': players, **item})
            checked += 1
        if dict(multiples) != profile['multipliers']:
            raise ValueError('natural-yakuman multiplier distribution mismatch')
    records = [json.loads(line) for line in (directory / 'witnesses.jsonl').read_text(encoding='utf-8').splitlines()
               if line.strip()]
    record_key = lambda item: (item['players'], tuple(item['yakuman']))
    if sorted(records, key=record_key) != sorted(expected_records, key=record_key):
        raise ValueError('natural-yakuman witness export mismatch')
    return {'profiles': {name: profile['combination_count'] for name, profile in payload['profiles'].items()},
            'witnesses_checked': checked, 'unique_projections': len(seen)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path, default=ROOT / 'results/yakuman')
    args = parser.parse_args()
    print(json.dumps(verify(args.directory), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
