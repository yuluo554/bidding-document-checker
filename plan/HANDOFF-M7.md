# HANDOFF-M7 —— 迭代二收尾交接快照

> 用法（新对话续接）：`/goal 读取 <项目根>/plan/HANDOFF-M7.md 继续完成任务`（启动命令里的绝对路径由用户侧拼接，本文件内一律相对路径）。
> 落盘：2026-10-21，由执行 M7 的工作对话写入。
> **状态：待复验**（执行方未自宣通过；见 `update/执行记录.md` 与 `update/发布记录.md`）。

## 一、当前进度（M0–M7 已完成并发布）

| 项 | 值 |
|---|---|
| 版本 | **0.6.0**（`pyproject.toml` 与 `src/bidchecker/__init__.py` 双源一致） |
| main HEAD | `96b7c58bb96db22b236a8d3ad16a5fb9197bcf70`（tag 后文档回写提交） |
| tag `v0.6.0` | annotated，指向 `761cd74b3d5ea70a6472dceda4d474d30d2619be`（= PR #1 的 merge commit） |
| tag 滞后 | `v0.6.0..HEAD` = **1 个纯文档提交**（`96b7c58`，台账回写；发布物不含它，**不重打 tag**） |
| `v0.5.0` | `ae8bbab7…` 未动（tag 与 Release 原样） |
| 测试 | **273 passed**（3.12.10，editable `[dev,report,web,llm]`；含真装门） |
| 基准 | bench parse F1=**1.0000**；bench e2e 检出率 **1.0000** / 误报 **0** / 准确率 **1.0000** |
| CI | PR run `39617092134`、main push run `39618073723`、tag 后文档 run `39619133524` —— **三 run 全 success** |
| CI 注解 | 合计 **1 条**（`ubuntu-latest → Ubuntu 26` 迁移通知）；**Node20 弃用 0 条**（v0.5.0 为 4 条） |
| Release | v0.6.0，**3 附件**（wheel / sdist / SHA256SUMS），`releases/latest` = `v0.6.0` |

### M7 交付内容（一句话版）

修 D1「`pip install` 后 findings 的 `rule_type` 全变空串」——根因是 wheel 不含
`data/knowledge/`，`load_rules()` 静默 `return []`，而 `basis` 仍在所以「看起来正常」。
修法：data-files 装到 `<prefix>/share/bidchecker/knowledge` + `find_knowledge_dir()` 装态回落
（保留「两文件同时存在才算找到」）+ 缺库时 stderr 一行警告。附带：条文复核锚、条数口径对齐、
CI 换 actions v7、floor 抬 3.12。

## 二、四项决策（用户 2026-10-21 拍板，06 D29）

| 编号 | 结论 | 一句话理由 |
|---|---|---|
| DEC1 | **B：`requires-python >= 3.12`** | 与另两仓口径统一、CI 矩阵 4→2、可转 PEP 639 SPDX；3.8 已于 2024-10 EOL（用户接受「3.8 用户装不上」） |
| DEC2 | **A：`[tool.setuptools.data-files]` → `share/bidchecker/knowledge`** | `find_knowledge_dir()` 已有「两文件同时存在」判定，加一个候选是最小改动；B 会动 fixtures 与台账路径契约 |
| DEC3 | **A：仍可运行 + stderr 警告** | 不改 `plan/06 D20`「引擎无知识库仍可运行」的既有决策，退出码语义不变 |
| DEC4 | **A：`ratio=0.8` 不抽常量** | 它是业务规则数据而非代码常量；保持 `rules.json` 自足，改值须同步两处（已写进 `data/README.md`） |
| 发布 | **附 wheel + sdist + SHA256SUMS** | 本版核心就是「装完可用」，发 wheel 才能让别人真验（v0.5.0 是 0 附件） |

## 三、既定口径清单（动了会打挂基准或门）

1. **`examples/` 字节冻结**：`test_examples_fixture_frozen` 是真门（负控：改一条 `defect_id` 立刻 1 failed）。
   要改必须 `bidchecker datagen --seed 42` 重生成并让门绿。**改 fixtures 一律 `write_bytes`**，`write_text` 会引入 CRLF 多红一条。
2. **`data/knowledge/raw/*.txt` 的 sha256**（`47be0c37…` 87号令 / `c5ec298d…` 实施条例）被
   `data/README.md` 台账 + `test_raw_files_ledger_sha256_matches` 双重钉住。**raw/ 不进 wheel**。
3. **`rules.json` = 21 条**（引擎内 20 + CHK-CL-01 围标 1）。`test_rules_count_is_pinned` 钉死；
   增删规则须同步 `EXPECTED_RULE_COUNT`、`data/README.md`、`plan/06 D19`。
4. **`blocks.jsonl` = 16 块**，每条必须带 `reviewed_on` / `next_review_due`，且 `next_review_due > reviewed_on`；
   已核对条文周期 **12 个月**（`REVIEW_CYCLE_MONTHS`）。
5. **`CHK-PC-01.params.ratio = 0.8`** 只在 `rules.json` 与 `test_rules_json_well_formed` 两处，改值须同步。
6. **基准门槛不放宽**：bench parse F1 ≥ 0.95、bench e2e 检出率 ≥ 0.95。
7. **装态验证必须在中立目录**（不是仓根）：仓根的 `data/knowledge` 会掩盖 D1 类缺陷。
8. **`installed_wheel` marker**：真装门较慢（~22s），CI 里拆成单独 step 跑；本地全量跑不要带 `-m "not installed_wheel"` 就看不到它。

## 四、本机环境坑（只记实测过的）

1. **PEP 639 与 license classifier 不可共存**：`license = "MIT"`（SPDX 表达式）+ `setuptools>=77` 时，
   保留 `License :: OSI Approved :: MIT License` 会让构建**直接失败**
   （`InvalidConfigError: License classifiers have been superseded by license expressions`），不是警告。
2. **分支 push 不触发 CI**：`ci.yml` 的 `on.push.branches: [main]` 只认 main，推 `iter/*` 必须走 PR。
3. **`gh release view --json isLatest` 不存在**：判 Latest 用 `gh api repos/<o>/<r>/releases/latest --jq '.tag_name'`。
4. **`write_text` 改 fixtures 会引入 CRLF**：会多红一条 `test_no_cr_in_committed_examples`（噪声），一律用 `write_bytes`。
5. **`| tail` / `| head` 会吞退出码**：本仓 `report`/`serve` 缺 extra 时是 exit 2，诊断期两次看成 0。
   一律 `cmd >nul 2>&1 & echo %ERRORLEVEL%`（bash：`cmd >/dev/null 2>&1; echo $?`）。
6. **venv 里没有 setuptools**（Python 3.12 起默认不装）：`python -c "import setuptools"` 在干净 venv 会
   `ModuleNotFoundError`，这不代表构建链有问题（`build` 会自建隔离环境）。
7. **`ubuntu-latest` 自 2026-10-19 起迁 Ubuntu 26**：CI 注解里的那条迁移通知是环境信息，**不是弃用告警**；
   判「注解清零」时只数 Node20 弃用。

## 五、M7 收尾动作（本对话已完成）

- [x] 四项决策落 `plan/06` D29（+ D30 复核口径、D31 条数口径）
- [x] 代码 + 测试 + 文档改动（16 文件，`5cd5714`）
- [x] 负控 NC1–NC7 全跑（NC3/NC4/NC5/NC6 变红复核，NC2 rc=0+警告，NC7 零误报）
- [x] 分支 → PR #1 → `--merge` 进 main（`761cd74`，**不用 squash**：让 CI 验过的提交留在祖先链）
- [x] tag `v0.6.0`（annotated）= `761cd74`，推送
- [x] Release 3 附件；三方 sha256 对撞（本地 / GitHub digest / 匿名 curl 真下载）
- [x] 真下载 → 真装（wheel 与 sdist 各一全新 venv）→ 中立目录 run
- [x] tag 树浅克隆自证：273 passed
- [x] tag 后文档回写（`96b7c58`）+ CI 绿
- [x] `plan/00` M7 里程碑行 + D29–D31 索引
- [x] `update/执行记录.md` + `update/发布记录.md`（**状态写「待复验」**）

## 六、M7 DoD checklist（终态 2026-10-21）

- [x] G1 `pip install` 后 `rule_type` 不再为空（装态 == 源码态，逐字段相同）
- [x] G2 缺知识库不静默（stderr 一行 + 退出码语义不变）
- [x] G3 新增装态可用性门（`tests/test_installed_wheel.py`，6 条；缺 data-files 会红）
- [x] G4 条文带机读复核元数据（16/16，含 `next_review_due > reviewed_on` 门）
- [x] G5 自述数字与实物一致（21 条三处对齐 + 条数门）
- [x] G6 CI 在迁移后 runner 上绿（三 run success，Node20 注解 0 条）
- [x] 发布：tag + Release（3 附件）+ 真下载真装复验

## 七、未做 / 残留（如实）

1. **招标投标法第 33/34 条仍未补核**（需官方渠道人工取原文），`status=待核对` +
   `next_review_due=2026-11-05`。**到期后 `test_blocks_carry_review_metadata` 会红**——这是有意的催办机制，
   不是 bug。补核时须同时更新 `raw/`（若取到原文）+ 台账 sha256 + blocks 的 `status`/`note`/`reviewed_on`。
2. 未上 PyPI（本仓口径：不发 PyPI，走 Release 附件）。
3. 未实测真 LLM 端点；未做真实 docx/PDF 输入适配（与诊断范围一致，`plan/06 D7` 仍显式顺延）。
4. `data/knowledge/raw/*.txt` 不进 wheel → 装态没有台账 sha256 门，由
   `test_source_tree_anchor_prevents_permanent_skip` 做反向锚防假 skip。
5. **待复验项**：本次执行方自测全部通过，但按项目纪律不视为「通过」，需独立复验。

## 八、关键命令速查

```bash
# 环境（本机；临时环境一律在 %TEMP% 下，不在仓内建 .venv）
bd-verify = C:\Users\ASUS\AppData\Local\Temp\bd-verify   # editable 全 extras
bd-whl    = C:\Users\ASUS\AppData\Local\Temp\bd-whl      # 装 0.6.0 wheel
bd-neutral= C:\Users\ASUS\AppData\Local\Temp\bd-neutral  # 中立运行目录（装态验证必须用它）

# 测试与基准
$bd-verify\Scripts\python.exe -m pytest -q                          # 273 passed（含真装门）
$bd-verify\Scripts\python.exe -m pytest -q -m "not installed_wheel" # 272 passed
$bd-verify\Scripts\python.exe -m pytest -q -m installed_wheel       # 1 passed（真装门，~22s）
$bd-verify\Scripts\bidchecker.exe bench parse                       # F1=1.0000 PASS
$bd-verify\Scripts\bidchecker.exe bench e2e                         # 检出率 1.0000 / 误报 0 PASS

# 构建与检查 wheel 里的知识库
$bd-verify\Scripts\python.exe -m build                              # wheel + sdist，0 warning
$bd-verify\Scripts\python.exe -c "import zipfile,glob; n=zipfile.ZipFile(glob.glob(r'dist\*.whl')[0]).namelist(); print([x for x in n if 'knowledge' in x])"
#   → 期望 2 条：...data/data/share/bidchecker/knowledge/{rules.json,blocks.jsonl}

# 装态验证（中立目录！）
cd /d %TEMP%\bd-neutral
$bd-whl\Scripts\bidchecker.exe run examples\demo-goods-1 --out out
$bd-whl\Scripts\python.exe -c "import json; d=json.load(open('out/findings.json',encoding='utf-8')); print(sorted({f['rule_type'] for f in d['findings']}))"
#   → 期望 6 个非空值（无空串）

# 缺知识库行为（NC2）
#   把 <venv>\share\bidchecker\knowledge 改名后再 run → rc 仍 0，stderr 有一行「警告：知识库不可用…」

# 发布物
gh release view v0.6.0 --repo yuluo554/bidding-document-checker --json assets --jq '.assets[]|"\(.name) \(.size) \(.digest)"'
git rev-list -n1 v0.6.0        # 761cd74b3d5ea70a6472dceda4d474d30d2619be
```
