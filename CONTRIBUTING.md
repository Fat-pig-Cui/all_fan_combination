# 参与开发

欢迎提交规则反例、可复算牌例、算法修正和性能改进。项目以理论规则的存在性枚举为目标，
不要求连接雀魂服务器，也不把旧人工总数当作正确答案。

## 开发环境

Python 3.9 或更新版本；使用虚拟环境安装 `requirements.txt`。
从仓库根目录运行：

```bash
python -m unittest discover -s tests -v
python tools/verify_snapshot.py
python audit_results.py results/full
python audit_results.py results/sanma
```

可选JavaScript对照需要Node.js和单独取得的参考源码；具体命令见README。
不提交外部项目源码、IDE设置、虚拟环境或本机路径。

## 规则或算法变更

1. 给出具体和牌前手牌、和牌张、固定面子、风位及条件，说明预期结果。
2. 同步修改Python判役、结构约束及条件证书中受影响的部分。
3. 添加能够区分修改前后行为的边界测试。
4. 若改变统计口径，更新 `THEORY.md`、README及来源说明。
5. 在新的输出目录重新枚举；只有 `unsat` 才能发布新的完整总数。

```bash
python enumerate_combinations.py --output results/local-run
python tools/report_results.py results/local-run
python tools/pack_results.py results/local-run
```

## 发布结果快照

`results/full/` 是已发布基线，不是开发时的默认工作目录。
`results/sanma/` 是独立的三麻基线；更改三麻规则时同步判役、求解、条件证书与 `rules.py`，不要混入四麻续算。新的三麻运行用 `--players 3` 和独立目录；余牌门槛当前为用户确认的3张。
核心源码改变后，旧快照的源码校验会失败；不要只修改哈希来掩盖模型变化。
发布更新时应将新完整运行的 `records.zip`、`archive.json`、汇总、复算结果和报告一起更新。
打包操作保留本地JSONL；验证压缩内容后，待发布快照只保留压缩包，不再附带大JSONL副本。
替换基线后重新生成报告，再更新 `results/SHA256SUMS`，并记录统计差异及其原因。

GitHub Actions运行测试、文件／源码哈希检查和全部见证复算，不在每次提交中重新执行完整枚举。
本地通过这些检查不等于已在GitHub执行过工作流。
