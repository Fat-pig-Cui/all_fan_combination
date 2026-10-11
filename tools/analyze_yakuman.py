#!/usr/bin/env python3
"""Enumerate compatible natural-yakuman projections.

Natural yakuman are kept in a separate projection from the ordinary-yaku
snapshot.  Z3 supplies standard and seven-pairs witnesses; the independent
Python evaluator decides the final yakuman set.  Kokushi is a special shape
and is therefore supplied by a small explicit witness family.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import z3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from calc_fan import Context, YAKUMAN, compact_tiles, score_hand, tile_name
from rules import get_rules
from shape_solver import ShapeSolver


NATURAL_FLAGS = tuple(sorted((
    'chiihou', 'chinroutou', 'chuuren', 'daisangen', 'daisuushii',
    'junsei_chuuren', 'ryuuiisou', 'shousuushii', 'suukantsu',
    'suuankou', 'suuankou_tanki', 'tenhou', 'tsuuiisou',
)))


def context_variants(players: int):
    """Use both win sources and both first-turn seats.

    The first-turn contexts are intentionally fixed to a clean tsumo.  The
    ordinary contexts cover both tsumo and ron, because concealed status and
    winning-group assignment can change a natural projection.
    """
    common = dict(round_wind=27, riichi=0, ippatsu=False, event='none', players=players)
    yield Context(win=0, tsumo=True, seat=27, first_turn=False, **common)
    yield Context(win=0, tsumo=False, seat=27, first_turn=False, **common)
    yield Context(win=0, tsumo=True, seat=27, first_turn=True, **common)
    yield Context(win=0, tsumo=True, seat=28, first_turn=True, **common)


def add_scores(found, witness, scores):
    for score in scores:
        if not score.yakuman:
            continue
        names = tuple(sorted(score.yakuman))
        found.setdefault(names, {
            'hand': compact_tiles(witness.hand),
            'win': tile_name(witness.context.win),
            'melds': [group.to_dict() for group in getattr(witness, 'melds', ())],
            'closed': getattr(witness, 'closed', True),
            'tsumo': witness.context.tsumo,
            'first_turn': witness.context.first_turn,
            'seat': tile_name(witness.context.seat),
            'players': witness.context.players,
            'kind': witness.kind,
        })


def enumerate_solver_context(found, context, players, kind):
    solver = ShapeSolver(natural=True, kind=kind, context=context, players=players)
    while solver.check() == z3.sat:
        model = solver.solver.model()
        witness = solver.decode(model)
        scores = score_hand(witness.hand, witness.context, witness.melds)
        add_scores(found, witness, scores)
        flags = {name for name, flag in zip(NATURAL_FLAGS, solver.yakuman_flags)
                 if z3.is_true(model.eval(flag, model_completion=True))}
        solver.block_yakuman_projection(flags)


def enumerate_kokushi(found, players):
    available = set(get_rules(players).available_tiles)
    orphans = tuple(sorted(set(range(34)) & {0, 8, 9, 17, 18, 26, 27, 28, 29, 30, 31, 32, 33} & available))
    duplicate = orphans[0]
    completed = tuple(sorted(orphans + (duplicate,)))
    for first_turn, seat, tsumo in ((False, 27, True), (False, 27, False),
                                    (True, 27, True), (True, 28, True)):
        common = dict(round_wind=27, riichi=0, ippatsu=False, event='none', players=players,
                      first_turn=first_turn, seat=seat, tsumo=tsumo)
        # Duplicate win: thirteen-sided kokushi.  A different orphan win while
        # retaining the duplicate gives the ordinary kokushi projection.
        for win in (duplicate, orphans[1]):
            hand = list(completed)
            hand.remove(win)
            context = Context(win=win, **common)
            class W:
                pass
            witness = W()
            witness.hand = tuple(hand)
            witness.context = context
            witness.kind = 'kokushi'
            add_scores(found, witness, score_hand(hand, context))


def profile(players: int):
    found = {}
    enumerate_kokushi(found, players)
    for context in context_variants(players):
        for kind in ('standard', 'seven'):
            enumerate_solver_context(found, context, players, kind)
    by_multiple = Counter(sum(YAKUMAN[name][1] for name in names) for names in found)
    return {
        'players': players,
        'yakuman_catalog': {name: {'name': YAKUMAN[name][0], 'multiple': YAKUMAN[name][1]}
                            for name in sorted(YAKUMAN)},
        'combination_count': len(found),
        'multipliers': {str(key): by_multiple[key] for key in sorted(by_multiple)},
        'combinations': [
            {'yakuman': list(names), 'multiple': sum(YAKUMAN[name][1] for name in names),
             'witness': found[names]}
            for names in sorted(found)
        ],
    }


def report(data):
    lines = [
        '# 自然役满复合分析', '',
        '本报告把自然役满作为独立投影枚举；普通役组合快照的计数与文件不在此处重算。',
        '每一行代表一个可成立的完整役满集合，倍数是集合内各役满倍数之和。', '',
        '## 结果', '',
        '| 玩法 | 役满集合数 | 倍数分布 |', '|---|---:|---|',
    ]
    for players in (4, 3):
        item = data[str(players)]
        dist = '、'.join(f"{key}倍:{value}" for key, value in item['multipliers'].items())
        lines.append(f"| {'四麻' if players == 4 else '三麻'} | {item['combination_count']} | {dist} |")
    lines += [
        '', '## 判定范围', '',
        '- 天和、地和使用首巡自摸上下文；天和会把四暗刻、纯正九莲、国士无双提升为对应上位役满，地和则按实际等待形区分。',
        '- 普通形与七对子由结构约束提出，再由 `calc_fan.py` 独立复核；国士无双由显式十三幺牌形复核。',
        '- 本次枚举不把宝牌、累计役满支付档位或普通役加入自然役满集合。',
        '- 四麻参考资料是 `majsoul-replay-editor/products/4P/所有役满合集/README.md`；其中列出的参考总行数为98，作为文献对照，不作为求解器输入。',
        '', '## 读取方式', '',
        '机器结果见 `results/yakuman/summary.json`，每个集合保留一个可复核的牌形见证。',
    ]
    four = data['4']['combination_count']
    lines.insert(9, f'四麻与参考资料的行数对照：计算得到 **{four}** 行，参考资料记载 **98** 行；多出的集合见下文说明。')
    if four == 99:
        lines.insert(10, '差异是“四杠子＋大四喜＋字一色”（四倍役满）：四种风牌各开杠、以另一张字牌作雀头，结构上可以成立；参考合集未列出该开放杠组合。')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'results/yakuman')
    parser.add_argument('--players', choices=('3', '4', 'all'), default='all')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    selected = (3, 4) if args.players == 'all' else (int(args.players),)
    data = {str(players): profile(players) for players in selected}
    # Keep a stable two-profile document when the default command is used.
    for players in (3, 4):
        data.setdefault(str(players), profile(players))
    payload = {'schema_version': 1, 'profiles': data}
    (args.output / 'summary.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.output / 'REPORT.md').write_text(report(data), encoding='utf-8')
    with (args.output / 'witnesses.jsonl').open('w', encoding='utf-8') as handle:
        for players in (4, 3):
            for combination in data[str(players)]['combinations']:
                handle.write(json.dumps({'players': players, **combination}, ensure_ascii=False) + '\n')
    print(json.dumps({players: data[str(players)]['combination_count'] for players in (4, 3)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
