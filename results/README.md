# 已发布结果

本目录保存2026-10-10的理论枚举快照及离线算法对照结果。
它们不包含账户信息、在线牌谱或服务器返回数据。

| 文件 | 内容 |
|---|---|
| `full/REPORT.md` | 完成状态、逐番分布和验证边界 |
| `full/summary.json` | 21,179种组合、求解器版本、运行时间及核心源码哈希 |
| `full/records.zip` | 组合见证和拒绝记录的ZIP压缩包，约1.05 MiB |
| `full/archive.json` | 两个原始成员的SHA-256、字节数和记录数 |
| `full/audit.json` | 全部见证重新判役、去重和统计校验结果 |
| `reference-check.json` | 23个边界牌例的本地JavaScript算法对照 |
| `validation-sample.json` | 从运行中的已确认见证均匀抽取的200个牌例 |
| `reference-sample-check.json` | 上述200个牌例的本地算法对照 |
| `SHA256SUMS` | 上述文件的SHA-256摘要；路径相对仓库根目录 |

拒绝条数是候选见证数，不是“不可能的役组合”数。
一个见证不支持目标时，程序仍会查找其他支持同一目标的牌形。

压缩包内保留 `combinations.jsonl`（21,179条见证）和 `rejections.jsonl`（5,474条拒绝记录）。
原始记录共34.12 MiB，压缩后约1.05 MiB，体积减少约96.93%。
原始内容摘要与压缩前一致；ZIP使用固定成员顺序、时间和权限，避免文件时间变化影响重新打包。
复算工具可直接读取ZIP，不必手动解压。若需查看原始数据，可使用标准ZIP工具或：

```bash
python -m zipfile -e results/full/records.zip results/local-extracted
```

```bash
python tools/verify_snapshot.py
python audit_results.py results/full
```

完整枚举耗时依机器和求解器状态而异；本基线运行约64分钟。
CI只复算已有见证和校验快照，不宣称再次从零证明穷尽。

新的运行请使用 `results/local-run` 等独立目录，默认被Git忽略。
枚举及续算使用未压缩的JSONL工作目录；已发布ZIP用于分发与复算。
完整性以 `complete=true` 和 `termination="unsat"` 为准，理论边界见 [THEORY.md](../THEORY.md)。
