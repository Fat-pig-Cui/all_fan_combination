#!/usr/bin/env python3
"""Recalculate every saved witness without depending on solver internals."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from calc_fan import BIT, ORDER, YAKU, context_from_dict, parse_meld, parse_tiles, score_hand
from reachability import condition_certificate


def audit(directory: Path):
    seen = set()
    histogram = {True: Counter(), False: Counter()}
    total = 0
    for number, line in enumerate((directory / 'combinations.jsonl').read_text().splitlines(), 1):
        record = json.loads(line)
        context = context_from_dict(record['witness'])
        hand = parse_tiles(record['witness']['hand'])
        melds = tuple(parse_meld(meld) for meld in record['witness']['melds'])
        mask = sum(BIT[name] for name in record['yaku'])
        key = (record['closed'], mask)
        if key in seen or mask != record['mask'] or not mask:
            raise ValueError(f'line {number}: duplicate, invalid mask, or empty yaku')
        if record['yaku'] != [name for name in ORDER if name in record['yaku']] or record['yaku_ids'] != [YAKU[name][0] for name in record['yaku']]:
            raise ValueError(f'line {number}: catalog/order mismatch')
        selected = score_hand(hand, context, melds)
        if not any(not score.yakuman and score.mask == mask and score.han == record['han'] and score.fu == record['witness_fu'] and score.closed == record['closed'] for score in selected):
            raise ValueError(f'line {number}: witness does not produce recorded selected score')
        if condition_certificate(SimpleNamespace(hand=hand, melds=melds, context=context)) is None:
            raise ValueError(f'line {number}: illegal post-riichi kan')
        seen.add(key)
        histogram[key[0]][record['han']] += 1
        total += 1
    summary = json.loads((directory / 'summary.json').read_text())
    if total != summary['combination_count']:
        raise ValueError('Summary count mismatch')
    for closed, label in ((True, 'closed'), (False, 'open')):
        actual = {str(han): count for han, count in sorted(histogram[closed].items())}
        if summary[label]['han_histogram'] != actual or summary[label]['count'] != sum(actual.values()):
            raise ValueError('Summary histogram mismatch: ' + label)
    return {'witnesses_checked': total, 'unique': True, 'all_witnesses_recalculated': True,
            'enumeration_complete': summary['complete'], 'termination': summary['termination']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
