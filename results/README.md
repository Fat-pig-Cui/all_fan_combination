# 已发布结果

> **2026-10-11已修正双立直与抢杠的永久振听遗漏。旧快照的21,179条组合见证和5,474条拒绝候选均重新检查，移除492种无效组合。当前求解器确认剩余约束无解，下面的快照已更新为20,687种组合。**

本目录保存2026-10-11修正后的四麻快照、独立的三麻完整枚举及离线算法对照结果。
它们不包含账户信息、在线牌谱或服务器返回数据。

| 文件 | 内容 |
|---|---|
| `full/REPORT.md` | 完成状态、逐番分布和验证边界 |
| `full/summary.json` | 20,687种组合、求解器版本、运行时间、复核来源与核心源码哈希 |
| `full/records.zip` | 四麻组合见证和拒绝记录的ZIP压缩包，约1.09 MiB |
| `full/archive.json` | 两个原始成员的SHA-256、字节数和记录数 |
| `full/audit.json` | 全部见证重新判役、去重和统计校验结果 |
| `sanma/REPORT.md` | 三麻18,861种、逐番分布、拔北与条件证书说明 |
| `sanma/summary.json` | 门清14,748／副露4,113、3张余牌立直门槛、规则指纹与 `unsat` |
| `sanma/records.zip` | 三麻18,861条见证与2,613条拒绝候选，约1.06 MiB |
| `sanma/archive.json`、`sanma/audit.json` | 三麻压缩成员摘要及全部见证复算结果 |
| `yakuman/REPORT.md`、`yakuman/summary.json` | 四麻／三麻自然役满复合集合、倍数分布和参考合集差异 |
| `yakuman/witnesses.jsonl` | 每个自然役满集合的一条可复核牌形见证 |
| `reference-check.json` | 22个四麻边界牌例的本地JavaScript计分对照，加1个非法过程拒绝检查 |
| `validation-sample.json` | 从修正后完整快照均匀抽取的200个牌例 |
| `reference-sample-check.json` | 上述200个牌例的本地算法对照 |
| `SHA256SUMS` | 上述文件的SHA-256摘要；路径相对仓库根目录 |

拒绝条数是候选见证数，不是“不可能的役组合”数。
一个见证不支持目标时，程序仍会查找其他支持同一目标的牌形。

压缩包内保留 `combinations.jsonl`（20,687条见证）和 `rejections.jsonl`（5,966条拒绝记录）。
共用规则配置实现后，四麻已重新判断全部候选并检查剩余约束，仍为20,687种；原始记录共36.53 MiB，压缩后约1.09 MiB。
三麻独立快照为18,861种，原始记录共32.91 MiB，压缩后约1.06 MiB。两种玩法不共用续算状态或规则指纹。
成员摘要与本次重新判定后的原始记录一致；ZIP使用固定成员顺序、时间和权限，避免文件时间变化影响重新打包。
复算工具可直接读取ZIP，不必手动解压。若需查看原始数据，可使用标准ZIP工具或：

```bash
python -m zipfile -e results/full/records.zip results/local-extracted
```

```bash
python tools/verify_snapshot.py
python audit_results.py results/full
python audit_results.py results/sanma
python tools/verify_yakuman.py results/yakuman
```

完整枚举耗时依机器和求解器状态而异。2026-10-10旧模型从零运行约64分钟；本次重新判定旧候选后求解剩余空间，约76秒，最终同样以当前模型的`unsat`确认完成。
CI只复算已有见证和校验快照，不宣称再次从零枚举。

三麻初次计算先读取四麻的26,653条牌形提示，实际重新判断79,175个候选状态并确认16,244个集合；随后三麻求解器额外确认2,617个集合，最终以`unsat`穷尽为18,861种。最后又按最终代码重新核对18,861条组合和2,613条拒绝候选，结果不变。初次搜索约489秒，最终复核约33秒；四麻只是搜索提示，不决定三麻结果。
三麻立直至少剩3张通常牌由用户确认；北拔宝牌不进入普通役或拆分择优。三麻与四麻的普通役集合对比：共有18,706，四麻独有1,981，三麻独有155，后者全部包含岭上开花。详细分类见[三麻与四麻普通役组合差异](../SANMA_COMPARISON.md)。

旧快照可从Git历史恢复至独立目录，摘要见当前汇总的`revalidation`。重新判定某个快照并检查当前模型剩余空间，可执行：

```bash
python tools/revalidate_snapshot.py results/full --output results/local-revalidated
```

工具重新计算所有组合与拒绝候选，不信任旧计分结果，也不会通过总数减法标记完成；超时或中断保留不完整状态。当前快照的机器复核记录说明实际检查量与终止原因。

新的运行请使用 `results/local-run` 等独立目录，默认被Git忽略。
两仓库的历史对比报告和数据已移至 [对比归档](../archive/README.md)。
枚举及续算使用未压缩的JSONL工作目录；已发布ZIP用于分发与复算。
完整性以 `complete=true` 和 `termination="unsat"` 为准，理论边界见 [THEORY.md](../THEORY.md)。
