# 已发布结果

> **2026-10-11已修正双立直与抢杠的永久振听遗漏。旧快照的21,179条组合见证和5,474条拒绝候选均重新检查，移除492种无效组合。当前求解器确认剩余约束无解，下面的快照已更新为20,687种组合。**

本目录保存2026-10-11修正后的理论枚举快照及离线算法对照结果。
它们不包含账户信息、在线牌谱或服务器返回数据。

| 文件 | 内容 |
|---|---|
| `full/REPORT.md` | 完成状态、逐番分布和验证边界 |
| `full/summary.json` | 20,687种组合、求解器版本、运行时间、复核来源与核心源码哈希 |
| `full/records.zip` | 组合见证和拒绝记录的ZIP压缩包，约1.02 MiB |
| `full/archive.json` | 两个原始成员的SHA-256、字节数和记录数 |
| `full/audit.json` | 全部见证重新判役、去重和统计校验结果 |
| `reference-check.json` | 22个边界牌例的本地JavaScript计分对照，加1个非法过程拒绝检查 |
| `validation-sample.json` | 从修正后完整快照均匀抽取的200个牌例 |
| `reference-sample-check.json` | 上述200个牌例的本地算法对照 |
| `SHA256SUMS` | 上述文件的SHA-256摘要；路径相对仓库根目录 |

拒绝条数是候选见证数，不是“不可能的役组合”数。
一个见证不支持目标时，程序仍会查找其他支持同一目标的牌形。

压缩包内保留 `combinations.jsonl`（20,687条见证）和 `rejections.jsonl`（5,966条拒绝记录）。
原始记录共33.52 MiB，压缩后约1.02 MiB，体积减少约96.94%。
成员摘要与本次重新判定后的原始记录一致；ZIP使用固定成员顺序、时间和权限，避免文件时间变化影响重新打包。
复算工具可直接读取ZIP，不必手动解压。若需查看原始数据，可使用标准ZIP工具或：

```bash
python -m zipfile -e results/full/records.zip results/local-extracted
```

```bash
python tools/verify_snapshot.py
python audit_results.py results/full
```

完整枚举耗时依机器和求解器状态而异。2026-10-10旧模型从零运行约64分钟；本次重新判定旧候选后求解剩余空间，约76秒，最终同样以当前模型的`unsat`确认完成。
CI只复算已有见证和校验快照，不宣称再次从零枚举。

旧快照可从Git历史恢复至独立目录，摘要见当前汇总的`revalidation`。重新判定某个快照并检查当前模型剩余空间，可执行：

```bash
python tools/revalidate_snapshot.py results/full --output results/local-revalidated
```

工具重新计算所有组合与拒绝候选，不信任旧计分结果，也不会通过总数减法标记完成；超时或中断保留不完整状态。当前快照的机器复核记录说明实际检查量与终止原因。

新的运行请使用 `results/local-run` 等独立目录，默认被Git忽略。
两仓库的历史对比报告和数据已移至 [对比归档](../archive/README.md)。
枚举及续算使用未压缩的JSONL工作目录；已发布ZIP用于分发与复算。
完整性以 `complete=true` 和 `termination="unsat"` 为准，理论边界见 [THEORY.md](../THEORY.md)。
