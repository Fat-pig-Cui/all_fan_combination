# 历史对比归档

## 2026-10-11：四麻普通役组合对齐

人工推导的 `all_yaku_combos` 与牌形见证枚举的 `all_fan_combination` 已完成逐集合对齐：均为20,687种，门清15,270种、副露5,417种；完整役集合、番数和逐番／专题分布均无差异。

| 归档文件 | 内容 |
|---|---|
| [修正前报告](2026-10-11-alignment/COMPARISON_INITIAL.md) | 初次发现的差异、已解释部分及当时待研究项 |
| [修正后报告](2026-10-11-alignment/COMPARISON.md) | 剩余九项差异的结构推导、修正结果及验证边界 |
| [修正前数据](2026-10-11-alignment/comparison-initial.json) | 修正前统计、见证子集与文件摘要 |
| [修正后数据](2026-10-11-alignment/comparison.json) | 完整集合比较、逐番分布、专题统计与文件摘要 |

归档只覆盖四麻普通役、宝牌为0、不计自然役满的理论口径，不是服务器验证，也不代表三麻结果。
旧仓库的具体牌例和规则修正保留在其 [CORRECTIONS.md](https://github.com/Fat-pig-Cui/all_yaku_combos/blob/main/CORRECTIONS.md)。

归档文件保存历史结论，不随后续运行覆盖。需复算时，从本仓库根目录执行：

```bash
python tools/compare_results.py ../all_yaku_combos --output results/local-comparison.json
```
