#!/usr/bin/env python3
"""Score existing tile witnesses under sanma, then solve every remaining set.

The four-player archive supplies optional search hints, never combination
counts or an exclusion list. Each hint is scored and certified under sanma;
the three-player solver must return UNSAT before the run is complete.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
from itertools import permutations
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import z3
from calc_fan import BIT, ORDER, Group, context_from_dict, parse_meld, parse_tiles, score_hand
from enumerate_combinations import combination_record, scenario, source_hashes, summary_for, write_summary
from reachability import condition_certificate
from result_records import iter_record_lines, verify_archive
from shape_solver import ShapeSolver


def enumerate_sanma(source, output, *, limit=0, timeout_ms=0, log_every=100):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a new output directory; source snapshots are read-only')
    source_bytes = (source / 'summary.json').read_bytes()
    source_summary = json.loads(source_bytes)
    if source_summary['scope']['players'] != 4:
        raise ValueError('Seed snapshot must be four-player')
    if (source / 'records.zip').exists():
        verify_archive(source)
    output.mkdir(parents=True)
    solver = ShapeSolver(players=3, timeout_ms=timeout_ms)
    records, seen, seed_states = [], set(), set()
    hashes = source_hashes()
    hashes['tools/enumerate_sanma.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    start = time.monotonic()
    complete, reason, models, rejected = False, 'running', 0, 0
    proof = {'method': 'rescore_permuted_tile_hints_then_exhaust_sanma_constraints',
             'source_summary_sha256': hashlib.sha256(source_bytes).hexdigest(),
             'source_archive_sha256': hashlib.sha256((source / 'records.zip').read_bytes()).hexdigest()
                 if (source / 'records.zip').exists() else None,
             'source_records_read': 0, 'unique_seed_states_checked': 0,
             'invalid_seed_states': 0, 'sets_confirmed_from_hints': 0,
             'additional_solver_models': 0, 'additional_solver_sets': 0}

    def checkpoint():
        payload = summary_for(records, complete=complete, reason=reason, models=models,
                              rejected=rejected, elapsed=time.monotonic() - start, hashes=hashes, players=3)
        payload['search_hints'] = dict(proof)
        write_summary(output, payload)
        return payload

    checkpoint()
    try:
        with (output / 'combinations.jsonl').open('w', encoding='utf-8') as accepted_output, \
                (output / 'rejections.jsonl').open('w', encoding='utf-8') as rejected_output:
            def accept(witness, score, certificate):
                key = score.closed, score.mask
                if key in seen:
                    return False
                seen.add(key)
                records.append(combination_record(witness, score, certificate))
                accepted_output.write(json.dumps(records[-1], ensure_ascii=False) + '\n')
                solver.block_projection(*key)
                return True

            for name in ('combinations.jsonl', 'rejections.jsonl'):
                for line in iter_record_lines(source, name):
                    raw = json.loads(line)['witness']
                    proof['source_records_read'] += 1
                    hand = parse_tiles(raw['hand'])
                    melds = tuple(parse_meld(item) for item in raw['melds'])
                    if any(g.open and g.sequence for g in melds):
                        continue
                    original = context_from_dict(raw)
                    for suits in permutations(range(3)):
                        def tile_map(t):
                            return t if t >= 27 else suits[t // 9] * 9 + t % 9
                        mapped_hand = tuple(sorted(tile_map(t) for t in hand))
                        mapped_melds = tuple(sorted(Group(tile_map(g.tile), g.sequence, g.open, g.kan) for g in melds))
                        physical = mapped_hand + (tile_map(original.win),) + tuple(t for g in mapped_melds for t in g.tiles)
                        if any(t in range(1, 8) for t in physical):
                            continue
                        context = replace(original, players=3, win=tile_map(original.win), seat=min(original.seat, 29))
                        variants = [context]
                        if Counter(physical)[30] < 4:
                            variants.append(replace(context, tsumo=True, event='rinshan', ippatsu=False,
                                                    north_count=1, win_source='north_replacement'))
                        for candidate in variants:
                            state = mapped_hand, mapped_melds, candidate
                            if state in seed_states:
                                continue
                            seed_states.add(state)
                            models += 1
                            proof['unique_seed_states_checked'] += 1
                            witness = SimpleNamespace(hand=mapped_hand, melds=mapped_melds, context=candidate)
                            try:
                                scores = score_hand(mapped_hand, candidate, mapped_melds)
                                certificate = condition_certificate(witness)
                            except ValueError:
                                scores, certificate = (), None
                            if not certificate or not scores:
                                proof['invalid_seed_states'] += 1
                                continue
                            for score in scores:
                                if score.yaku and not score.yakuman and accept(witness, score, certificate):
                                    proof['sets_confirmed_from_hints'] += 1
                            if limit and len(records) >= limit:
                                reason = 'combination_limit'
                                return checkpoint()
                    if proof['source_records_read'] % 2000 == 0:
                        accepted_output.flush()
                        checkpoint()
                        print(f"seed_records={proof['source_records_read']} checked={models} sets={len(records)}", file=sys.stderr, flush=True)
            accepted_output.flush()
            checkpoint()
            print(f"Hints confirmed {len(records)} sets; solving remaining sanma constraints.", file=sys.stderr, flush=True)
            while True:
                status = solver.check()
                if status == z3.unsat:
                    complete, reason = True, 'unsat'
                    break
                if status == z3.unknown:
                    reason = 'unknown: ' + solver.solver.reason_unknown()
                    break
                witness = solver.decode()
                models += 1
                proof['additional_solver_models'] += 1
                scores = score_hand(witness.hand, witness.context, witness.melds)
                certificate = condition_certificate(witness)
                matching = [s for s in scores if not s.yakuman and s.mask == witness.mask and s.closed == witness.closed]
                if not matching or certificate is None:
                    rejected += 1
                    rejected_output.write(json.dumps({
                        'reason': 'unreachable_conditions' if certificate is None else 'not_score_selected',
                        'target_yaku': [n for n in ORDER if witness.mask & BIT[n]],
                        'witness': scenario(witness), 'actual': [s.to_dict() for s in scores],
                    }, ensure_ascii=False) + '\n')
                    solver.block_rejected_hand(witness)
                elif accept(witness, matching[0], certificate):
                    proof['additional_solver_sets'] += 1
                if proof['additional_solver_models'] % log_every == 0:
                    accepted_output.flush()
                    checkpoint()
                    print(f"solver_models={proof['additional_solver_models']} sets={len(records)} rejected={rejected}", file=sys.stderr, flush=True)
                if limit and len(records) >= limit:
                    reason = 'combination_limit'
                    break
    except KeyboardInterrupt:
        reason = 'interrupted'
    except Exception:
        reason = 'error'
        raise
    finally:
        checkpoint()
    return checkpoint()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'results/full')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--timeout-ms', type=int, default=0)
    args = parser.parse_args()
    if min(args.limit, args.timeout_ms) < 0:
        parser.error('Limits must be nonnegative')
    try:
        result = enumerate_sanma(args.source, args.output, limit=args.limit, timeout_ms=args.timeout_ms)
    except (ValueError, OSError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['complete'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
