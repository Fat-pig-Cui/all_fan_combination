#!/usr/bin/env python3
"""Finish the ordinary ancient-yaku search in disjoint event-signature shards.

Each shard fixes only projected yaku flags, not a representative timeline.
A separate UNSAT check proves that these shards cover the whole model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'ordinary'))
import z3
from calc_fan import BIT, Context, ORDER, situational, score_hand
from enumerate_guyi import hashes, save_json, scenario, witness
from reachability import condition_certificate
from result_records import iter_record_lines
from shape_solver import ShapeSolver

EVENT_YAKU = ('menzen_tsumo', 'riichi', 'double_riichi', 'ippatsu', 'chankan', 'rinshan',
              'haitei', 'houtei', 'tsubame', 'kanburi', 'pin_moon', 'pin_fish')
EVENT_MASK = sum(BIT[y] for y in EVENT_YAKU)
COMPATIBLE_PRIOR_DRIVER = '379da870a7532a9ffe1ab8935f884f76a1dc0e0e9ac8969876d9f92c66ce62c3'


def selected_score_constraints(solver):
    """Necessary dominance conditions; add conjuncts to the original model."""
    role = dict(zip(ORDER, solver.yaku))
    kans = z3.Sum([z3.If(k, 1, 0) for k in solver.kan])
    # Three unfixed consecutive triplets + a sequence, with no sanankou,
    # lose to the triple-sequence reading (at least one extra han).
    solver.solver.add(z3.Implies(z3.And(solver.closed, role['three_consecutive_triplets'],
                                      z3.Not(role['sanankou']), z3.Not(role['toitoi'])), kans > 0))
    # Three unfixed consecutive triplets plus that very same sequence
    # contain four copies of each rank. Four identical sequences give
    # ryanpeikou + three-same (6 han), beating at most sanankou + consecutive
    # (4 han). A declared ankan prevents this regrouping and is retained.
    four_identical = z3.Or(*[
        z3.And(solver.seq[i], *[z3.Not(solver.seq[j]) for j in range(4) if j != i],
               *[z3.Or(*[solver.tile[j] == solver.tile[i] + d for j in range(4) if j != i]) for d in range(3)])
        for i in range(4)])
    solver.solver.add(z3.Not(z3.And(solver.closed, kans == 0, solver.kind == 0, four_identical)))


def signatures():
    result = set()
    for closed in (False, True):
        for riichi in ((0, 1, 2) if closed else (0,)):
            for tsumo in (False, True):
                for event in ('none', 'chankan', 'rinshan', 'haitei', 'houtei'):
                    for ippatsu in (False, True):
                        for tsubame in (False, True):
                            for kanburi in (False, True):
                                for win in (4, 9, 17):
                                    try:
                                        c = Context(win, tsumo=tsumo, riichi=riichi, event=event,
                                                    ippatsu=ippatsu, tsubame=tsubame, kanburi=kanburi)
                                    except ValueError:
                                        continue
                                    mask = sum(BIT[y] for y in situational(c, closed))
                                    result.add((closed, mask))
    return sorted(result)


def shard_constraint(solver, closed, event_mask):
    return z3.And(solver.closed == closed, *(solver.yaku[ORDER.index(y)] == bool(event_mask & BIT[y]) for y in EVENT_YAKU))


def run(output, seeds, resume=False, inherit=None):
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'combinations.jsonl'
    summary_path = output / 'summary.json'
    driver_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    source = hashes()
    seen = {}
    shards_done = set()
    inherited_proof = None
    if path.exists() and not resume:
        raise ValueError('Output exists; use --resume or a fresh output')
    if resume and summary_path.exists():
        previous = json.loads(summary_path.read_text())
        assert previous['source_sha256'] == source and previous['driver_sha256'] == driver_hash
        if previous['complete']:
            return previous
        shards_done = {tuple(s) for s in previous['shards_done']}
        inherited_proof = previous.get('inherited_proof')
    if resume and path.exists():
        seen = {(r['closed'], r['mask']): r for r in map(json.loads, path.read_text().splitlines())}
    solver = ShapeSolver()
    # The new model is literally the old base model AND these conditions.
    # Previously exhausted shards remain UNSAT under this restriction.
    selected_score_constraints(solver)
    shards = signatures()
    solver.solver.push()
    solver.solver.add(z3.Not(z3.Or(*(shard_constraint(solver, c, m) for c, m in shards))))
    assert solver.check() == z3.unsat, 'Event signatures did not cover the structural model'
    solver.solver.pop()
    prior_keys = set()
    if inherit is not None:
        old_summary_path = inherit / 'summary.json'
        old = json.loads(old_summary_path.read_text())
        if old['source_sha256'] != source or old['driver_sha256'] != COMPATIBLE_PRIOR_DRIVER:
            raise ValueError('Inheritance requires the exact compatible base-model driver and unchanged core sources')
        if hashlib.sha256((inherit / 'driver.py').read_bytes()).hexdigest() != COMPATIBLE_PRIOR_DRIVER:
            raise ValueError('Missing/mismatched prior driver source')
        if not old['coverage_unsat'] or old['shard_count'] != len(shards):
            raise ValueError('Prior coverage proof differs')
        shards_done = {tuple(s) for s in old['shards_done']}
        assert shards_done <= set(shards)
        for line in iter_record_lines(inherit, 'combinations.jsonl'):
            r = json.loads(line)
            prior_keys.add((r['closed'], r['mask']))
        assert len(prior_keys) == old['combination_count']
        parent = output / 'proof_parent'
        parent.mkdir(exist_ok=True)
        shutil.copy2(old_summary_path, parent / 'summary.json')
        shutil.copy2(inherit / 'driver.py', parent / 'driver.py')
        save_json(parent / 'keys.json', sorted(prior_keys))
        inherited_proof = dict(shards=len(shards_done), stronger_by_conjunction=True,
                               prior_summary_sha256=hashlib.sha256(old_summary_path.read_bytes()).hexdigest(),
                               prior_driver_sha256=COMPATIBLE_PRIOR_DRIVER,
                               prior_keys_sha256=hashlib.sha256((parent / 'keys.json').read_bytes()).hexdigest())
        seeds = list(seeds) + [inherit]
    start = time.monotonic()
    models = rejected = 0
    complete = False
    termination = 'running'

    def checkpoint():
        data = dict(complete=complete, termination=termination, combination_count=len(seen),
                    closed=sum(k[0] for k in seen), open=sum(not k[0] for k in seen),
                    models=models, rejected=rejected, elapsed_seconds=round(time.monotonic()-start, 3),
                    source_sha256=source, driver_sha256=driver_hash, z3_version=z3.get_version_string(),
                    shard_count=len(shards), shards_done=sorted(shards_done), coverage_unsat=True,
                    inherited_proof=inherited_proof)
        save_json(summary_path, data)
        return data

    with path.open('a') as handle:
        def accept(w, scores=None, cert=None):
            cert = cert if cert is not None else condition_certificate(w)
            if cert is None:
                return
            for s in (scores if scores is not None else score_hand(w.hand, w.context, w.melds)):
                if s.yakuman or not s.yaku or (s.closed, s.mask) in seen:
                    continue
                r = dict(closed=s.closed, mask=s.mask, yaku=list(s.yaku), han=s.han, fu=s.fu,
                         witness=scenario(w), selected_interpretation=s.to_dict(), condition_certificate=cert)
                seen[s.closed, s.mask] = r
                handle.write(json.dumps(r, ensure_ascii=False) + '\n')

        try:
            for directory in seeds:
                for line in iter_record_lines(directory, 'combinations.jsonl'):
                    accept(witness(json.loads(line)['witness']))
            assert prior_keys <= seen.keys(), 'Every previously blocked key must retain a validated witness'
            handle.flush()
            checkpoint()
            print(f'{len(seen)} validated seeds; {len(shards)} event shards', flush=True)
            for closed, event_mask in shards:
                if (closed, event_mask) in shards_done:
                    continue
                solver.solver.push()
                solver.solver.add(shard_constraint(solver, closed, event_mask))
                for c, m in seen:
                    if c == closed and m & EVENT_MASK == event_mask:
                        solver.block_projection(c, m)
                while True:
                    status = solver.check()
                    if status == z3.unsat:
                        break
                    if status != z3.sat:
                        raise RuntimeError(solver.solver.reason_unknown())
                    w = solver.decode()
                    models += 1
                    cert = condition_certificate(w)
                    scores = score_hand(w.hand, w.context, w.melds)
                    if cert is None or not any(not s.yakuman and s.mask == w.mask and s.closed == w.closed for s in scores):
                        rejected += 1
                        solver.block_rejected_hand(w)
                    else:
                        accept(w, scores, cert)
                        for s in scores:
                            if not s.yakuman:
                                assert s.mask & EVENT_MASK == event_mask and s.closed == closed
                                solver.block_projection(s.closed, s.mask)
                    if models % 200 == 0:
                        handle.flush()
                        checkpoint()
                        print(f'models={models}, sets={len(seen)}, rejected={rejected}, elapsed={time.monotonic()-start:.1f}s', flush=True)
                solver.solver.pop()
                shards_done.add((closed, event_mask))
                handle.flush()
                checkpoint()
                print(f'shards={len(shards_done)}/{len(shards)}, sets={len(seen)}, elapsed={time.monotonic()-start:.1f}s', flush=True)
            complete, termination = True, 'unsat'
        except KeyboardInterrupt:
            termination = 'interrupted'
        except RuntimeError as error:
            termination = 'unknown: ' + str(error)
        finally:
            handle.flush()
            summary = checkpoint()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'ordinary' / 'results_sharded')
    parser.add_argument('--seed', type=Path, action='append', default=[])
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--inherit', type=Path, help='Reuse exhausted shards from the exact earlier base-model driver')
    args = parser.parse_args()
    s = run(args.output, args.seed, args.resume, args.inherit)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    return 0 if s['complete'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
