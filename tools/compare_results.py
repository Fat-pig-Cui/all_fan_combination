#!/usr/bin/env python3
"""Compare the published snapshot with the current manual all_yaku_combos checkout.

Reads old histogram literals without executing its scripts. This is a histogram
comparison; when a normalized manual export exists, also compare complete sets.
"""
from __future__ import annotations

import argparse
import ast
import gzip
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from result_records import iter_record_lines, verify_archive


# First matching structural yaku selects the old mutually exclusive topic.
TOPICS = (
    ('条件役专题', None, 'table_1', 'table_2_1'),
    ('七对子专题', 'chiitoitsu', 'table_2', None),
    ('小三元专题', 'shousangen', 'table_3', 'table_2_2'),
    ('无小三元的一般形混老头专题', 'honroutou', 'table_4', 'table_2_3'),
    ('一般形断幺九专题', 'tanyao', 'table_5', 'table_2_4'),
    ('无断幺的平和专题', 'pinfu', 'table_6', None),
    ('无断幺平和的一般形清一色专题', 'chinitsu', 'table_7', 'table_2_5'),
    ('无平和清一色的纯全带幺九专题', 'junchan', 'table_8', 'table_2_6'),
    ('只含混全和混色的二杯口专题', 'ryanpeikou', 'table_9', None),
    ('无平和清一色的一气通贯专题', 'ittsuu', 'table_10', 'table_2_7'),
    ('无断幺平和纯全的三色同顺专题', 'sanshoku_doujun', 'table_11', 'table_2_8'),
    ('只含役牌双混的一杯口专题', 'iipeikou', 'table_12', None),
    ('无混老断幺纯全的三色同刻专题', 'sanshoku_doukou', 'table_13', 'table_2_9'),
    ('只含役牌三暗杠混色的混全专题', 'chanta', 'table_14', 'table_2_10'),
    ('只含役牌混对对三暗的三杠专题', 'sankantsu', 'table_15', 'table_2_11'),
    ('只含役牌三暗混一色的对对专题', 'toitoi', 'table_16', 'table_2_12'),
    ('其他部分', None, 'table_17', 'table_2_13'),
)
CONDITIONS = frozenset(('riichi', 'double_riichi', 'ippatsu', 'chankan',
                        'rinshan', 'haitei', 'houtei', 'menzen_tsumo'))
VALUE_YAKU = frozenset(('haku', 'hatsu', 'chun', 'seat_wind', 'round_wind'))


def literals(path):
    result = {}
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = value
    return result


def topic_index(yaku):
    for index, (_, slug, _, _) in enumerate(TOPICS):
        if slug and slug in yaku:
            return index
    return 0 if yaku <= CONDITIONS else len(TOPICS) - 1


def histogram(rows):
    counts = Counter(row['han'] for row in rows)
    return [counts.get(han, 0) for han in range(21)]


def expanded_topic(path):
    data = literals(path)
    expanded = list(data['table'])
    # Seven pairs uses the explicit condition list instead of table_info.
    if 'fans_all' in data:
        for offset, families in enumerate(data['fans_all'], 1):
            for han, count in enumerate(data['table']):
                if han + offset < len(expanded):
                    expanded[han + offset] += count * len(families)
    else:
        for name, families in data.items():
            if not name.endswith('_info'):
                continue
            base = data[name[:-5]]
            for family in families:
                for han, count in enumerate(base):
                    if han + family['fan'] < len(expanded):
                        expanded[han + family['fan']] += count * family['num']
    if path.parent.name == '小三元专题':
        expanded = [value * 3 for value in expanded]
    return expanded


def compare(old, run):
    old = old.resolve()
    run = run.resolve()
    summary = json.loads((run / 'summary.json').read_text(encoding='utf-8'))
    if not summary['complete'] or summary['termination'] != 'unsat':
        raise ValueError('The selected snapshot is not complete')
    if summary['scope']['players'] != 4:
        raise ValueError('The manual comparison requires the four-player snapshot')
    for name, expected in summary['source_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Source differs from snapshot: ' + name)
    archive_check = verify_archive(run)
    records = [json.loads(line) for line in iter_record_lines(run, 'combinations.jsonl')]
    if len(records) != summary['combination_count']:
        raise ValueError('Record count disagrees with summary')
    if len({(r['closed'], frozenset(r['yaku'])) for r in records}) != len(records):
        raise ValueError('Duplicate combination in snapshot')
    tables = literals(old / 'cal_sum.py')
    grouped = defaultdict(list)
    for row in records:
        grouped[row['closed'], topic_index(set(row['yaku']))].append(row)
    topics = []
    for index, (name, _, closed_key, open_key) in enumerate(TOPICS):
        row = {'topic': name}
        for mode, closed, key in [('closed', True, closed_key), ('open', False, open_key)]:
            before = tables[key] if key else [0] * 21
            after = histogram(grouped[closed, index])
            row[mode] = {'old_count': sum(before), 'new_count': sum(after),
                         'delta': sum(after) - sum(before), 'old_histogram': before,
                         'new_histogram': after,
                         'delta_histogram': [b - a for a, b in zip(before, after)]}
        script = old / name / '辅助计算脚本.py'
        if script.is_file():
            expanded = expanded_topic(script)
            row['old_closed_topic_script_histogram'] = expanded
            row['old_closed_topic_script_count'] = sum(expanded)
        topics.append(row)
    totals = {}
    for mode, closed in [('closed', True), ('open', False)]:
        before = [sum(t[mode]['old_histogram'][han] for t in topics) for han in range(21)]
        after = histogram([r for r in records if r['closed'] == closed])
        expected = [summary[mode]['han_histogram'].get(str(han), 0) for han in range(21)]
        if after != expected or sum(after) != summary[mode]['count']:
            raise ValueError('Records disagree with summary: ' + mode)
        totals[mode] = {'old_count': sum(before), 'new_count': sum(after),
                        'delta': sum(after) - sum(before), 'old_histogram': before,
                        'new_histogram': after,
                        'delta_histogram': [b - a for a, b in zip(before, after)]}
    # Keep the historically identified subsets as diagnostics after corrections.
    iipeikou = [r for r in grouped[True, 11] if {'chanta', 'honitsu'} <= set(r['yaku'])]
    honroutou = [r for r in grouped[True, 3] if 'honitsu' in r['yaku']
                and 'sankantsu' not in r['yaku'] and len(VALUE_YAKU & set(r['yaku'])) >= 2]
    findings = {}
    for label, subset, index in [('iipeikou_chanta_honitsu', iipeikou, 11),
                                 ('honroutou_honitsu_multiple_value_yaku', honroutou, 3)]:
        delta = topics[index]['closed']['delta_histogram']
        findings[label] = {'count': len(subset), 'han_histogram': histogram(subset),
                           'histogram_explains_entire_topic_delta': histogram(subset) == delta,
                           'example': subset[0]}
    set_comparison = None
    manual_summary_path = old / 'results/summary.json'
    manual_files = []
    if manual_summary_path.is_file():
        manual_summary = json.loads(manual_summary_path.read_text(encoding='utf-8'))
        if manual_summary['scope']['players'] != 4 or manual_summary['scope']['dora'] != 0:
            raise ValueError('The normalized manual scope differs')
        if manual_summary['scope']['selection'] != summary['scope']['selection']:
            raise ValueError('The normalized manual selection rule differs')
        for name, digest in manual_summary['source_sha256'].items():
            if hashlib.sha256((old / name).read_bytes()).hexdigest() != digest:
                raise ValueError('Manual export source differs: ' + name)
        manual_archive = manual_summary_path.parent / manual_summary['archive']
        if hashlib.sha256(manual_archive.read_bytes()).hexdigest() != manual_summary['archive_sha256']:
            raise ValueError('Manual archive hash differs')
        manual_rows = json.loads(gzip.decompress(manual_archive.read_bytes()))['rows']
        def key(row):
            return row['closed'], tuple(sorted(row['yaku']))
        manual_by_key = {key(row): row for row in manual_rows}
        new_by_key = {key(row): row for row in records}
        if len(manual_by_key) != len(manual_rows) or len(manual_rows) != manual_summary['combination_count']:
            raise ValueError('Duplicate or missing manual combinations')
        only_manual = sorted(manual_by_key.keys() - new_by_key.keys())
        only_new = sorted(new_by_key.keys() - manual_by_key.keys())
        mismatch = [k for k in sorted(manual_by_key.keys() & new_by_key.keys())
                    if manual_by_key[k]['han'] != new_by_key[k]['han']]
        set_comparison = {
            'manual_count': len(manual_rows), 'new_count': len(records),
            'only_manual_count': len(only_manual), 'only_new_count': len(only_new),
            'han_mismatch_count': len(mismatch),
            'only_manual': [manual_by_key[k] for k in only_manual],
            'only_new': [new_by_key[k] for k in only_new],
            'han_mismatches': [{'manual': manual_by_key[k], 'new': new_by_key[k]} for k in mismatch],
            'source_and_archive_hashes_match': True,
            'same_complete_combination_sets': not only_manual and not only_new,
        }
        manual_files = [manual_summary_path, manual_archive]
    git_head = subprocess.run(['git', '-C', str(old), 'rev-parse', 'HEAD'],
                              check=True, capture_output=True, text=True).stdout.strip()
    files = [old / 'cal_sum.py', old / 'README.md', run / 'summary.json', run / 'records.zip']
    files.extend(sorted(old.glob('*/辅助计算脚本.py')))
    files.extend(manual_files)
    dirty = subprocess.run(['git', '-C', str(old), 'status', '--porcelain'],
                           check=True, capture_output=True, text=True).stdout
    return {'schema_version': 2,
            'comparison_kind': 'complete_sets_and_histograms' if set_comparison else 'histograms_and_selected_subsets',
            'old_repository': old.name, 'old_commit': git_head, 'new_scope': summary['scope'],
            'old_working_tree_modified': bool(dirty),
            'new_snapshot_complete': True, 'archive_check': archive_check,
            'sha256': {('old/' + p.relative_to(old).as_posix() if p.is_relative_to(old)
                        else 'new/' + p.relative_to(ROOT).as_posix()):
                       hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            'totals': totals, 'topics': topics, 'findings': findings,
            'set_comparison': set_comparison,
            'limitations': (['No normalized manual combination export was available.'] if not set_comparison else []) +
                           ['Theory model coverage is not proved by agreement between repositories.',
                            'No server or client cross-validation was performed.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('old_repository', type=Path)
    parser.add_argument('--run', type=Path, default=ROOT / 'results/full')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = compare(args.old_repository, args.run)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(payload, encoding='utf-8')
        print(args.output)
    else:
        print(payload, end='')


if __name__ == '__main__':
    main()
