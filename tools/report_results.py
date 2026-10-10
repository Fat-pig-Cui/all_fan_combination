#!/usr/bin/env python3
"""Audit a stopped enumeration and generate a human-readable results report."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_results import audit
from result_records import ARCHIVE_NAME


def report(directory: Path):
    summary = json.loads((directory / 'summary.json').read_text())
    if summary['termination'] == 'running':
        raise ValueError('Enumeration is still running; wait for its final checkpoint')
    root = Path(__file__).resolve().parents[1]
    for name, digest in summary['source_sha256'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Source differs from enumeration snapshot: ' + name)
    checked = audit(directory)
    checked['source_hashes_match'] = True
    (directory / 'audit.json').write_text(json.dumps(checked, ensure_ascii=False, indent=2) + '\n')
    complete = summary['complete'] and summary['termination'] == 'unsat'
    status = '已穷尽当前理论模型' if complete else '尚未穷尽，只是已确认组合的下界'
    lines = [
        '# 四麻普通役组合枚举结果', '',
        f"状态：**{status}**。停止原因：`{summary['termination']}`。", '',
        f"已确认 **{summary['combination_count']:,}** 种组合：门清 **{summary['closed']['count']:,}**，副露 **{summary['open']['count']:,}**。", '',
        '计数单位为“门清性＋完整计分役集合”，不区分手牌、符数或支付金额。',
        '不计宝牌和自然役满；保留13番以上普通役集合。场风包括东、南、西。',
        '普通手按基本点、原始番数、符择优，完全同分同番同符的不同役集合均保留。', '',
        '## 逐番分布', '', '| 番数 | 门清 | 副露 | 合计 |', '|---:|---:|---:|---:|',
    ]
    closed = summary['closed']['han_histogram']
    opened = summary['open']['han_histogram']
    for han in sorted(set(closed) | set(opened), key=int):
        a, b = closed.get(han, 0), opened.get(han, 0)
        lines.append(f'| {han} | {a:,} | {b:,} | {a + b:,} |')
    records_note = ('原始记录和拒绝记录保存在同目录的 `records.zip` 中；复算可直接读取压缩包，无需解压。'
                    if (directory / ARCHIVE_NAME).exists() and not (directory / 'combinations.jsonl').exists()
                    else '原始记录见同目录的 `combinations.jsonl`，拒绝记录见 `rejections.jsonl`。')
    lines.extend([
        f"| 合计 | {summary['closed']['count']:,} | {summary['open']['count']:,} | {summary['combination_count']:,} |", '',
        '## 验证与证据边界', '',
        f"- 全部 {checked['witnesses_checked']:,} 条见证重新判役通过，未发现重复组合，逐番汇总一致。",
        '- 核心源代码哈希与运行快照一致。',
        '- 暗杠听牌限制逐条复算；其他条件役采用文档中的存在性构造引理。',
        '- 没有逐张模拟全部牌山和所有对手操作，也没有执行雀魂服务器／客户端验证。',
        '- 完成性限于 `THEORY.md` 定义的有限模型；修改规则、宝牌择优或三麻配置须重新枚举。', '',
        '## 复算', '', '```bash',
        f'python3 audit_results.py {directory.as_posix()}', '```', '',
        records_note + '机器汇总见 `summary.json`。',
        '本报告由 `tools/report_results.py` 根据汇总和重新计算结果生成。', '',
    ])
    target = directory / 'REPORT.md'
    target.write_text('\n'.join(lines))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        print(report(args.directory))
    except ValueError as error:
        parser.exit(2, str(error) + '\n')


if __name__ == '__main__':
    main()
