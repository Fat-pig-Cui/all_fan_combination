#!/usr/bin/env python3
"""Enumerate distinct four-player ordinary-yaku sets by structural witnesses.

Z3 proposes complete winning structures.  calc_fan.py independently checks
all decompositions and score selection; reachability.py proves the relevant
post-riichi kan wait invariants.  Only a validated set is projected/blocked.
An UNSAT result establishes exhaustion under the documented finite model;
a limit, timeout, or interruption is explicitly an incomplete enumeration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from collections import Counter
from pathlib import Path

import z3

from calc_fan import BIT, ORDER, YAKU, compact_tiles, score_hand, tile_name
from reachability import condition_certificate
from shape_solver import ShapeSolver


def source_hashes():
    root = Path(__file__).resolve().parent
    names = ('calc_fan.py', 'shape_solver.py', 'reachability.py', 'enumerate_combinations.py')
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def scenario(witness):
    context = witness.context
    return {
        'hand': compact_tiles(witness.hand), 'win': tile_name(context.win),
        'melds': [group.to_dict() for group in witness.melds],
        'tsumo': context.tsumo, 'seat': tile_name(context.seat), 'round_wind': tile_name(context.round_wind),
        'riichi': context.riichi, 'ippatsu': context.ippatsu, 'event': context.event,
    }


def combination_record(witness, score, certificate):
    return {
        'closed': score.closed, 'mask': score.mask,
        'yaku': list(score.yaku), 'yaku_ids': [YAKU[name][0] for name in score.yaku],
        'han': score.han, 'witness_fu': score.fu,
        'witness': scenario(witness),
        'selected_interpretation': score.to_dict(),
        'condition_certificate': certificate,
    }


def summary_for(records, *, complete, reason, models, rejected, elapsed, hashes):
    result = {
        'schema_version': 1,
        'scope': {'players': 4, 'ranked': True, 'natural_yakuman': False, 'dora_in_combinations': False,
                  'dora_for_partition_selection': 0, 'include_ordinary_han_13_plus': True,
                  'round_winds': ['1z', '2z', '3z'], 'riichi_min_live_tiles': 4,
                  'selection': 'maximum(base_points, raw_han, fu); retain exact ties'},
        'complete': complete, 'termination': reason,
        'combination_count': len(records), 'models_checked': models,
        'rejected_models': rejected, 'elapsed_seconds': round(elapsed, 3),
        'source_sha256': hashes, 'python_version': platform.python_version(), 'z3_version': z3.get_version_string(),
    }
    for label, closed in (('closed', True), ('open', False)):
        subset = [record for record in records if record['closed'] == closed]
        hist = Counter(record['han'] for record in subset)
        result[label] = {'count': len(subset), 'han_histogram': dict(sorted(hist.items()))}
    return result


def write_summary(directory, payload):
    temporary = directory / 'summary.json.tmp'
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(directory / 'summary.json')


def enumerate_sets(directory: Path, *, limit=0, max_models=0, timeout_ms=0, resume=False, seed=0, log_every=100):
    directory.mkdir(parents=True, exist_ok=True)
    records_path = directory / 'combinations.jsonl'
    hashes = source_hashes()
    records = []
    if records_path.exists():
        if not resume:
            raise ValueError('Output exists; use --resume or choose a fresh --output directory')
        for line in records_path.read_text().splitlines():
            if line.strip():
                records.append(json.loads(line))
        previous_path = directory / 'summary.json'
        if previous_path.exists():
            previous = json.loads(previous_path.read_text())
            if previous.get('source_sha256') != hashes:
                raise ValueError('Source changed since this result; choose a fresh output directory')
            if previous.get('complete'):
                return previous
    solver = ShapeSolver(timeout_ms=timeout_ms, seed=seed)
    seen = set()
    for record in records:
        key = (record['closed'], record['mask'])
        if key in seen:
            raise ValueError('Duplicate combination in resume file')
        seen.add(key)
        solver.block_projection(*key)
    start = time.monotonic()
    models = rejected = 0
    complete = False
    reason = 'running'
    def checkpoint():
        payload = summary_for(records, complete=complete, reason=reason, models=models,
                              rejected=rejected, elapsed=time.monotonic() - start, hashes=hashes)
        write_summary(directory, payload)
        return payload
    checkpoint()
    try:
        with records_path.open('a') as output, (directory / 'rejections.jsonl').open('a') as rejected_output:
            while True:
                if limit and len(records) >= limit:
                    reason = 'combination_limit'
                    break
                if max_models and models >= max_models:
                    reason = 'model_limit'
                    break
                status = solver.check()
                if status == z3.unsat:
                    complete, reason = True, 'unsat'
                    break
                if status == z3.unknown:
                    reason = 'unknown: ' + solver.solver.reason_unknown()
                    break
                model = solver.solver.model()
                witness = solver.decode(model)
                models += 1
                certificate = condition_certificate(witness)
                scores = score_hand(witness.hand, witness.context, witness.melds)
                matching = [score for score in scores if not score.yakuman and score.closed == witness.closed and score.mask == witness.mask]
                if certificate is None or not matching:
                    rejected += 1
                    rejected_output.write(json.dumps({
                        'reason': 'post_riichi_kan_changes_waits' if certificate is None else 'not_score_selected',
                        'target_yaku': [name for i, name in enumerate(ORDER) if witness.mask & (1 << i)],
                        'witness': scenario(witness), 'actual': [score.to_dict() for score in scores],
                    }, ensure_ascii=False) + '\n')
                    solver.block_rejected_hand(witness)
                else:
                    score = matching[0]
                    record = combination_record(witness, score, certificate)
                    records.append(record)
                    seen.add((record['closed'], record['mask']))
                    output.write(json.dumps(record, ensure_ascii=False) + '\n')
                    output.flush()
                    solver.block_projection(record['closed'], record['mask'])
                if models % log_every == 0:
                    payload = checkpoint()
                    print(f"models={models} sets={len(records)} closed={payload['closed']['count']} open={payload['open']['count']} rejected={rejected} elapsed={time.monotonic() - start:.1f}s", file=sys.stderr, flush=True)
    except KeyboardInterrupt:
        reason = 'interrupted'
    finally:
        payload = checkpoint()
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('results/full'))
    parser.add_argument('--limit', type=int, default=0, help='accepted-set limit; 0 means no limit')
    parser.add_argument('--max-models', type=int, default=0, help='diagnostic model limit; 0 means no limit')
    parser.add_argument('--timeout-ms', type=int, default=0, help='per solver check; 0 means no timeout')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--log-every', type=int, default=100)
    args = parser.parse_args()
    if min(args.limit, args.max_models, args.timeout_ms) < 0 or args.log_every < 1:
        parser.error('Limits must be nonnegative; log interval must be positive')
    try:
        payload = enumerate_sets(args.output, limit=args.limit, max_models=args.max_models,
                                 timeout_ms=args.timeout_ms, resume=args.resume,
                                 seed=args.seed, log_every=args.log_every)
    except ValueError as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload['complete'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
