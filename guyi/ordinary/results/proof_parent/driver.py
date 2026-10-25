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


def run(output, seeds, resume=False):
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'combinations.jsonl'
    summary_path = output / 'summary.json'
    driver_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    source = hashes()
    seen = {}
    shards_done = set()
    if path.exists() and not resume:
        raise ValueError('Output exists; use --resume or a fresh output')
    if resume and summary_path.exists():
        previous = json.loads(summary_path.read_text())
        assert previous['source_sha256'] == source and previous['driver_sha256'] == driver_hash
        if previous['complete']:
            return previous
        shards_done = {tuple(s) for s in previous['shards_done']}
    if resume and path.exists():
        seen = {(r['closed'], r['mask']): r for r in map(json.loads, path.read_text().splitlines())}
    solver = ShapeSolver()
    shards = signatures()
    solver.solver.push()
    solver.solver.add(z3.Not(z3.Or(*(shard_constraint(solver, c, m) for c, m in shards))))
    assert solver.check() == z3.unsat, 'Event signatures did not cover the structural model'
    solver.solver.pop()
    start = time.monotonic()
    models = rejected = 0
    complete = False
    termination = 'running'

    def checkpoint():
        data = dict(complete=complete, termination=termination, combination_count=len(seen),
                    closed=sum(k[0] for k in seen), open=sum(not k[0] for k in seen),
                    models=models, rejected=rejected, elapsed_seconds=round(time.monotonic()-start, 3),
                    source_sha256=source, driver_sha256=driver_hash, z3_version=z3.get_version_string(),
                    shard_count=len(shards), shards_done=sorted(shards_done), coverage_unsat=True)
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
    args = parser.parse_args()
    s = run(args.output, args.seed, args.resume)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    return 0 if s['complete'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
