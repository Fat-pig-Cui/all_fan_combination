# 古役扩展

本目录在 `all_fan_combination` 的段位场普通役枚举基础上，增加雀魂古役规则的理论枚举。古役扩展与主目录的四麻、三麻段位结果分开保存，不改变默认计番器和段位场结果。

## 已发布结果

| 结果 | 门清 | 副露 | 合计 |
| :---: | :---: | :---: | :---: |
| 四麻段位基线 | 15,270 | 5,417 | 20,687 |
| 四麻开启古役 | 34,737 | 23,068 | 57,805 |
| 四麻新增 | 21,020 | 17,651 | 38,671 |
| 三麻段位基线 | 14,748 | 4,113 | 18,861 |
| 三麻开启古役 | 33,148 | 15,029 | 48,177 |
| 三麻新增 | 19,896 | 10,916 | 30,812 |

四麻报告见 [ORDINARY_DELTA.md](ORDINARY_DELTA.md)，三麻报告见 [SANMA_ORDINARY_DELTA.md](SANMA_ORDINARY_DELTA.md)。两份报告中的“含某古役”表用于观察覆盖范围，按“恰好包含哪些古役”分组的表用于互斥相加。四麻的 47 类互斥分组共 38,671 种。

完整新增、消失集合和机器可读分组表分别保存在 [ordinary_delta.zip](ordinary_delta.zip) 与 [sanma_ordinary_delta.zip](sanma_ordinary_delta.zip)。压缩包中的 CSV 记录示例牌型、和牌条件和门清／副露状态；暗杠使用五张相同数字的文档显示法，和牌张独立写在手牌之后。

## 规则范围

古役模型在四麻或三麻段位规则上额外启用雀魂古役。普通差量统计包含燕返、杠振、十二落抬、五门齐、三连刻、一色三同顺、一筒摸月和九筒捞鱼；古役役满仍作为普通结果的排除条件处理。宝牌不进入组合，普通役达到 13 番以上仍按完整役集合计数，自然役满优先于普通役。

三麻额外使用三麻牌组、禁止吃、拔北和拔北岭上补牌；三麻报告中的四麻结论不能直接移植。三麻立直的通常牌山门槛为 3 张，四麻为 4 张。支付层的三麻自摸损不改变组合键，因此没有在差量中重复计入。

古役搜索仍沿用主项目的三层结构：先生成牌型和声明状态，再由独立计番器遍历全部合法分解和和牌张归属，最后检查立直、暗杠、岭上、抢杠、燕返、杠振等条件事件。只有完整计分集合通过择优和过程检查后才进入结果。

## 复算

古役独立计番器位于 [ordinary](ordinary/)，其 `rules.py`、`calc_fan.py` 和 `shape_solver.py` 不覆盖主目录同名模块。四麻分片驱动在 [enumerate_ordinary_sharded.py](enumerate_ordinary_sharded.py)，三麻驱动在 [enumerate_sanma_delta.py](enumerate_sanma_delta.py)。

从仓库根目录创建环境后运行：

```sh
python3 -m venv .venv-guyi
.venv-guyi/bin/python -m pip install -r guyi/ordinary/requirements.txt

# 运行四麻古役分片搜索到新的本地目录
.venv-guyi/bin/python guyi/enumerate_ordinary_sharded.py \
  --output guyi/ordinary/results_reproduced

# 运行三麻古役搜索到新的本地目录
.venv-guyi/bin/python guyi/enumerate_sanma_delta.py \
  --output-root guyi/ordinary/results_sanma_reproduced --mode ancient
```

已有发布压缩包可直接用于审阅，不需要解压；重新运行应使用新目录。`--resume` 只允许源文件哈希和搜索配置保持一致的检查点。限制模型数或中途停止的结果不能作为最终计数。

根目录的 [PAPER_GUYI.md](../PAPER_GUYI.md) 介绍古役差量的建模、投影、排除和完成性判据。主项目普通役的算法论文仍是 [PAPER.md](../PAPER.md)。古役役满排除规则由当前计番器和回归测试共同验证，复算入口只使用当前快照。
