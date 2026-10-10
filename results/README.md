# 已发布结果

本目录保存2026-10-10的理论枚举快照及离线算法对照结果。
它们不包含账户信息、在线牌谱或服务器返回数据。

| 文件 | 内容 |
|---|---|
| `full/REPORT.md` | 完成状态、逐番分布和验证边界 |
| `full/summary.json` | 21,179种组合、求解器版本、运行时间及核心源码哈希 |
| `full/combinations.jsonl` | 每种组合一条可复算见证，约29 MiB |
| `full/rejections.jsonl` | 5,474条被拒绝的候选见证，约6 MiB |
| `full/audit.json` | 全部见证重新判役、去重和统计校验结果 |
| `reference-check.json` | 23个边界牌例的本地JavaScript算法对照 |
| `validation-sample.json` | 从运行中的已确认见证均匀抽取的200个牌例 |
| `reference-sample-check.json` | 上述200个牌例的本地算法对照 |
| `SHA256SUMS` | 上述文件的SHA-256摘要；路径相对仓库根目录 |

拒绝条数是候选见证数，不是“不可能的役组合”数。
一个见证不支持目标时，程序仍会查找其他支持同一目标的牌形。

```bash
python tools/verify_snapshot.py
python audit_results.py results/full
```

完整枚举耗时依机器和求解器状态而异；本基线运行约64分钟。
CI只复算已有见证和校验快照，不宣称再次从零证明穷尽。

新的运行请使用 `results/local-run` 等独立目录，默认被Git忽略。
完整性以 `complete=true` 和 `termination="unsat"` 为准，理论边界见 [THEORY.md](../THEORY.md)。
