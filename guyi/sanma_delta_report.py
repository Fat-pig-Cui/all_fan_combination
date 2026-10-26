#!/usr/bin/env python3
"""Build the three-player ordinary-yaku delta after re-scoring all witnesses."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import csv
import io
import zipfile

ROOT = Path(__file__).resolve().parent
ORDINARY = ROOT / "ordinary"
sys.path.insert(0, str(ORDINARY))
from calc_fan import ORDER, YAKU, YAKUMAN, score_hand
from enumerate_sanma_delta import witness, source_hashes
from reachability import condition_certificate
from result_records import iter_record_lines, verify_archive

ANCIENT = set(ORDER[30:])


def records(path):
    path = Path(path)
    if path.suffix == ".json":
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else data.get("records", [])
    return [json.loads(line) for line in iter_record_lines(path, 'combinations.jsonl') if line.strip()]


def key(score):
    return score.closed, tuple(score.yaku)


def names(yaku):
    return "＋".join(YAKU[name][1] for name in yaku) or "—"


def re_score(record):
    try:
        w = witness(record["witness"])
        if condition_certificate(w) is None:
            return []
        scores = score_hand(w.hand, w.context, w.melds)
    except (ValueError, KeyError):
        return []
    return [score for score in scores if not score.yakuman and score.yaku]


def current_from(records_list):
    output = {}
    for record in records_list:
        for score in re_score(record):
            output.setdefault(key(score), dict(closed=score.closed, mask=score.mask,
                                               yaku=list(score.yaku), han=score.han, fu=score.fu,
                                               witness=record["witness"],
                                               selected_interpretation=score.to_dict()))
    return output


def state(k):
    return "门清" if k[0] else "副露"


def removal_reason(k):
    y = set(k[1])
    if {'double_riichi', 'haitei'} <= y:
        return '双立直＋海底摸月被石上三年替代'
    if {'double_riichi', 'houtei'} <= y:
        return '双立直＋河底捞鱼被石上三年替代'
    if {'iipeikou', 'pinfu', 'junchan', 'chinitsu'} <= y:
        return '一杯口＋平和＋纯全带幺九＋清一色必然改计一色三同顺'
    if {'iipeikou', 'pinfu', 'chanta', 'honitsu'} <= y:
        return '一杯口＋平和＋混全带幺九＋混一色必然改计一色三同顺'
    return '其他（详见压缩包）'


def main():
    baseline_dir = ORDINARY.parents[1] / 'results' / 'sanma'
    baseline_audit = verify_archive(baseline_dir)
    baseline_summary = json.loads((baseline_dir / 'summary.json').read_text())
    assert baseline_summary['complete'] and baseline_summary['scope']['players'] == 3
    baseline_records = records(baseline_dir)
    ancient_paths = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else []
    if not ancient_paths:
        raise ValueError('Pass one completed ancient-yaku result directory as an argument; generated run data is not bundled.')
    if len(ancient_paths) != 1:
        raise ValueError('Publish only one complete full-model run; earlier partial searches are seeds, not a proof')
    full_summary = json.loads((ancient_paths[0] / 'summary.json').read_text())
    assert full_summary['complete'] and full_summary['termination'] == 'unsat'
    assert full_summary.get('required_yaku') is None and full_summary.get('only_shard') is None
    assert full_summary['coverage_unsat'] and len(full_summary['shards_done']) == full_summary['shard_count']
    assert full_summary['source_sha256'] == source_hashes()
    ancient_records = []
    for path in ancient_paths:
        ancient_records.extend(records(path))
    # Baseline names come from the independent RANKED scorer. Re-scoring them
    # with ancient yaku already enabled would erase precisely the delta.
    baseline = {(r['closed'], tuple(r['yaku'])): r for r in baseline_records}
    assert len(baseline) == baseline_summary['combination_count']
    current = current_from(ancient_records)
    assert len(current) == full_summary['combination_count']
    for r in ancient_records:
        assert any((s.closed, s.mask, s.han, s.fu) == (r['closed'], r['mask'], r['han'], r['fu']) for s in re_score(r))
    added = sorted(current.keys() - baseline.keys(), key=lambda k: (not k[0], len(k[1]), k[1]))
    assert all(set(k[1]) & ANCIENT for k in added), 'New ordinary projection without an ancient role requires investigation'
    removed = sorted(baseline.keys() - current.keys(), key=lambda k: (not k[0], len(k[1]), k[1]))
    unchanged = baseline.keys() & current.keys()

    def counts(keys):
        return dict(total=len(keys), closed=sum(k[0] for k in keys), open=sum(not k[0] for k in keys))

    profiles = defaultdict(Counter)
    for k in added:
        profiles[tuple(y for y in k[1] if y in ANCIENT)][state(k)] += 1
    ancient_in_added = {y: [k for k in added if y in k[1]] for y in ANCIENT}

    lines = [
        "# 雀魂三麻开启古役后的普通役组合差量",
        "",
        "## 统计范围与三麻模型",
        "",
        "这是在雀魂三麻段位规则上额外启用雀魂14种古役的理论扩展，不表示官方提供这种房间。三麻仅去除2至8万，完整保留筒子、索子和字牌；禁止吃，允许碰、杠和拔北。拔北补牌可成立岭上开花，立直要求通常牌山至少剩3张。",
        "",
        "普通役组合按最终计入的完整役种集合去重，门清和副露分开统计；不计宝牌，不计自然役满，普通役累计达到13番以上仍保留。同一手牌比较全部合法分解，依次按基本点、总番数和符数择优，完全并列者均保留。基线由独立段位计番得到，开启古役后的集合由完整古役模型枚举；某个旧示例升级为古役役满，不等于整个普通役集合消失。",
        "",
        "本报告只使用理论计番器和结构枚举；三麻服务器行为、拔北与边界事件的实机验证不在本次计算内。",
        "",
        "## 数量变化",
        "",
        "| 项目 | 门清 | 副露 | 合计 |",
        "|:---:|:---:|:---:|:---:|",
    ]
    for label, title, keys in (("baseline", "三麻段位基线", baseline), ("unchanged", "仍然存在", unchanged),
                               ("removed", "消失", set(removed)), ("added", "新增", set(added)),
                               ("current", "开启古役后", current)):
        c = counts(keys)
        lines.append(f"| {title} | {c['closed']:,} | {c['open']:,} | {c['total']:,} |")
    lines += ["", f"即 ${len(baseline)}-{len(removed)}+{len(added)}={len(current)}$ 种。", ""]

    lost = defaultdict(Counter)
    for k in removed:
        lost[removal_reason(k)][state(k)] += 1
    lines += ["## 消失的组合", "", "下表按组合族归类，包含核心役种之外的所有合法扩展；各行互斥，完整集合逐条列在压缩包中。", "",
              "| 消失的组合族 | 门清 | 副露 | 合计 |", "|:---:|:---:|:---:|:---:|"]
    for reason, c in sorted(lost.items()):
        lines.append(f"| {reason} | {c['门清']:,} | {c['副露']:,} | {sum(c.values()):,} |")
    if not removed:
        lines.append("| — | 0 | 0 | 0 |")
    lines += ['', '一杯口替换的两族必须有四组顺子；纯全或混全加染手使数牌顺子只能取123或789，'
              '一杯口而非二杯口要求四组的分配为三组相同、一组不同，因此必然触发一色三同顺。'
              '车轮类役满会使部分旧牌例失效，但不能仅凭旧牌例升级为役满就将对应普通组合删除。']

    lines += ["", "## 新增的组合", "", "新增集合按恰好包含的古役集合分组；下表各行互斥，可以直接相加。", "",
              "| 新增集合所含古役（恰好） | 门清 | 副露 | 合计 |", "|:---:|:---:|:---:|:---:|"]
    for profile, c in sorted(profiles.items(), key=lambda item: (len(item[0]), item[0])):
        lines.append(f"| {names(profile)} | {c['门清']:,} | {c['副露']:,} | {sum(c.values()):,} |")
    if not profiles:
        lines.append("| — | 0 | 0 | 0 |")

    lines += ["", "## 按单个古役统计", "", "同一新增集合可能含多个古役，所以下表不能相加；它用于观察三麻中各古役的覆盖范围。", "",
              "| 古役 | 门清 | 副露 | 合计 |", "|:---:|:---:|:---:|:---:|"]
    for y in ORDER[30:]:
        keys = ancient_in_added[y]
        lines.append(f"| {YAKU[y][1]} | {sum(k[0] for k in keys):,} | {sum(not k[0] for k in keys):,} | {len(keys):,} |")

    lines += ["", "## 三麻与四麻差异的解释", "",
              "三麻没有三色同顺；三色同刻仍可使用三门的1或9成立。一色三同顺在筒子、索子中仍然可能，不能因没有万子顺子而将它排除。另一方面，三麻禁止吃，副露的三组相同顺子只能全部留在手中；改拆成三连刻与剩余固定刻子后，对对和等收益更高，因此不能作为最终取高的副露一色三同顺结果。门清四顺子分解则必须保留。拔北增加了岭上开花的可达路径，但不是固定面子，也不属于牌河。",
              "",
              "一色三同顺、三连刻、十二落抬、五门齐、一筒摸月和九筒捞鱼仍由同一古役计番器判断，但三麻牌池会改变它们的可实现牌型数量。大车轮、大竹林、大数邻、大七星等古役役满不属于本报告的普通役差集；若某牌型在开启古役后成为役满，旧普通役集合只在没有其他可达示例时才算消失。",
              "",
              "## 完整性与核验",
              "",
              f"独立三麻段位基线共有 **{len(baseline_records):,}** 种，已核对压缩包各成员的SHA-256、字节数和记录数。完整古役模型共有 **{len(ancient_records):,}** 种，每条见证都重新计番并核对行动条件证书。",
              "",
              f"完整古役搜索的{full_summary['shard_count']}个事件分片全部以UNSAT结束，并通过分片覆盖检查。既有结果只用于提供经重新计番的见证，不用于排除未搜索的役种集合。完整新增与消失清单、示例牌型和分组表保存在同目录的 `sanma_ordinary_delta.zip`。这些是所声明模型下的离线理论结论，不是服务器实测。",
              ""]

    meta = dict(scope="three-player ranked ordinary-yaku delta with Mahjong Soul ancient yaku",
                baseline=counts(baseline), current=counts(current), unchanged=counts(unchanged),
                added=counts(set(added)), removed=counts(set(removed)), ancient_profiles=len(profiles),
                baseline_records=len(baseline_records), ancient_records=len(ancient_records),
                ancient_search_summary=[str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)
                                        for p in ancient_paths], source_sha256=source_hashes())
    meta.update(complete=True, termination='unsat', shard_count=full_summary['shard_count'],
                baseline_archive_audit=baseline_audit,
                removed_reason_counts={reason:sum(c.values()) for reason,c in lost.items()})
    def csv_text(header, rows):
        buf = io.StringIO(newline=''); writer = csv.writer(buf)
        writer.writerow(header); writer.writerows(rows)
        return '\ufeff' + buf.getvalue()
    from ordinary_delta import hand_display, describe
    with zipfile.ZipFile(ROOT / 'sanma_ordinary_delta.zip', 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for label, keys, data in (('added', added, current), ('removed', removed, baseline)):
            archive.writestr(label + '.csv', csv_text(['状态','完整役种集合','示例牌型','和牌情境'],
                [[state(k),names(k[1]),hand_display(data[k]['witness']),describe(data[k]['witness'])] for k in keys]))
        archive.writestr('ancient_profiles.csv', csv_text(['新增集合所含古役（恰好）','门清','副露','合计'],
            [[names(profile),c['门清'],c['副露'],sum(c.values())]
             for profile,c in sorted(profiles.items(), key=lambda item:(len(item[0]),item[0]))]))
        archive.writestr('summary.json',json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    (ROOT / "SANMA_ORDINARY_DELTA.md").write_text("\n".join(lines))
    (ROOT / "sanma_ordinary_delta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
