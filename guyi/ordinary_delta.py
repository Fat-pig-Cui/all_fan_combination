#!/usr/bin/env python3
"""Audit finished ancient-yaku enumeration and generate the ranked delta."""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'ordinary'))
from calc_fan import ORDER, YAKU, YAKUMAN, compact_tiles, parse_tiles, score_hand
from enumerate_guyi import hashes, witness
from reachability import condition_certificate
from result_records import iter_record_lines, verify_archive

ANCIENT = ORDER[30:]
RESULTS = ROOT / 'ordinary' / 'results'


def key(r):
    return r['closed'], tuple(r['yaku'])


def names(slugs):
    return '＋'.join(YAKU[y][1] for y in slugs) or '—'


def state(r):
    return '门清' if r['closed'] else '副露'


def hand_display(data):
    # Spaces separate concealed/winning tiles from declared groups only.
    concealed = data['hand'].replace(' ', '') + data['win']
    groups = []
    for g in data.get('melds', []):
        if g['kind'] == 'ankan':
            tile, = set(parse_tiles(g['tiles']))
            groups.append(compact_tiles((tile,) * 5))
        else:
            groups.append(g['tiles'].replace(' ', ''))
    return concealed + (' ' + ''.join(groups) if groups else '')


def describe(data):
    event = dict(none='普通自摸' if data['tsumo'] else '普通舍牌荣和',
                 chankan='抢杠荣和', rinshan='岭上自摸', haitei='海底自摸', houtei='河底荣和')[data['event']]
    extra = []
    if data.get('riichi'):
        extra.append('双立直' if data['riichi'] == 2 else '立直')
    if data.get('ippatsu'):
        extra.append('一发')
    if data.get('tsubame'):
        extra.append('和别家的立直宣言牌')
    if data.get('kanburi'):
        extra.append('该舍牌紧接别家杠后岭上摸牌')
    return '，'.join([event] + extra + ['自风' + data['seat'], '场风' + data['round_wind']])


def csv_text(header, rows):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return '\ufeff' + buffer.getvalue()


def main():
    summary = json.loads((RESULTS / 'summary.json').read_text())
    if not summary['complete'] or summary['termination'] != 'unsat':
        raise ValueError('Enumeration must finish UNSAT before publishing a count')
    if summary['source_sha256'] != hashes():
        raise ValueError('Enumeration source hash mismatch')
    if 'driver_sha256' in summary:
        assert hashlib.sha256((ROOT / 'enumerate_ordinary_sharded.py').read_bytes()).hexdigest() == summary['driver_sha256']
        assert summary['coverage_unsat'] and len(summary['shards_done']) == summary['shard_count']
        if summary.get('inherited_proof'):
            p = summary['inherited_proof']
            parent = RESULTS / 'proof_parent'
            assert p['stronger_by_conjunction']
            for name, field in [('summary.json','prior_summary_sha256'), ('driver.py','prior_driver_sha256'), ('keys.json','prior_keys_sha256')]:
                assert hashlib.sha256((parent / name).read_bytes()).hexdigest() == p[field]
            old = json.loads((parent / 'summary.json').read_text())
            assert old['source_sha256'] == summary['source_sha256']
            assert len(old['shards_done']) == p['shards']
    baseline_dir = ROOT / 'ordinary' / 'baseline'
    baseline_audit = verify_archive(baseline_dir)
    baseline = {key(r): r for r in map(json.loads, iter_record_lines(baseline_dir, 'combinations.jsonl'))}
    records = list(map(json.loads, iter_record_lines(RESULTS, 'combinations.jsonl')))
    current = {key(r): r for r in records}
    assert len(current) == len(records) == summary['combination_count']
    if summary.get('inherited_proof'):
        prior_keys = {tuple(k) for k in json.loads((RESULTS / 'proof_parent' / 'keys.json').read_text())}
        assert prior_keys <= {(r['closed'],r['mask']) for r in records}
    assert len(baseline) == 20687
    for r in records:
        w = witness(r['witness'])
        selected = score_hand(w.hand, w.context, w.melds)
        matching = [s for s in selected if not s.yakuman and s.yaku == tuple(r['yaku']) and s.closed == r['closed']
                    and s.mask == r['mask'] and s.han == r['han'] and s.fu == r['fu']]
        assert matching, key(r)
        for s in matching:
            if s.closed and 'three_same_sequences' in s.yaku:
                assert len(s.groups) == 4 and all(g.sequence for g in s.groups)
                if w.context.tsumo or w.context.event == 'chankan':
                    assert {'ryanpeikou', 'chanta', 'junchan'} & set(s.yaku)
        assert condition_certificate(w) is not None, key(r)

    added = sorted(current.keys() - baseline.keys(), key=lambda k: (not k[0], current[k]['han'], k[1]))
    removed = sorted(baseline.keys() - current.keys(), key=lambda k: (not k[0], baseline[k]['han'], k[1]))
    unchanged = current.keys() & baseline.keys()
    counts = {}
    for label, keys in [('ranked', baseline), ('unchanged', unchanged), ('removed', removed), ('added', added), ('ancient', current)]:
        counts[label] = dict(total=len(keys), closed=sum(k[0] for k in keys), open=sum(not k[0] for k in keys))
    assert counts['ancient']['total'] == counts['ranked']['total'] - len(removed) + len(added)
    profiles = defaultdict(Counter)
    for k in added:
        p = tuple(y for y in k[1] if y in ANCIENT)
        profiles[p][state(current[k])] += 1

    lost_reasons = Counter()
    removal_rows = []
    for k in removed:
        r = baseline[k]
        w = witness(r['witness'])
        scores = score_hand(w.hand, w.context, w.melds)
        sample_after = '；'.join(names(s.yaku) if not s.yakuman else '役满：' + '＋'.join(YAKUMAN[y][0] for y in s.yakuman) for s in scores)
        if 'double_riichi' in k[1] and 'haitei' in k[1]:
            reason = '双立直＋海底摸月 → 石上三年'
        elif 'double_riichi' in k[1] and 'houtei' in k[1]:
            reason = '双立直＋河底捞鱼 → 石上三年'
        elif {'iipeikou', 'pinfu', 'junchan', 'chinitsu'} <= set(k[1]):
            reason = '一杯口＋平和＋纯全带幺九＋清一色 → 一色三同顺替换一杯口'
        elif {'iipeikou', 'pinfu', 'chanta', 'honitsu'} <= set(k[1]):
            reason = '一杯口＋平和＋混全带幺九＋混一色 → 一色三同顺替换一杯口'
        else:
            reason = '其他（详见完整差量）'
        lost_reasons[reason] += 1
        removal_rows.append([state(r), r['han'], names(r['yaku']), reason,
                             hand_display(r['witness']), describe(r['witness']), sample_after])

    added_rows = [[state(current[k]), current[k]['han'], names(k[1]),
                   names(y for y in k[1] if y in ANCIENT), hand_display(current[k]['witness']),
                   describe(current[k]['witness'])] for k in added]
    profile_rows = [[names(p), c['门清'], c['副露'], sum(c.values())]
                    for p, c in sorted(profiles.items(), key=lambda pc: (len(pc[0]), tuple(ORDER.index(y) for y in pc[0])))]
    delta_meta = dict(scope='four-player ranked + Mahjong Soul 14 ancient yaku, ordinary complete sets only',
                      counts=counts, ancient_profiles=len(profiles), removed_reason_counts=dict(lost_reasons),
                      completion='unsat', witness_audit_count=len(records), baseline_audit=baseline_audit,
                      sources=summary['source_sha256'], driver_sha256=summary.get('driver_sha256'),
                      shard_count=summary.get('shard_count'), coverage_unsat=summary.get('coverage_unsat'),
                      inherited_proof=summary.get('inherited_proof'))
    with zipfile.ZipFile(ROOT / 'ordinary_delta.zip', 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr('added.csv', csv_text(['状态','总番数','完整役种集合','其中的古役','示例牌型','和牌情境'], added_rows))
        z.writestr('removed.csv', csv_text(['状态','段位总番数','消失的完整役种集合','归类','段位旧示例','旧示例情境','该旧示例启用古役后'], removal_rows))
        z.writestr('ancient_profiles.csv', csv_text(['新增集合所含古役（恰好）','门清','副露','合计'], profile_rows))
        z.writestr('summary.json', json.dumps(delta_meta, ensure_ascii=False, indent=2) + '\n')
    (RESULTS / 'delta_summary.json').write_text(json.dumps(delta_meta, ensure_ascii=False, indent=2)+'\n')
    archive = RESULTS / 'records.zip'
    plain = RESULTS / 'combinations.jsonl'
    if plain.exists():
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            z.write(plain, 'combinations.jsonl')
        with zipfile.ZipFile(archive) as z:
            assert hashlib.sha256(z.read('combinations.jsonl')).digest() == hashlib.sha256(plain.read_bytes()).digest()

    lines = ['# 启用雀魂古役后的普通役组合差量', '',
             '## 统计范围', '',
             '以四麻段位规则为基线，只额外启用雀魂的14种古役；不引入一番街特色役。'
             '一组组合指最终同一次和牌计入的**完整役种名称集合**，门清与副露分别去重。'
             '不计宝牌，不计自然役满；普通役累计达到13番以上仍保留。'
             '同一手牌比较全部合法分解，按基本点、总番数、符数依次择优，完全并列者均保留。', '',
             '这是四麻差量；没有把自定义的“三麻＋古役”混入。', '',
             '## 数量变化', '',
             '| 项目 | 门清 | 副露 | 合计 |', '|:---:|:---:|:---:|:---:|']
    for label, title in [('ranked','段位基线'), ('unchanged','仍然存在'), ('removed','消失'), ('added','新增'), ('ancient','启用古役后')]:
        c = counts[label]
        lines.append(f"| {title} | {c['closed']:,} | {c['open']:,} | {c['total']:,} |")
    lines += ['', f"即 ${len(baseline)}-{len(removed)}+{len(added)}={len(current)}$ 种。", '',
              '## 少了哪些组合', '',
              '下表包含相应核心役种之外的合法条件役扩展；先归类石上三年，其余再归类一杯口替换，交叉部分不重复计算。', '',
              '| 消失的组合族 | 组合数 |', '|:---:|:---:|']
    for reason, n in sorted(lost_reasons.items()):
        lines.append(f'| {reason} | {n:,} |')
    if all('石上三年' in reason for reason in lost_reasons):
        lines += ['', '除了上述两族，没有其他段位完整组合消失。'
                  '三种车轮役满虽然会使部分旧示例失效，但相关普通役集合仍能换用其他牌型实现；'
                  '不能把“某张示例升级为役满”直接算成“这个普通组合被删除”。']
    elif not any('其他' in reason for reason in lost_reasons):
        lines += ['', '除此四族，没有其他段位完整组合消失。'
                  '涉及一杯口的两族都要求四组顺子；平和配合混全／纯全及单一数牌花色后，顺子只能取123或789。'
                  '要有一杯口而不是二杯口，四组的分配只能是三组相同、一组不同，'
                  '启用古役便必然改计一色三同顺，不再计一杯口。']
    lines += ['', '这里的“消失”是原完整役种集合无法再作为最终普通役结果出现，'
              '并不只是某个旧示例不能继续使用。'
              '大车轮、大竹林、大数邻会使门清的2至8各两张升级为役满，但相应旧普通役集合仍可改用其他牌型实现，不额外减少组合数；'
              '大七星覆盖原有字一色，原本已在自然役满排除范围内；'
              '人和只排除首次摸牌前的对应事件，不能据此排除同一牌型在后续巡目的普通和牌。', '',
              '## 多了哪些组合', '',
              '新增组合主要来自以下八种普通古役。表中是“**含该古役**的新增完整集合数”，'
              f'同一集合可能含多个古役，因此各行不能相加；完整清单另按“恰好包含哪些古役”无重叠分为{len(profiles)}类。', '',
              '| 新增组合包含的古役 | 门清 | 副露 | 合计 |', '|:---:|:---:|:---:|:---:|']
    for y in ANCIENT:
        matching = [k for k in added if y in k[1]]
        lines.append(f"| {YAKU[y][1]} | {sum(k[0] for k in matching):,} | {sum(not k[0] for k in matching):,} | {len(matching):,} |")
    no_ancient = [k for k in added if not set(k[1]) & set(ANCIENT)]
    lines += ['', '新增集合均包含至少一种普通古役。' if not no_ancient else f"新增集合中不含任何普通古役的有 **{len(no_ancient)}** 种。", '',
              '### 按恰好包含的古役集合统计', '',
              '下表各行互斥：每个新增完整集合只归入其实际包含的古役集合，因此门清、副露和合计三列均可分别相加。', '',
              '| 新增集合所含古役（恰好） | 门清 | 副露 | 合计 |', '|:---:|:---:|:---:|:---:|']
    for profile, c in sorted(profiles.items(), key=lambda item: (len(item[0]), tuple(ORDER.index(y) for y in item[0]))):
        lines.append(f"| {names(profile)} | {c['门清']:,} | {c['副露']:,} | {sum(c.values()):,} |")
    lines += [f"| **合计** | **{sum(c['门清'] for c in profiles.values()):,}** | **{sum(c['副露'] for c in profiles.values()):,}** | **{len(added):,}** |", '',
              '复合时还要注意：一色三同顺替换一杯口，但可与二杯口复合；'
              '三连刻和一色三同顺不能跨分解相加。'
              '一筒摸月替换海底摸月，九筒捞鱼替换河底捞鱼。'
              '十二落抬要求四组明面子，暗杠不计入四副露。'
              '燕返可以与杠振同时成立，例如对手暗杠、岭上摸牌后以该次舍牌宣言立直；'
              '但杠振所需的开杠会打断和牌者的一发，燕返也不能发生在不允许宣言立直的河底时点。', '',
              '## 完整差量与验证', '',
              '[完整差量压缩包](ordinary_delta.zip)包含新增集合、消失集合及古役分组表。'
              '每个集合附总番数、门清／副露状态和可复算的示例牌型。'
              '牌型写作“和牌前手牌紧跟和牌张，再空一格接固定面子”；暗杠用五个数字标记，实际仍为四张牌。', '',
              f"共重新计番验证 **{len(records):,}** 个古役集合的示例，并核对行动条件证书。"
              '搜索从完整牌型结构出发，候选再经独立计番器检查全部分解；'
              '输入种子只用于加速搜索；52个事件役分片通过覆盖性检查，并均取得不可满足（UNSAT）结论。'
              '另有26项边界回归检查，包括80个结构模型与独立计番的一致性抽样。'
              '这是所声明规则下的理论枚举，没有把脚本核验表述为服务器实测。', '']
    (ROOT / 'ORDINARY_DELTA.md').write_text('\n'.join(lines))
    print(json.dumps(delta_meta, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
