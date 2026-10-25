#!/usr/bin/env python3
"""Enumerate full ordinary-yaku sets with guyi, then save ranked-set deltas.

The bundled baseline is a read-only seed, never a completeness assumption.
Only UNSAT of the augmented structure model establishes completion.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time

import z3

from calc_fan import ORDER, YAKU, compact_tiles, context_from_dict, parse_tiles, parse_meld, score_hand, tile_name
from shape_solver import ShapeSolver, Witness
from reachability import condition_certificate
from result_records import iter_record_lines

ROOT = Path(__file__).resolve().parent


def hashes():
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.glob('*.py'))}


def scenario(w):
    c = w.context
    return dict(hand=compact_tiles(w.hand), win=tile_name(c.win), melds=[g.to_dict() for g in w.melds],
                tsumo=c.tsumo, seat=tile_name(c.seat), round_wind=tile_name(c.round_wind),
                riichi=c.riichi, ippatsu=c.ippatsu, event=c.event, tsubame=c.tsubame, kanburi=c.kanburi)


def witness(data):
    melds = tuple(parse_meld(g) for g in data.get('melds', []))
    return Witness(parse_tiles(data['hand']), melds, context_from_dict(data),
                   not any(g.open for g in melds), 0)


def save_json(path, data):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def enumerate_sets(output, resume=False, limit=0, extra_seeds=()):
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'combinations.jsonl'
    source = hashes()
    seen = {}
    prior = output / 'summary.json'
    if path.exists() and not resume:
        raise ValueError('Output exists; use --resume or a fresh --output')
    if resume and prior.exists():
        previous = json.loads(prior.read_text())
        if previous['source_sha256'] != source:
            raise ValueError('Source changed; use a fresh --output')
        if previous['complete']:
            return previous
    if resume and path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            seen[(r['closed'], r['mask'])] = r
    solver = ShapeSolver()
    for key in seen:
        solver.block_projection(*key)
    start = time.monotonic()
    models = rejected = seed_count = 0
    expanded_hands = set()
    complete = False
    termination = 'running'

    def checkpoint():
        summary = dict(complete=complete, termination=termination, combination_count=len(seen),
                       closed=sum(k[0] for k in seen), open=sum(not k[0] for k in seen),
                       models=models, rejected=rejected, seeded=seed_count,
                       elapsed_seconds=round(time.monotonic()-start, 3), source_sha256=source,
                       z3_version=z3.get_version_string())
        save_json(prior, summary)
        return summary

    with path.open('a') as handle:
        def accept(w, scores=None, cert=None):
            nonlocal seed_count
            cert = cert if cert is not None else condition_certificate(w)
            if cert is None:
                return False
            added = False
            for score in (scores if scores is not None else score_hand(w.hand, w.context, w.melds)):
                if score.yakuman or not score.yaku:
                    continue
                key = score.closed, score.mask
                if key in seen:
                    continue
                record = dict(closed=score.closed, mask=score.mask, yaku=list(score.yaku),
                              han=score.han, fu=score.fu, witness=scenario(w),
                              selected_interpretation=score.to_dict(), condition_certificate=cert)
                seen[key] = record
                handle.write(json.dumps(record, ensure_ascii=False)+'\n')
                solver.block_projection(*key)
                added = True
            return added

        def expand(w):
            # Conditions do not change the tile inventory. Re-score each
            # reachable context once; these are seeds, never an UNSAT shortcut.
            nonlocal seed_count
            c = w.context
            signature = (tuple(sorted(w.hand)), tuple(sorted(w.melds)), c.win, c.seat, c.round_wind)
            if signature in expanded_hands:
                return
            expanded_hands.add(signature)
            closed = not any(g.open for g in w.melds)
            for riichi in ((0, 1, 2) if closed else (0,)):
                for tsumo in (False, True):
                    events = ('none', 'haitei', 'rinshan') if tsumo else ('none', 'houtei', 'chankan')
                    for event in events:
                        if event == 'rinshan' and not any(g.kan for g in w.melds):
                            continue
                        if riichi == 2 and event in ('haitei', 'houtei', 'chankan'):
                            continue
                        for ippatsu in ((False, True) if riichi else (False,)):
                            flags = ((False, False), (True, False), (False, True), (True, True)) if not tsumo and event == 'none' else ((False, False),)
                            for t, k in flags:
                                try:
                                    context = replace(c, riichi=riichi, tsumo=tsumo, event=event,
                                                      ippatsu=ippatsu, tsubame=t, kanburi=k)
                                    if accept(replace(w, context=context)):
                                        seed_count += 1
                                except ValueError:
                                    continue

        checkpoint()
        try:
            # Re-evaluate every ranked witness AND rejected candidate, including
            # alternative event paths. Old rejected decompositions may win now.
            sources = [(ROOT / 'baseline', filename) for filename in ('combinations.jsonl', 'rejections.jsonl')]
            sources += [(Path(directory), 'combinations.jsonl') for directory in extra_seeds]
            for directory, filename in sources:
                for number, line in enumerate(iter_record_lines(directory, filename), 1):
                    data = json.loads(line)['witness']
                    w = witness(data)
                    expand(w)
                    if number % 2000 == 0:
                        print(f'seed {filename} {number}: {len(seen)} sets, {time.monotonic()-start:.1f}s', flush=True)
                        checkpoint()
            handle.flush()
            print(f'seed complete: {len(seen)}; checking remaining constraints', flush=True)
            while True:
                if limit and models >= limit:
                    termination = 'model_limit'
                    break
                status = solver.check()
                if status == z3.unsat:
                    complete, termination = True, 'unsat'
                    break
                if status == z3.unknown:
                    termination = 'unknown: ' + solver.solver.reason_unknown()
                    break
                w = solver.decode()
                models += 1
                cert = condition_certificate(w)
                scores = score_hand(w.hand, w.context, w.melds)
                matching = [s for s in scores if not s.yakuman and s.mask == w.mask and s.closed == w.closed]
                if cert is None or not matching:
                    rejected += 1
                    solver.block_rejected_hand(w)
                else:
                    accept(w, scores, cert)
                    expand(w)
                if models % 100 == 0:
                    handle.flush()
                    checkpoint()
                    print(f'models={models} sets={len(seen)} rejected={rejected} elapsed={time.monotonic()-start:.1f}s', flush=True)
        except KeyboardInterrupt:
            termination = 'interrupted'
        finally:
            handle.flush()
            summary = checkpoint()
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'results')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--max-models', type=int, default=0)
    parser.add_argument('--extra-seeds', type=Path, action='append', default=[])
    args = parser.parse_args()
    summary = enumerate_sets(args.output, args.resume, args.max_models, args.extra_seeds)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary['complete'] else 3


if __name__ == '__main__':
    raise SystemExit(main())
