#!/usr/bin/env python3
"""Optional offline parity check against the supplied local calcFan.js.

Only the calculator reference is executed in an isolated Node VM; no client,
server, browser, account or game replay is involved.  The Python calculator
and enumerator do not import this helper.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from calc_fan import score_request


NATURAL_IDS = {
    'tenhou': 35, 'chiihou': 36, 'daisangen': 37, 'suuankou': 38,
    'tsuuiisou': 39, 'ryuuiisou': 40, 'chinroutou': 41, 'kokushi': 42,
    'shousuushii': 43, 'suukantsu': 44, 'chuuren': 45,
    'junsei_chuuren': 47, 'suuankou_tanki': 48, 'kokushi_13': 49, 'daisuushii': 50,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True,
                        help='Directory containing the separately obtained calcFan.js, constants.js and utils.js')
    parser.add_argument('--cases', type=Path, default=ROOT / 'examples/reference_cases.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/local-reference-check.json')
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    reference = subprocess.run(['node', str(ROOT / 'tools/reference_runner.mjs'), str(args.core), str(args.cases)],
                               capture_output=True, text=True, check=True)
    native = json.loads(reference.stdout)
    mismatches = []
    expected_rejections = []
    for index, (case, js) in enumerate(zip(cases, native)):
        reference_fans = sorted((fan['id'], fan['val']) for fan in js['fans'] if fan['val'])
        python = score_request(case)
        if case.get('expected_legal_win') is False:
            if python['legal_win']:
                mismatches.append({'index': index, 'input': case, 'python': python,
                                   'reason': 'An explicitly invalid scenario was accepted'})
            else:
                expected_rejections.append({'index': index, 'reason': case.get('reason', 'invalid scenario'),
                                            'reference_scores_ignored': True})
            continue
        matches = False
        for score in python['results']:
            if js['yiman']:
                fans = sorted((NATURAL_IDS[fan['slug']], fan['multiple']) for fan in score['yakuman'])
                match = bool(score['yakuman']) and fans == reference_fans
            else:
                fans = sorted((fan['id'], fan['han']) for fan in score['yaku'])
                match = not score['yakuman'] and fans == reference_fans and score['fu'] == js['fu']
            matches |= match
        if not matches:
            mismatches.append({'index': index, 'input': case, 'reference': js, 'python': python})
    if len(native) != len(cases):
        raise ValueError('Reference did not return every case')
    payload = {
        'mode': 'offline local calculator comparison', 'cases_checked': len(cases),
        'passed': not mismatches, 'mismatches': mismatches,
        'expected_rejections': expected_rejections,
        'scoring_cases_compared': sum(case.get('expected_legal_win') is not False for case in cases),
        'normalization': 'ignore zero-valued ura and yakuman fu; compare ordinary IDs/han/fu and natural IDs/multiples',
        'reference_sha256': {name: hashlib.sha256((args.core / name).read_bytes()).hexdigest() for name in ('calcFan.js', 'constants.js', 'utils.js')},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not mismatches else 1


if __name__ == '__main__':
    raise SystemExit(main())
