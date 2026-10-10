# all_fan_combination

**雀魂四人段位场普通役组合的理论枚举与独立Python判役。**

A standalone Python riichi evaluator and a witness-based enumerator for ordinary yaku combinations in four-player ranked Mahjong Soul rules.

从合法和牌结构出发，计算完整役集合，再按 **门清状态＋役种集合** 去重。
本项目独立运行，不读取或修改 `all_yaku_combos` 的人工组合表，不需要雀魂服务器或牌谱验证。
这是非官方的理论研究工具。采用 [MIT许可证](LICENSE)。

## 已完成的枚举

2026-10-10 的完整运行返回 `unsat`，当前理论模型共 **21,179** 种组合：
门清 **15,762**，副露 **5,417**。逐番分布和全部见证复算结果见
[结果报告](results/full/REPORT.md)，机器状态见 [summary.json](results/full/summary.json)。

这次计数不含宝牌与自然役满；13番以上普通役集合保留。
完整性限于本文和 `THEORY.md` 定义的有限结构模型及条件可达性构造，不是所有牌山与对手操作的逐步穷举。
全部21,179条见证已复算；23个边界牌例和200个生成牌例与本地JavaScript参考算法对照通过。
单元测试、文件／源码哈希和全部见证复算由 [GitHub Actions](.github/workflows/checks.yml) 配置执行。

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

# 校验已发布文件和核心源码哈希，再复算全部见证
python tools/verify_snapshot.py
python audit_results.py results/full

# 运行测试
python -m unittest discover -s tests -v
```

### 从零枚举与续算

`results/full/` 是仓库附带的已完成快照。新的枚举使用独立目录，避免与基线混用。
完整运行可能耗时较长；2026-10-10基线运行约64分钟，时间随机器和求解器状态变化。

```bash
# 完整枚举：只有求解器返回 unsat 才标记 complete=true
python enumerate_combinations.py --output results/local-run

# 限量检查：退出码3，明确标记不完整，不作为最终总数
python enumerate_combinations.py --output results/local-sample --limit 100

# 已有结果需要显式续算；源代码改变时拒绝混用旧结果
python enumerate_combinations.py --output results/local-run --resume

# 对保存的每一条见证重新判役、检查暗杠听牌和去重
python audit_results.py results/local-run

# 枚举停止后，复算并生成同目录的 REPORT.md 和 audit.json
python tools/report_results.py results/local-run
```

`--timeout-ms` 设置每次求解的时间上限；默认0不设上限。超时返回 `unknown`，不会伪装成穷举完成。
`--max-models` 限制候选数，`--limit` 限制已接受组合数，二者都用于诊断。
重复使用已有输出目录必须带 `--resume`，避免误覆盖。
枚举命令退出码：0表示完成，3表示限量／超时／中断等不完整运行，2表示输入或参数错误。
对已完成目录使用 `--resume` 会返回保存的汇总，不会重新执行完整枚举。

## 统计口径

| 项目 | 定义 |
|---|---|
| 玩法 | 雀魂四人段位规则；包括合法延长场，场风取东、南、西 |
| 普通役 | 30种，白、发、中以及门风、场风分别编码 |
| 门清与副露 | 分开统计；暗杠保持门清 |
| 自然役满 | 判定全部自然役满及其上位形式，成立时排除普通役组合 |
| 累计役满 | 普通役组合达到13番以上仍保留，不按支付等级合并 |
| 宝牌 | 不进入组合，也不参与枚举中的拆分择优；独立判役接口可另给 `dora` 总番数 |
| 拆分择优 | 普通手比较 `(基本点, 原始番数, 符)`，保留完全同分同番同符的全部役集合；自然役满优先 |
| 无役 | 不计入结果；宝牌不能独立赋予和牌资格 |
| 流局满贯 | 荒牌流局事件，不属于这些14张和牌型的组合 |
| 三麻 | 未混入本模型；以后必须作为独立规则配置实现 |

这里统计的是满足已编码规则的**完整计分役集合**，不是手牌种数、出现概率或支付金额种数。
例如小三元会自动包含相应两种三元牌役；二杯口不会另外叠加一杯口。
七对子与一般形重叠时，不能把两种解释的役拼接，也不能保留输给更高计分解释的七对子组合。

## 文件与执行流程

| 文件 | 作用 |
|---|---|
| `calc_fan.py` | 独立Python判役器；枚举全部拆分、和牌张归属、普通役、自然役满、符与基本点 |
| `shape_solver.py` | 生成四面子＋雀头或七对子结构；编码每种牌最多四张、开放／杠状态、风位及役的定义 |
| `reachability.py` | 条件役的构造证书；逐次验证立直后暗杠必须使用第四张且保持完整听牌集合 |
| `enumerate_combinations.py` | 求解候选、独立判役、排除错误见证、投影去重、流式写结果与进度 |
| `audit_results.py` | 不依赖求解器，逐条复算已保存的见证与统计 |
| `tools/report_results.py` | 对停止后的结果检查源码哈希、复算全部见证并生成中文统计报告 |
| `tools/verify_snapshot.py` | 不依赖Z3，校验已发布文件与核心源码的SHA-256 |
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
- 立直后岭上和牌必须至少找到一个合法的最后暗杠；记录摸入第四张及前后听牌。
- 抢杠要求对手有碰出的三张，和牌张是第四张，因此和牌者完成手牌中该牌只能有一张。
- 普通立直一发抢杠使用宣告立直前已有的对手碰；被抢的加杠尚未成立。
- 双立直可以在后续对手碰、加杠时抢杠，但那条过程已不满足一发。
- 海底只能是最后一次通常摸牌；岭上不与海底叠加。
- 模型采用立直后至少剩4张通常牌：普通立直一发海底可构造，一发河底不可构造。
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
