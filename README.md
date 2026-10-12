# all_fan_combination

**雀魂四人／三人段位场普通役组合的理论枚举与独立Python判役。**

A standalone Python riichi evaluator and witness-based enumerator for ordinary yaku combinations in four-player and three-player ranked Mahjong Soul rules.

从合法和牌结构出发，计算完整役集合，再按 **门清状态＋役种集合** 去重。
本项目独立运行，不读取或修改 [all_yaku_combos](https://github.com/Fat-pig-Cui/all_yaku_combos) 的人工组合表，不需要雀魂服务器或牌谱验证。
这是非官方的理论研究工具。采用 [MIT许可证](LICENSE)。

## 已完成的枚举

2026-10-11已修正双立直与普通抢杠的永久振听遗漏。旧快照的21,179条组合见证与5,474条拒绝候选均重新判定，移除492种无效组合；当前求解器检查剩余约束并返回 `unsat`。
修正后的理论模型共 **20,687** 种组合：门清 **15,270**，副露 **5,417**。逐番分布和全部见证复算结果见
[结果报告](results/full/REPORT.md)，机器状态见 [summary.json](results/full/summary.json)。

三麻完整枚举为 **18,861种**：门清 **14,748种**，副露 **4,113种**，当前求解器返回 `unsat`，全部见证已复算。结果与逐番分布见 [三麻报告](results/sanma/REPORT.md)，完整配置见 [三麻汇总](results/sanma/summary.json)。
牌组为108张，禁止吃，北为客风，拔北补牌可计岭上，立直至少剩3张通常牌；三麻不直接继承四麻计数。实现与存在性构造边界见 [三麻方案](SANMA_DESIGN.md)。

| 配置 | 门清 | 副露 | 合计 |
|---|---:|---:|---:|
| 四麻 | 15,270 | 5,417 | 20,687 |
| 三麻 | 14,748 | 4,113 | 18,861 |

按完整役集合比较，两种玩法共有18,706种，四麻独有1,981种，三麻独有155种。三麻独有项全部包含岭上；拔北使若干四麻无法开杠的牌形也能补牌和牌。

## 自然役满复合分析

自然役满单独按“完整役满集合”枚举，不混入上面的普通役组合计数。当前四麻得到99个集合，三麻得到99个集合；四麻数量与已修订的参考合集一致。其中包括开放杠形的“四杠子＋大四喜＋字一色”：四种风牌各开杠、以另一张字牌作雀头，至少一组杠为明杠，因而不会额外成立四暗刻单骑。完整倍数分布、每个集合的牌形见证以及三麻结果见 [自然役满分析报告](results/yakuman/REPORT.md) 和 [机器汇总](results/yakuman/summary.json)。

这次计数不含宝牌与自然役满；13番以上普通役集合保留。
完整性限于本文和 `THEORY.md` 定义的有限结构模型及条件可达性构造，不是所有牌山与对手操作的逐步穷举。
四麻全部20,687条当前见证已重新判役与检查条件。23个四麻边界牌例中22个比较计分、1个检查非法过程应被拒绝；另200个从四麻快照抽取的牌例与本地JavaScript参考算法计分对照通过。
规则注意事项、已修正错误和其余验证边界见 [规则审查记录](RULE_AUDIT.md)。
单元测试、文件／源码哈希和全部见证复算由 [GitHub Actions](.github/workflows/checks.yml) 配置执行。

与人工推导仓库 `all_yaku_combos` 的完整役集合、番数和专题分布已逐条对齐。
两次对比报告与机器数据保存在 [对比归档](archive/README.md)，用于记录本次修正过程。

## 安装与运行

Python 3.9 或更新版本。独立判役器和结果复算只使用标准库；枚举器和完整测试额外使用 Z3。
所有命令从仓库根目录运行。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell可用 `python -m venv .venv` 创建环境，激活命令为 `.\.venv\Scripts\Activate.ps1`。

```bash
# 独立判役：手牌必须是和牌前，和牌张另列
python calc_fan.py examples/pinfu_sanshoku.json
python calc_fan.py examples/three_ankans.json
python calc_fan.py examples/sanma_nuki_chiitoitsu.json
python calc_fan.py examples/sanma_nuki_pinfu.json
python calc_fan.py examples/sanma_rob_north.json

# 校验已发布文件和核心源码哈希，再复算全部见证
python tools/verify_snapshot.py
python audit_results.py results/full
python audit_results.py results/sanma
python tools/verify_yakuman.py results/yakuman

# 运行测试
python -m unittest discover -s tests -v
```

### 从零枚举与续算

`results/full/` 与 `results/sanma/` 分别保存四麻、三麻快照。新的枚举使用独立目录，避免与基线混用。
从零运行可能耗时较长；2026-10-10旧模型运行约64分钟。2026-10-11复核重新判定旧候选，再求解当前模型的剩余空间，约76秒；两者不是相同的运行方式，耗时随机器和求解器状态变化。
本次三麻先重新判断四麻牌形提示，再搜索三麻剩余空间，约489秒；最终输入检查完善后又复核全部三麻候选，仍为18,861种。这些时间不能等同于三麻从零求解的耗时。

```bash
# 完整枚举：只有求解器返回 unsat 才标记 complete=true
python enumerate_combinations.py --output results/local-run

# 三麻从零枚举
python enumerate_combinations.py --players 3 --output results/local-sanma

# 三麻加速：重新判断四麻牌形提示，再穷尽三麻剩余空间
python tools/enumerate_sanma.py --output results/local-sanma-seeded

# 限量检查：退出码3，明确标记不完整，不作为最终总数
python enumerate_combinations.py --output results/local-sample --limit 100

# 已有结果需要显式续算；源代码改变时拒绝混用旧结果
python enumerate_combinations.py --output results/local-run --resume

# 对保存的每一条见证重新判役、检查暗杠听牌和去重
python audit_results.py results/local-run

# 枚举停止后，复算并生成同目录的 REPORT.md 和 audit.json
python tools/report_results.py results/local-run

# 重新枚举自然役满（默认同时生成四麻和三麻）
python tools/analyze_yakuman.py --players all
```

`--timeout-ms` 设置每次求解的时间上限；默认0不设上限。超时返回 `unknown`，不会伪装成穷举完成。
`--max-models` 限制候选数，`--limit` 限制已接受组合数，二者都用于诊断。
重复使用已有输出目录必须带 `--resume`，避免误覆盖。
枚举命令退出码：0表示完成，3表示限量／超时／中断等不完整运行，2表示输入或参数错误。
对未压缩的已完成运行目录使用 `--resume` 会返回保存的汇总，不会重新执行完整枚举。
枚举输出及续算使用JSONL；已发布ZIP快照用于读取与复算，不作为枚举输出目录。
如需将快照作为独立工作目录，应先将压缩包解压到新目录，并复制对应的 `summary.json`。

## 统计口径

| 项目 | 定义 |
|---|---|
| 玩法 | 独立的雀魂四麻／三麻段位配置；场风取东、南、西 |
| 普通役 | 30种，白、发、中以及门风、场风分别编码 |
| 门清与副露 | 分开统计；暗杠保持门清 |
| 自然役满 | 判定全部自然役满及其上位形式，成立时排除普通役组合 |
| 累计役满 | 普通役组合达到13番以上仍保留，不按支付等级合并 |
| 宝牌 | 不进入组合，也不参与枚举中的拆分择优；独立判役接口可另给 `dora` 总番数 |
| 拆分择优 | 普通手比较 `(基本点, 原始番数, 符)`，保留完全同分同番同符的全部役集合；自然役满优先 |
| 无役 | 不计入结果；宝牌不能独立赋予和牌资格 |
| 流局满贯 | 荒牌流局事件，不属于这些14张和牌型的组合 |
| 三麻 | 108张、禁止吃、北拔独立计操作；单独保存结果和规则指纹 |

这里统计的是满足已编码规则的**完整计分役集合**，不是手牌种数、出现概率或支付金额种数。
例如小三元会自动包含相应两种三元牌役；二杯口不会另外叠加一杯口。
七对子与一般形重叠时，不能把两种解释的役拼接，也不能保留输给更高计分解释的七对子组合。

## 文件与执行流程

| 文件 | 作用 |
|---|---|
| `calc_fan.py` | 独立Python判役器；枚举全部拆分、和牌张归属、普通役、自然役满、符与基本点 |
| `rules.py` | 四麻／三麻的牌组、座次、吃牌、立直余牌门槛与补牌容量配置 |
| `shape_solver.py` | 生成四面子＋雀头或七对子结构；编码每种牌最多四张、开放／杠状态、风位及役的定义 |
| `reachability.py` | 条件役的构造证书；逐次验证立直后暗杠必须使用第四张且保持完整听牌集合 |
| `enumerate_combinations.py` | 求解候选、独立判役、排除错误见证、投影去重、流式写结果与进度 |
| `audit_results.py` | 不依赖求解器，逐条复算已保存的见证与统计 |
| `tools/report_results.py` | 对停止后的结果检查源码哈希、复算全部见证并生成中文统计报告 |
| `tools/verify_snapshot.py` | 不依赖Z3，校验已发布文件与核心源码的SHA-256 |
| `tools/pack_results.py` | 将原始见证与拒绝记录压缩为ZIP，保留原始内容摘要 |
| `tools/revalidate_snapshot.py` | 重新判定旧快照的所有候选，再由当前求解器检查剩余空间；只有 `unsat` 标记完整 |
| `tools/enumerate_sanma.py` | 将既有四麻牌形作为三麻搜索提示；重新判役、检查证书后继续求解全部剩余集合 |
| `tools/analyze_yakuman.py` | 独立枚举自然役满复合集合，并生成四麻／三麻牌形见证与差异报告 |
| `tools/verify_yakuman.py` | 重新判定自然役满见证，检查役满组合、倍数及结果统计 |
| `result_records.py` | 统一读取本地JSONL和已发布ZIP记录 |
| `tests/` | 判役边界、约束与Python方程一致性、条件可达性、输出／续算检查 |
| `tools/check_reference.py` | 可选的本地JavaScript算法对照，仅用于开发核对 |

核心流程：

```text
合法面子／雀头或七对子结构＋和牌张＋风位＋条件
  → 结构模型提出尚未出现的完整役集合
  → Python独立枚举这个手牌的全部合法拆分并择优
  → 验证立直后暗杠的完整听牌集合
  → 保存见证，排除这个已确认的“门清性＋役集合”投影
  → 求解下一组，直到 unsat
```

这相当于在有限牌形空间中按目标役集合查找见证，省去大量产生同一结果的重复牌面。
它不从旧仓库的两两冲突表生成候选，也不以旧总数作为终止条件。

## 条件役的理论可达性

采用存在性构造，不模拟随机概率，也不展开所有牌山排列：

- 普通立直可以发生在已有暗杠之后；一发窗口内不再完成鸣牌或杠。
- 双立直在首次舍牌宣告，此前无鸣牌／杠；自己的后续暗杠必须逐次保持完整听牌集合。
- 四麻立直后岭上须有合法的最后暗杠；三麻也可用最后拔北补牌，记录新摸北、响应时序与不变的听牌。
- 抢杠要求对手有碰出的三张，和牌张是第四张，因此和牌者完成手牌中该牌只能有一张。
- 普通立直一发抢杠使用宣告立直前已有的对手碰；被抢的加杠尚未成立。
- 雀魂振听按舍牌判定：暗杠、加杠、拔北的牌不纳入舍张振听，放过抢杠／抢北响应也不会新增振听；已有振听仍限制这些荣和方式。完成的杠或拔北仍中断一发。
- 双立直不能与普通抢加杠复合：对手碰只能发生在宣告之后，放过形成该碰的原始待牌舍牌会导致立直后振听，牌被碰走不撤销见逃。造成振听的不是后来的加杠响应。结构约束、标准形判役和条件证书均拒绝；国士抢暗杠仍可判定，但不属于普通役枚举。
- 海底只能是最后一次通常摸牌；岭上不与海底叠加。
- 立直余牌门槛四麻为4张、三麻为3张；各自在无人鸣牌／杠／拔北中断的一巡内可构造普通立直一发海底。一发河底不可构造。
- 双立直一发发生在首巡附近，不可能同时到海底。
- 一人独自四杠属于自然役满，已排除；见证无需额外安排其他人的杠，因而不会提前触发四杠散了。

`condition_certificate` 保存这些构造规则及必要的实际听牌数据。
这是在上述规则与构造引理下的可达性模型；它没有伪称逐张验证整个136张牌山和所有对手的完整摸打记录。
若将来修改立直余牌限制或鸣牌中断规则，需要同时修改模型、构造证书与测试，并重新枚举。

## 独立判役输入

```json
{
  "hand": "56s 55p",
  "win": "4s",
  "tsumo": true,
  "seat": "1z",
  "round_wind": "1z",
  "riichi": 0,
  "ippatsu": false,
  "event": "rinshan",
  "melds": [
    {"kind": "ankan", "tiles": "1111m"},
    {"kind": "ankan", "tiles": "2222p"},
    {"kind": "ankan", "tiles": "3333s"}
  ]
}
```

`hand` 只包括和牌前未固定的手牌，长度为 `13 - 3×固定面子数`；杠子在 `melds` 中使用实际四张。
固定面子类型为 `chi`、`pon`、`minkan`、`kakan`、`ankan`。
`riichi` 为0／1／2，`event` 为 `none`／`chankan`／`rinshan`／`haitei`／`houtei`。
`first_turn=true` 可用于天和／地和判定；枚举普通役集合时不使用该状态。
`dora` 可显式提供所有悬赏牌的总番数；脚本不根据红牌记号或指示牌自动推导它。

`players` 默认4；三麻显式设为3。`north_count` 是已经拔出的北数量（0至4），与手牌及杠中的北合计不超过四张，不自动加入宝牌番数。
三麻拔北补牌输入 `event="rinshan"`、`win_source="north_replacement"`、`north_count>=1`；杠后补牌可用 `win_source="kan_replacement"`。
抢北输入 `win_source="north_ron"`、`win="4z"`、荣和及 `event="none"`，不会自动提供抢杠役。
可选 `live_tiles` 表示宣告杠／拔北时通常山余牌，少于2张时拒绝该操作；此接口不是完整牌谱校验。

输出包括普通役ID、名称、番数、门清性、符、基本点、自然役满倍数，以及被选择的拆分和和牌张归属。
红5按普通5进行结构和四张上限检查；悬赏番必须单独给出。

## 输出与完成判据

- `combinations.jsonl`：每种组合一行，包含唯一标识、番数、和牌前手牌、固定面子、条件和选中的解释。
- `rejections.jsonl`：被更高计分解释覆盖或立直后暗杠改变听牌的候选，记录拒绝理由和实际计分结果。
- `summary.json`：门清／副露总数、逐番分布、源代码哈希、求解器版本和完成状态。

只有 `complete=true` 且 `termination="unsat"` 表示当前有限理论模型已穷尽。
限量、超时和人工中断都保存已确认见证，但 `complete=false`。
每种组合有一条实际牌形见证；暂时没找到见证不等于组合不可能，只有最终穷尽才完成排除。
原始源代码哈希改变后不能直接续算，以免把不同模型的结果混在一起。
公开快照将两份大记录文件分别存放于 `results/full/records.zip` 和 `results/sanma/records.zip`；复算直接读取压缩包，无需解压。
压缩包及解压后成员分别有摘要校验，原始内容保持一致。四麻约36.53 MiB压缩为1.09 MiB，三麻约32.91 MiB压缩为1.06 MiB。
公开快照与文件摘要见 [results/README.md](results/README.md)；本地新运行目录默认被Git忽略。

## 参考算法与验证边界

`calc_fan.py` 独立编写，参考 `majsoul-replay-editor` 的 `calcFan.js` 立直分支与 `calcSudian` 的比较规则。
没有移植川麻、国标、古役、活动规则、全局数据或JavaScript运行时。
同分不同役保留全部择优解释，避免理论结果依赖JavaScript DFS的首次命中顺序；自然役满在所有解释中优先。
参考快照、算法差异及来源记录见 `PROVENANCE.md`。

可选的本地算法对照：

```bash
python tools/check_reference.py --core /path/to/replay-editor/core
python tools/check_reference.py --core /path/to/replay-editor/core \
  --cases results/validation-sample.json --output results/local-sample-check.json
```

这项检查只执行本地参考计算器，与服务器或客户端实测无关；枚举及独立判役不依赖该参考路径。
需要自行取得参考源码及Node.js。`--core` 必须显式指定；默认报告写入被Git忽略的
`results/local-reference-check.json`，不覆盖仓库附带的对照报告。

规则反例、算法变更和结果更新流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。
