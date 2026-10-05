# HANDOFF-M1 —— 数据先行里程碑交接快照

> 用法（新对话续接）：`/goal 读取 <项目根>/plan/HANDOFF-M1.md 继续完成任务`（启动命令里的绝对路径由用户侧拼接，本文件内一律相对路径）。
> 落盘：2026-10-05，由完成 M0 的工作对话写入。

## 一、当前进度（M0 已完成）

- **计划文档**：plan/00–06 全部定稿（01 题目定稿 2026-10-04；02–06 定稿 2026-10-05），索引与状态见 [00-README总览.md](00-README总览.md)；
- **可运行骨架**（已验证）：
  - `bidchecker` 包（src layout）：`schema.py` = 参数卡 IR + Finding（既定口径的代码化，to_dict/from_dict JSON 往返）；`cli.py`（run/datagen/bench/report/serve，未交付命令退出码 2 并指向 plan/05）；`rules/gates.py` 类目门控已实现；`parsers/common.py` 预处理（CRLF/零宽/全角空格）已实现；其余子包为带设计注释的占位；
  - tests 30 项全绿（0.13s）：schema 往返 / CLI / 预处理 / 门控 / 包级导入 / stub 行为锁定 / extras 守门；
  - pyproject：core 零依赖 + extras（web/report/llm/dev）；`.gitattributes` eol=lf 入仓（EOL 门预防）；ci.yml 四矩阵（ubuntu/windows × py3.8/3.12）——**CI 尚未首跑**（GitHub push 后验证，M6 对账 push 数=run 数）；
  - README（骨架版，状态诚实标注 🚧）、LICENSE（MIT，contributors 署名）；
- **git**：本地已提交；未建远端、未 push（建仓 = M6 动作）。

## 二、下一里程碑 M1（数据先行）待办

1. `datagen` 生成器：Markdown 固定体例模板——招标 6 章 / 投标 7 章（05 §1.1），虚构主体池（公司/人名/证书编号/项目名）；
2. 缺陷注入 D1–D12（05 §1.2）+ **项目级互斥表**（防同参数双注入打架）；干净对照组项目；
3. 真值：`ground_truth.json`（主期望 + also_expect），**真值语义写进生成器模块注释**（05 §1.4）；
4. 固定 seed 两次生成**位级一致**守门测试；fixtures 字节冻结 + "出现 CR 即大声失败"守门测试（06 D12）；
5. `bidchecker datagen --seed 42` 产出 3 个演示项目（货物×2、服务×1）入 `examples/`；data/README 登记表更新；
6. DoD 全过后：写 HANDOFF-M2、回写 plan/00/05/06 状态，再结束会话。

## 三、既定口径清单（动了会打挂基准）

- `schema.py` 字段与结构 = plan/04 §1；任何变更必须同步生成器真值语义 + 基准对账逻辑，并重跑全部基准；
- 真值对账口径：注入缺陷记**主期望**，隐含结论记 `also_expect`，e2e 按"文档全部非 pass 集合"对账（非逐条一一比对）；
- Finding 三级判定常量（符合/不符合/待人工确认）与 7 种 rule_type 集合不变；
- `only_if` 类目门控对**全部** check_type 生效（含 conditional/checklist 分支）——引擎分派前必过 `rules/gates.py`；
- 基准门槛不放宽：解析 F1 ≥ 0.95、检出率 ≥ 0.95、误报 0、零 API 依赖；
- 测试全离线 mock；core 零依赖（test_extras_gate 已守门；加测试期依赖必须同步 extras）；
- CLI 未交付命令 = 退出码 2 + 指向 plan/05 的提示（test_cli 锁定）；
- EOL：fixtures 字节冻结文件出现 CR 即大声失败；`.gitattributes` `* text=auto eol=lf` 已入仓。

## 四、本机环境坑（只记实测过的）

- **系统 Python 3.8.8 + setuptools 49.2.1 过老**：`pip install -e .` 报 `invalid command 'bdist_wheel'`；2026-10-05 已升级 setuptools 75.3.4 + wheel 0.45.1（75.x 为 3.8 支持的最后一版）——新机器/干净 venv 需先装这两个再可编辑安装；
- 用 `py` 不用 `python`（商店占位符）；脚本一律 `py -X utf8`（中文控制台 GBK）；全程 `PYTHONDONTWRITEBYTECODE=1`（**pip install 也要带**，防 pyc 损坏类随机崩溃；单轮崩溃/随机失败先重试再深挖）；
- pip 已配置 tsinghua 镜像；若注册表系统代理污染 → 前缀 `NO_PROXY="*" no_proxy="*"`；
- `bidchecker.exe` 装到 `Python38\Scripts`（不在 PATH）→ 统一用 `py -X utf8 -m bidchecker`；
- Git Bash 以 `/` 开头的参数会被 MSYS 静默转写（扫描/路径类字面值用包含形式，"0 命中"先跑阳性对照）；
- **提交元数据邮箱是个人 QQ 邮箱**（06 D13）：M6 发布前必须 filter-branch env-filter 全历史改写 GitHub noreply，本地 `git config user.email` 同步改——列入 M6 DoD。

## 五、M1 DoD checklist

- [ ] 招标 6 章 / 投标 7 章固定体例 Markdown 生成（主体全虚构）
- [ ] D1–D12 缺陷注入 + 项目级互斥表 + 干净对照组
- [ ] ground_truth.json（主期望 + also_expect），语义写入生成器模块注释
- [ ] 固定 seed 两次生成位级一致（守门测试）；fixtures 字节冻结 + CR 守门测试
- [ ] `examples/` 3 个演示项目（货物×2、服务×1）；data/README 登记表更新
- [ ] pytest 全绿（含生成器新测试）；plan/00/05/06 状态回写；HANDOFF-M2 落盘

## 六、关键命令速查

```bash
cd <项目根>
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest -q            # 全量测试
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker --version
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker run examples/demo   # M2 前退出码 2
# 重装（先升级构建链）：
NO_PROXY="*" no_proxy="*" py -m pip install -U setuptools wheel
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -X utf8 -m pip install -e . --no-build-isolation
```
