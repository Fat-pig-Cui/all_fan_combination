#!/usr/bin/env python3
"""Enumerate Mahjong Soul three-player ordinary-yaku projections with/without guyi."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import z3

ROOT = Path(__file__).resolve().parent
ORDINARY = ROOT / "ordinary"
sys.path.insert(0, str(ORDINARY))

from calc_fan import BIT, Context, ORDER, compact_tiles, context_from_dict, parse_meld, parse_tiles, score_hand, situational, tile_name
from reachability import condition_certificate
from enumerate_ordinary_sharded import selected_score_constraints
from shape_solver import ShapeSolver, Witness
from result_records import iter_record_lines

ANCIENT = ORDER[30:]
EVENT_YAKU = ("menzen_tsumo", "riichi", "double_riichi", "ippatsu", "chankan",
              "rinshan", "haitei", "houtei", "tsubame", "kanburi", "pin_moon", "pin_fish")
EVENT_MASK = sum(BIT[name] for name in EVENT_YAKU)


def source_hashes():
    names = ("calc_fan.py", "rules.py", "shape_solver.py", "reachability.py",
             "result_records.py", "enumerate_ordinary_sharded.py", "enumerate_sanma_delta.py")
    return {name: hashlib.sha256((ORDINARY / name if name not in ("enumerate_sanma_delta.py", "enumerate_ordinary_sharded.py")
                                  else ROOT / name).read_bytes()).hexdigest() for name in names}


def scenario(w):
    c = w.context
    return dict(hand=compact_tiles(w.hand), win=tile_name(c.win),
                melds=[g.to_dict() for g in w.melds], tsumo=c.tsumo,
                seat=tile_name(c.seat), round_wind=tile_name(c.round_wind),
                riichi=c.riichi, ippatsu=c.ippatsu, event=c.event,
                first_turn=c.first_turn, tsubame=c.tsubame, kanburi=c.kanburi,
                players=c.players, north_count=c.north_count,
                win_source=c.win_source, live_tiles=c.live_tiles)


def witness(data):
    melds = tuple(parse_meld(g) for g in data.get("melds", []))
    c = context_from_dict(data)
    return Witness(parse_tiles(data["hand"]), melds, c, not any(g.open for g in melds), 0)


def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


def signatures():
    result = set()
    # Only 1p and 9p can trigger the pin-moon/pin-fish replacement in sanma;
    # using all available tiles is harmless and keeps the coverage proof explicit.
    wins = (9, 17, 27, 28, 29, 30, 31, 32, 33)
    for closed in (False, True):
        for riichi in ((0, 1, 2) if closed else (0,)):
            for tsumo in (False, True):
                for event in ("none", "chankan", "rinshan", "haitei", "houtei"):
                    for ippatsu in (False, True):
                        for tsubame in (False, True):
                            for kanburi in (False, True):
                                for win in wins:
                                    try:
                                        c = Context(win, tsumo=tsumo, riichi=riichi, event=event,
                                                    ippatsu=ippatsu, tsubame=tsubame,
                                                    kanburi=kanburi, players=3)
                                    except ValueError:
                                        continue
                                    mask = sum(BIT[y] for y in situational(c, closed))
                                    result.add((closed, mask))
    return sorted(result)


def shard_constraint(solver, closed, event_mask):
    return z3.And(solver.closed == closed,
                  *(solver.yaku[ORDER.index(y)] == bool(event_mask & BIT[y])
                    for y in EVENT_YAKU))


def enumerate_sets(output: Path, ancient_enabled: bool, resume=False, max_models=0, seed_dirs=(), only_shard=None, required_yaku=None):
    if not ancient_enabled:
        raise ValueError('Use the independently scored ranked sanma snapshot; forbidding ancient yaku is not ranked scoring')
    output.mkdir(parents=True, exist_ok=True)
    path = output / "combinations.jsonl"
    summary_path = output / "summary.json"
    source = source_hashes()
    seen = {}
    shards_done = set()
    if path.exists() and not resume:
        raise ValueError(f"{path} exists; use --resume")
    if resume and summary_path.exists():
        previous = json.loads(summary_path.read_text())
        if previous["source_sha256"] != source or previous["ancient_enabled"] != ancient_enabled:
            raise ValueError("Source or mode changed; use a fresh output")
        if previous.get('required_yaku') != required_yaku or previous.get('only_shard') != (list(only_shard) if only_shard is not None else None):
            raise ValueError('Search slice changed; use a fresh output')
        if previous["complete"]:
            return previous
        shards_done = {tuple(s) for s in previous["shards_done"]}
    if resume and path.exists():
        seen = {(r["closed"], r["mask"]): r for r in map(json.loads, path.read_text().splitlines())}

    solver = ShapeSolver(players=3)
    selected_score_constraints(solver)
    # Sanma cannot chi. An open three-identical-sequences reading therefore
    # consists of three concealed identical sequences and one fixed triplet.
    # Regrouping the nine tiles gives toitoi + consecutive triplets (4 han),
    # versus 2 han for the sequences. Flush/value/condition roles are retained.
    # Losing 1-han chanta still gains han; losing 2-han junchan ties han but
    # the triplets have more fu. Closed FOUR-sequence readings remain possible.
    solver.solver.add(z3.Implies(solver.yaku[ORDER.index('three_same_sequences')], solver.closed))
    if not ancient_enabled:
        solver.forbid(ANCIENT)
    else:
        # A full run also searches projections WITHOUT an ordinary ancient
        # yaku. Seeds alone cannot prove which ranked sets survive enabling it.
        if required_yaku:
            solver.solver.add(solver.yaku[ORDER.index(required_yaku)])
    shards = signatures()
    solver.solver.push()
    solver.solver.add(z3.Not(z3.Or(*(shard_constraint(solver, c, m) for c, m in shards))))
    assert solver.check() == z3.unsat, "event signatures do not cover the three-player model"
    solver.solver.pop()

    start = time.monotonic()
    models = rejected = 0
    complete = False
    termination = "running"

    def checkpoint():
        summary = dict(complete=complete, termination=termination,
                       combination_count=len(seen),
                       closed=sum(k[0] for k in seen),
                       open=sum(not k[0] for k in seen), models=models,
                       rejected=rejected, elapsed_seconds=round(time.monotonic()-start, 3),
                       source_sha256=source, z3_version=z3.get_version_string(),
                       players=3, ancient_enabled=ancient_enabled,
                       required_yaku=required_yaku, only_shard=only_shard,
                       shard_count=len(shards), shards_done=sorted(shards),
                       coverage_unsat=True)
        # Only shards already searched are complete; keep this separate from
        # the coverage proof to make checkpoints unambiguous.
        summary["shards_done"] = sorted(shards_done)
        save_json(summary_path, summary)
        return summary

    with path.open("a") as handle:
        def accept(w, scores=None, cert=None):
            cert = cert if cert is not None else condition_certificate(w)
            if cert is None:
                return
            candidates = scores if scores is not None else score_hand(w.hand, w.context, w.melds)
            for score in candidates:
                if score.yakuman or not score.yaku:
                    continue
                key = (score.closed, score.mask)
                if key in seen:
                    continue
                seen[key] = dict(closed=score.closed, mask=score.mask,
                                  yaku=list(score.yaku), han=score.han, fu=score.fu,
                                  witness=scenario(w),
                                  selected_interpretation=score.to_dict(),
                                  condition_certificate=cert)
                handle.write(json.dumps(seen[key], ensure_ascii=False) + "\n")

        checkpoint()
        try:
            seed_states = set()
            for seed_dir in seed_dirs:
                seed_path = Path(seed_dir)
                if seed_path.is_file() and seed_path.suffix == '.json':
                    seed_records = json.loads(seed_path.read_text())
                else:
                    seed_records = (json.loads(line) for line in iter_record_lines(seed_path, 'combinations.jsonl') if line.strip())
                for record in seed_records:
                    w = witness(record["witness"])
                    state = (w.hand, w.melds, w.context)
                    if state in seed_states:
                        continue
                    seed_states.add(state)
                    accept(w)
                handle.flush()
                checkpoint()
                print(f'seeds={seed_dir}, sets={len(seen)}', flush=True)
            handle.flush()
            checkpoint()
            for closed, event_mask in signatures():
                if only_shard is not None and (closed, event_mask) != only_shard:
                    continue
                if required_yaku in EVENT_YAKU and not (event_mask & BIT[required_yaku]):
                    continue
                if (closed, event_mask) in shards_done:
                    continue
                solver.solver.push()
                solver.solver.add(shard_constraint(solver, closed, event_mask))
                for c, m in seen:
                    if c == closed and m & EVENT_MASK == event_mask:
                        solver.block_projection(c, m)
                while True:
                    if max_models and models >= max_models:
                        termination = "model_limit"
                        solver.solver.pop()
                        handle.flush()
                        return checkpoint()
                    status = solver.check()
                    if status == z3.unsat:
                        break
                    if status != z3.sat:
                        raise RuntimeError(solver.solver.reason_unknown())
                    w = solver.decode()
                    models += 1
                    cert = condition_certificate(w)
                    scores = score_hand(w.hand, w.context, w.melds)
                    matching = [s for s in scores if not s.yakuman and s.mask == w.mask and s.closed == w.closed]
                    if cert is None or not matching:
                        rejected += 1
                        # A rejected decomposition can still yield other valid
                        # selected projections. Keep and block those too.
                        if cert is not None:
                            accept(w, scores, cert)
                            for score in scores:
                                if not score.yakuman and score.yaku:
                                    solver.block_projection(score.closed, score.mask)
                        solver.block_rejected_hand(w)
                    else:
                        accept(w, scores, cert)
                        for score in matching:
                            solver.block_projection(score.closed, score.mask)
                    if models % 200 == 0:
                        handle.flush()
                        checkpoint()
                        print(f"{output.name}: models={models}, sets={len(seen)}, "
                              f"rejected={rejected}, elapsed={time.monotonic()-start:.1f}s", flush=True)
                solver.solver.pop()
                shards_done.add((closed, event_mask))
                handle.flush()
                checkpoint()
                print(f"{output.name}: shards={len(shards_done)}/{len(shards)}, "
                      f"sets={len(seen)}, elapsed={time.monotonic()-start:.1f}s", flush=True)
            complete, termination = True, "unsat"
        except KeyboardInterrupt:
            termination = "interrupted"
        except RuntimeError as error:
            termination = 'unknown: ' + str(error)
        finally:
            handle.flush()
            summary = checkpoint()
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "ancient", "both"), default="both")
    parser.add_argument("--output-root", type=Path, default=ORDINARY)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-models", type=int, default=0)
    parser.add_argument("--seed", type=Path, action="append", default=[])
    parser.add_argument("--only-shard", nargs=2, metavar=("CLOSED", "MASK"))
    parser.add_argument("--required-yaku", choices=ANCIENT)
    args = parser.parse_args()
    modes = ("baseline", "ancient") if args.mode == "both" else (args.mode,)
    only_shard = None if args.only_shard is None else (args.only_shard[0].lower() in {"true", "1"}, int(args.only_shard[1]))
    results = {}
    for mode in modes:
        result = enumerate_sets(args.output_root / f"results_sanma_{mode}",
                                mode == "ancient", args.resume, args.max_models,
                                args.seed if mode == "ancient" else (), only_shard,
                                args.required_yaku if mode == "ancient" else None)
        results[mode] = result
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(r["complete"] for r in results.values()) else 3


if __name__ == "__main__":
    raise SystemExit(main())
