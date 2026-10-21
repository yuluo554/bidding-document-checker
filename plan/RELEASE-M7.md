# RELEASE-M7 —— 迭代二发布台账（v0.5.0 → v0.6.0）

> 写法纪律：本文件在 **tag 之前**写"tag 时点事实"，**tag 之后**只追加"tag 后事实"。
> 台账自身不能包含自己的 sha256（循环依赖），摘要值一律写进 Release 说明 / tag 消息 / `.sha256`。

---

## 一、tag 时点事实（打 tag 即冻结）

| 项 | 值 |
|---|---|
| 版本 | `0.6.0`（`pyproject.toml` 与 `src/bidchecker/__init__.py` 双源一致，实测 `bidchecker 0.6.0`） |
| 起点 HEAD | `ae8bbab7f06435d9827c8e39582daee46b9d22a5`（= `v0.5.0`，零滞后） |
| Python floor | `>= 3.12`（DEC1=B） |
| 构建后端 | `setuptools>=77`（PEP 639 license 表达式需要） |
| license | `license = "MIT"`（SPDX 表达式；已删除 `License :: OSI Approved :: MIT License` classifier） |
| CI | `{ubuntu-latest, windows-latest} × 3.12`，两步跑测试（`-m "not installed_wheel"` + `-m installed_wheel`），actions/checkout@v7 + actions/setup-python@v7 |

### 1.1 决策记录（用户 2026-10-21 拍板）

| 编号 | 结论 | 落地位置 |
|---|---|---|
| DEC1 | **B：`requires-python >= 3.12`** | `pyproject.toml`、CI 矩阵、README 快速开始、`plan/02` FR-81、`plan/03` 选型表与环境约束、`plan/06` D6/D11 |
| DEC2 | **A：data-files 装到 `<prefix>/share/bidchecker/knowledge`** | `pyproject.toml [tool.setuptools.data-files]`、`knowledge._installed_candidates()` |
| DEC3 | **A：仍可运行 + stderr 一行警告** | `pipeline._warn_missing_knowledge()`（进程内一次） |
| DEC4 | **A：`ratio=0.8` 不抽常量，文档写明两处同步** | `data/README.md §政策数值` |
| 发布 | **附 wheel + sdist + SHA256SUMS** | 见 §二 |

### 1.2 改动清单（相对 `ae8bbab`）

| 文件 | 改动 | 对应缺陷 |
|---|---|---|
| `pyproject.toml` | `0.5.0→0.6.0`；`requires-python >=3.12`；`setuptools>=77`；`license="MIT"`（SPDX）+ 删 license classifier；新增 `[tool.setuptools.data-files]`；新增 `installed_wheel` pytest marker | D1 / D5 |
| `src/bidchecker/knowledge/__init__.py` | 新增 `SHARE_SUBDIR`、`_is_knowledge_dir()`、`_installed_candidates()`、`knowledge_status()`；`find_knowledge_dir()` 加上装态分支（**保留**"两文件同时存在"判定） | D1 |
| `src/bidchecker/pipeline.py` | `finding_dicts()` 在规则映射为空时调 `_warn_missing_knowledge()`；新增 `reset_knowledge_warning()` | D1（DEC3=A） |
| `src/bidchecker/__init__.py` | `__version__ = "0.6.0"` | — |
| `data/knowledge/blocks.jsonl` | 16 条各加 `reviewed_on` + `next_review_due`（纯追加字段，`text`/`law`/`article_no` 字节未变）；33/34 条 note 补补救路径 | D3 |
| `data/README.md` | `rules.json 21 条`（原 20）；台账增「下次复核」列 + 复核口径段；新增「政策数值」段（DEC4=A） | D2 / D3 / D4 |
| `README.md` | 状态行翻 v0.6.0；快速开始加 "需要 Python ≥ 3.12"；新增「安装（pip / wheel）」段（知识库随包 + 缺失行为）；`serve` 行补"退出码 0/2"；路线图加 M7 | D5 / D6 |
| `plan/06-决策记录.md` | D19 「20 个」→ 21（含口径说明）；D6/D11 加 M7 改判注记；新增 D29/D30/D31 | D2 |
| `plan/02`、`plan/03` | 四矩阵 → 双矩阵（py3.12）；语言底线与环境约束同步 | D5 |
| `.github/workflows/ci.yml` | checkout@v4→v7、setup-python@v5→v7；矩阵去 3.8；拆 test / installed-wheel 两步 | D5 |
| `tests/test_installed_wheel.py`（新） | 5 条静态/定位/告警门 + 1 条真装门（`installed_wheel` marker） | D1 |
| `tests/test_knowledge.py` | 新增 `test_blocks_carry_review_metadata`、`test_rules_count_is_pinned`、`test_source_tree_anchor_prevents_permanent_skip` | D2 / D3 |

### 1.3 测试与基准（tag 时点实测）

| 项 | 结果 | 命令 |
|---|---|---|
| 全量测试（含真装门） | **273 passed / 0 failed**，rc=0 | `bd-verify\Scripts\python.exe -m pytest -q` |
| 不含真装门 | **272 passed / 1 deselected**，rc=0 | `... -m pytest -q -m "not installed_wheel"` |
| 真装门 | **1 passed**（21.96s） | `... -m pytest tests/test_installed_wheel.py::test_wheel_install_keeps_rule_types -q -m installed_wheel` |
| bench parse | F1=1.0000，结论 PASS，rc=0 | `bidchecker bench parse` |
| bench e2e | 检出率 1.0000 / 误报 0 / 准确率 1.0000，结论 PASS，rc=0 | `bidchecker bench e2e` |
| wheel | `bidchecker-0.6.0-py3-none-any.whl`，**39 条目**，知识库 2 条命中 `bidchecker-0.6.0.data/data/share/bidchecker/knowledge/{rules,blocks}`；构建 **0 warning** | `python -m build --wheel` |
| 装态端到端 | 干净 venv 装 wheel，中立目录 `run examples/demo-goods-1` → rc=0、结论 8 条、`rule_type` 6 个非空值、stderr 无警告 | 见 §三 NC1 |

### 1.4 负控（逐条实测）

| 编号 | 动作 | 期望 | 实测 |
|---|---|---|---|
| NC1 | 装 wheel 后跑 `run` | `rule_type` 集合 == 源码态 | ✅ 6 个非空值，`findings` 与源码态**逐字段相同** |
| NC2 | 把装态知识库移走再跑 | rc=0 + stderr 一行警告 | ✅ rc=0，stderr 有 `警告：知识库不可用…`，`basis` 仍非空 |
| NC3 | 一条 `reviewed_on=2099-01-01` / `next_review_due=2020-01-01` | 新门红 | ✅ rc=1，`test_blocks_carry_review_metadata` FAILED |
| NC4 | `rules.json` 删一条 | 条数门红 | ✅ rc=1，`test_rules_count_is_pinned` + `test_rules_json_well_formed` 双双 FAILED |
| NC5 | 改 `examples/demo-goods-1/ground_truth.json` 的 `D10→D99` | fixtures 冻结门红 | ✅ rc=1，`1 failed, 21 passed`；复原后 `22 passed` rc=0 |
| NC6 | 副本里 `run_checks` 恒返回 `[]` | `bench e2e` rc=1 + 逐条漏报 | ✅ rc=1，检出率 0.1667，结论 FAIL |
| NC7 | 干净对照 `demo-goods-2` | rc=0 且 findings 为空 | ✅ rc=0，`findings == []`，`summary.total == 0` |

### 1.5 未做 / 已知残留

- 招标投标法 33/34 条**仍未补核**（需官方渠道人工取原文），`status=待核对` + `next_review_due=2026-11-05`；
- `data/knowledge/raw/*.txt` 不进 wheel（体积 + 仅源码态需要），故装态没有台账 sha256 门——由 `test_source_tree_anchor_prevents_permanent_skip` 做反向锚；
- 未实测真 LLM 端点、未做真实 docx/PDF 输入适配；
- 未上 PyPI（本仓口径是不发 PyPI，改为 Release 附 wheel/sdist）。

---

## 二、tag 后事实（发布执行记录）

### 2.1 tag 与合并

| 项 | 值 |
|---|---|
| 分支 | `iter/m7-v0.6.0`（提交 `5cd571400a3a61e4bb73a3a78884e738e940670c`） |
| PR | #1 → `--merge` 进 main（**不用 squash**，为让 CI 验过的那个提交留在 main 祖先链） |
| main HEAD | `761cd74b3d5ea70a6472dceda4d474d30d2619be`（merge commit） |
| tag `v0.6.0` | **annotated**，`git rev-list -n1 v0.6.0` == `761cd74b3d5ea70a6472dceda4d474d30d2619be`（**零滞后**） |
| `v0.5.0` | 未动（tag 与 Release 均保持原状） |

### 2.2 CI（迁移后 runner 实测）

| run | 事件 | headSha | 结论 |
|---|---|---|---|
| `39617092134` | `pull_request`（PR #1） | `5cd5714…` | ✅ success（`test (ubuntu-latest, 3.12)` + `test (windows-latest, 3.12)` 全 success） |
| `39618073723` | `push`（main） | `761cd74…` | ✅ success（同上两 job） |

**注解**：两 run 合计仅 **1 条**，内容为
`The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026 …`（环境迁移通知）。
**Node20 弃用注解 0 条**（v0.5.0 的 4 条随 actions v7 消失）。

### 2.3 Release 附件（三方对撞）

| 文件 | 字节 | sha256（本地 dist / GitHub digest / 匿名 curl 真下载 三者相同） |
|---|---|---|
| `bidchecker-0.6.0-py3-none-any.whl` | 118,064 | `cc0b07161005c8fd079ea876409185a70e49d4803950a16d434d1554d9ab5e79` |
| `bidchecker-0.6.0.tar.gz` | 142,305 | `303361049b6204550c3d1fa3baaec67986b33fde24c0d1d4545202ca6c76a11b` |
| `SHA256SUMS` | 190 | （清单自身） |

Release URL：<https://github.com/yuluo554/bidding-document-checker/releases/tag/v0.6.0>
`isDraft=false`、`isPrerelease=false`、`releases/latest` → `v0.6.0`。

### 2.4 发布物复验（真下载 → 真装 → 中立目录跑）

| 渠道 | 结果 |
|---|---|
| 下载的 **wheel** 装进全新 venv，中立目录 `run examples/demo-goods-1` | rc=0，结论 8 条，`rule_type` 6 个非空值，stderr 无警告，`bidchecker.__version__ == 0.6.0` |
| 下载的 **sdist** 装进另一全新 venv，同一命令 | rc=0，`rule_type` 6 个非空值 |
| **tag 树**（`git clone --branch v0.6.0`）在全新 venv 跑它自带的测试 | **273 passed**，rc=0 |

### 2.5 本轮新增坑（记录备查）

1. **PEP 639 与 license classifier 不可共存**：`license = "MIT"`（SPDX 表达式）一旦启用，
   `setuptools>=77` 会对 `License :: OSI Approved :: MIT License` 直接抛
   `InvalidConfigError: License classifiers have been superseded by license expressions` ——
   构建当场失败，不是警告。改 SPDX 必须同时删 classifier。
2. **分支 push 不触发 CI**：`ci.yml` 的 `on.push.branches: [main]` 只认 main，
   推 `iter/*` 分支必须走 PR 才会有 run。
3. **真装门的期望值不能写死 rule_type 字符串**：`rules.json` 有 8 个 rule_type，
   而 `demo-goods-1` 只触发其中 6 个（`bond_check` / `price_check` 在该项目不适用）。
   正确口径是「装态 findings == 源码态 findings 逐字段相同」，期望值现算。
4. **`write_text` 写 fixtures 会引入 CRLF**：NC5 的变异第一版用 `read_text/write_text`，
   触发了两条红（`test_examples_fixture_frozen` + `test_no_cr_in_committed_examples`），
   第二条是噪声。改 fixtures 一律 `write_bytes(x.encode("utf-8"))`。
5. **`gh release view --json isLatest` 不存在**：要判 Latest 得查
   `gh api repos/<owner>/<repo>/releases/latest --jq '.tag_name'`。

---

## 三、复验入口（给复验方）

```bash
cd /d D:\ProgramData\zcode\10-05-bidding-document-checker
git status --porcelain          # 只应剩 update\（本批交接物）与已 gitignore 的 build/dist
C:\Users\ASUS\AppData\Local\Temp\bd-verify\Scripts\python.exe -m pytest -q   # 期望 273 passed
C:\Users\ASUS\AppData\Local\Temp\bd-verify\Scripts\bidchecker.exe bench parse # 期望 PASS
C:\Users\ASUS\AppData\Local\Temp\bd-verify\Scripts\bidchecker.exe bench e2e   # 期望 PASS
```

装态复验（中立目录，**不要在仓根跑**——仓根的 `data/knowledge` 会掩盖装态问题）：

```bash
C:\Users\ASUS\AppData\Local\Temp\bd-whl\Scripts\bidchecker.exe run examples\demo-goods-1 --out out
# 期望 rc=0；out\findings.json 的 rule_type 集合 = 6 个非空值
```
