#!/usr/bin/env python3
"""Revalidate a previous snapshot, then exhaust the current model's remainder.

Previous accepted and rejected witnesses are hints, not trusted results.
Each is scored and certified again before its projection or concrete state
is blocked.  Completion still requires the current solver to return UNSAT.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import z3

from calc_fan import BIT, ORDER, context_from_dict, parse_meld, parse_tiles, score_hand
from enumerate_combinations import combination_record, scenario, source_hashes, summary_for, write_summary
from reachability import condition_certificate
from result_records import iter_record_lines
from shape_solver import ShapeSolver


def revalidate(source: Path, output: Path, *, timeout_ms=0, limit=0):
    source, output = source.resolve(), output.resolve()
    if source == output or output.exists():
        raise ValueError('Choose a new output directory; the source snapshot is read-only')
    old_summary = (source / 'summary.json').read_bytes()
    output.mkdir(parents=True)
    solver = ShapeSolver(timeout_ms=timeout_ms)
    records, seen = [], set()
    start = time.monotonic()
    hashes = source_hashes()
    proof = {'method': 'recalculate_seed_witnesses_then_solve_remaining_current_constraints',
             'source_summary_sha256': hashlib.sha256(old_summary).hexdigest(),
             'source_combination_count': json.loads(old_summary)['combination_count'],
             'source_combinations_rechecked': 0, 'source_rejections_rechecked': 0,
             'removed_source_combinations': 0, 'additional_solver_models': 0}
    complete, reason, models, rejected = False, 'running', 0, 0

    def checkpoint():
        summary = summary_for(records, complete=complete, reason=reason, models=models,
                              rejected=rejected, elapsed=time.monotonic() - start, hashes=hashes)
        summary['revalidation'] = dict(proof)
        write_summary(output, summary)
        return summary

    def prior_witness(record, accepted):
        data = record['witness']
        context = context_from_dict(data)
        melds = tuple(parse_meld(item) for item in data.get('melds', []))
        names = record['yaku'] if accepted else record['target_yaku']
        return SimpleNamespace(hand=parse_tiles(data['hand']), melds=melds, context=context,
                               closed=not any(group.open for group in melds),
                               mask=sum(BIT[name] for name in names))

    checkpoint()
    try:
        with (output / 'combinations.jsonl').open('w', encoding='utf-8') as accepted_output, \
                (output / 'rejections.jsonl').open('w', encoding='utf-8') as rejected_output:
            def inspect(witness):
                nonlocal models, rejected
                models += 1
                certificate = condition_certificate(witness)
                scores = score_hand(witness.hand, witness.context, witness.melds)
                matching = [score for score in scores if not score.yakuman
                            and score.closed == witness.closed and score.mask == witness.mask]
                if certificate is None or not matching:
                    rejected += 1
                    why = ('double_riichi_kakan_furiten'
                           if witness.context.riichi == 2 and witness.context.event == 'chankan'
                           else 'post_riichi_kan_changes_waits' if certificate is None else 'not_score_selected')
                    rejected_output.write(json.dumps({
                        'reason': why, 'target_yaku': [name for name in ORDER if witness.mask & BIT[name]],
                        'witness': scenario(witness), 'actual': [score.to_dict() for score in scores],
                    }, ensure_ascii=False) + '\n')
                    solver.block_rejected_hand(witness)
                    return False
                key = (witness.closed, witness.mask)
                if key not in seen:
                    record = combination_record(witness, matching[0], certificate)
                    records.append(record)
                    seen.add(key)
                    accepted_output.write(json.dumps(record, ensure_ascii=False) + '\n')
                    solver.block_projection(*key)
                return True

            for accepted, name in ((True, 'combinations.jsonl'), (False, 'rejections.jsonl')):
                for line in iter_record_lines(source, name):
                    if not line.strip():
                        continue
                    witness = prior_witness(json.loads(line), accepted)
                    valid = inspect(witness)
                    field = 'source_combinations_rechecked' if accepted else 'source_rejections_rechecked'
                    proof[field] += 1
                    if accepted and not valid:
                        proof['removed_source_combinations'] += 1
                    if models % 2000 == 0:
                        checkpoint()
                        print(f'rechecked={models} sets={len(records)} rejected={rejected}', file=sys.stderr, flush=True)
                    if limit and len(records) >= limit:
                        reason = 'combination_limit'
                        return checkpoint()
            if proof['source_combinations_rechecked'] != proof['source_combination_count']:
                raise ValueError('Source summary count does not match its records')
            accepted_output.flush()
            rejected_output.flush()
            checkpoint()
            print('All seed states rechecked; solving the remaining current constraints.', file=sys.stderr, flush=True)
            while True:
                status = solver.check()
                if status == z3.unsat:
                    complete, reason = True, 'unsat'
                    break
                if status == z3.unknown:
                    reason = 'unknown: ' + solver.solver.reason_unknown()
                    break
                witness = solver.decode()
                inspect(witness)
                proof['additional_solver_models'] += 1
                if models % 100 == 0:
                    checkpoint()
                    print(f'models={models} sets={len(records)} rejected={rejected}', file=sys.stderr, flush=True)
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
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout-ms', type=int, default=0)
    args = parser.parse_args()
    if args.timeout_ms < 0:
        parser.error('--timeout-ms must be nonnegative')
    try:
        summary = revalidate(args.source, args.output, timeout_ms=args.timeout_ms)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, str(error) + '\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['complete'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
