# bidding-document-checker 项目计划总览

**项目**：招投标文件智能评审与合规校核系统（公共采购领域）
**方法论**：ai-tool-project-sprint（plan 先行 → 数据先行 → 解析/规则/LLM → 基准 → 编排交付 → 脱敏发布）
**项目系列**：construction-drawing-plan-checker（建造，已发布）→ power-operation-ticket-checker（电力，题目定稿）→ medical-record-quality-checker（医疗，题目定稿）→ 本项目（公共采购，题目定稿）

## 文档索引

| 文档 | 内容 | 状态 |
|---|---|---|
| [01-题目详细定义.md](01-题目详细定义.md) | 模拟赛题全文（介绍/任务/提交材料/评分/含金量锚点/边界） | ✅ 定稿 2026-10-04 |
| [02-需求解读.md](02-需求解读.md) | 痛点→能力转译表、FR 功能清单、边界与非目标、指标口径 | ✅ 定稿 2026-10-05 |
| [03-架构与技术选型.md](03-架构与技术选型.md) | 分层架构、技术栈、依赖分层、LLM 策略、目录结构、环境约束 | ✅ 定稿 2026-10-05 |
| [04-模块详设.md](04-模块详设.md) | 参数卡 schema（既定口径）、符合性引擎、解析器、知识库、基准 | ✅ 定稿 2026-10-05 |
| [05-数据计划与里程碑.md](05-数据计划与里程碑.md) | 合成文档生成器与缺陷注入设计、法规获取计划、M0–M7 细化 | ✅ 定稿 2026-10-05（M7 行 2026-10-21 补） |
| [06-决策记录.md](06-决策记录.md) | 重大决策表（D1–D31）+ 待用户拍板事项 + 缓议项跟踪（全部闭环） | ✅ 定稿 2026-10-05（D29–D31 于 2026-10-21 补；早期决策摘要见下） |
| [RELEASE-M7.md](RELEASE-M7.md) | v0.6.0 发布台账（tag 时点事实 / tag 后事实：PR、CI、附件三方对撞、真装复验、新增坑） | ✅ 2026-10-21 |
| [HANDOFF-M1.md](HANDOFF-M1.md) | M0→M1 交接快照（进度/待办/既定口径/环境坑/DoD/命令） | ✅ 2026-10-05 |
| [HANDOFF-M2.md](HANDOFF-M2.md) | M1→M2 交接快照（进度/待办/既定口径/环境坑/DoD/命令） | ✅ 2026-10-05 |
| [HANDOFF-M3.md](HANDOFF-M3.md) | M2→M3 交接快照（进度/待办/既定口径/环境坑/DoD/命令） | ✅ 2026-10-05 |
| [HANDOFF-M4.md](HANDOFF-M4.md) | M3→M4 交接快照（进度/待办/既定口径/环境坑/DoD/命令） | ✅ 2026-10-05 |
| [HANDOFF-M5.md](HANDOFF-M5.md) | M4→M5 交接快照（进度/待办/既定口径/环境坑/DoD/命令） | ✅ 2026-10-05 |
| [HANDOFF-M6.md](HANDOFF-M6.md) | M5→M6 交接快照（进度/待办/既定口径/环境坑/DoD/命令） | ✅ 2026-10-05 |
| [HANDOFF-M7.md](HANDOFF-M7.md) | M6→M7 交接快照（v0.6.0 口径/四项决策/既定口径清单/新坑/DoD/命令） | ✅ 2026-10-21（**待复验**） |

## 决策记录

| 日期 | 决策 | 结论 |
|---|---|---|
| 2026-10-04 | 选题 | 招投标文件智能评审（系列第四题）：政策锚点最强（发改法规〔2026〕195号八部门文件）、有真实赛事（中招协AI赛项）、开源空白；弃选：劳动合同审查（法规分散）、环评审查（专业门槛高）、危化品方案审查（与电力同属安全生产域） |
| 2026-10-04 | 仓库名与可见范围 | `bidding-document-checker`，GitHub 公开 |
| 2026-10-04 | 合规红线 | 全合成数据、辅助评审非决策工具定位（免责声明）、围标分析仅限文本特征 |
| 2026-10-04 | 法规依据 | 613号令/87号令/16号令/195号文文号与日期已核（见 01 §二.5），条款入库时逐条挂出处 |

> 2026-10-05 起新增决策（包名 `bidchecker`、py3.8 底线【**M7 改判为 3.12**】、输入格式 v1、LLM 接入、依赖分层、
> LICENSE、CI、EOL、提交邮箱改写、是否参赛【已拍板：不参赛】、品牌隔离执行、M1 数据口径细化）→
> [06-决策记录.md](06-决策记录.md) D5–D17；M2 解析对账口径 → 同文件 D18；M3 引擎接口/知识库落库/
> run 退出码/▲偏离方向语义 → 同文件 D19–D22；M4 围标检出/e2e 对账口径/LLM 兜底纪律/
> 招标投标法 33·34 条补核 → 同文件 D23–D26；M5 报告与图谱口径/符合性推导/serve 交付 → 同文件 D27；
> M6 发布执行记录（邮箱改写/建仓 push/CI/发布固化）→ 同文件 D28；
> M7 迭代二四项决策（floor 3.12 / 知识库进 wheel / 缺库警告 / ratio 不抽常量）+ 复核元数据口径 + 条数口径 → 同文件 D29–D31。

## 里程碑

细化版（周期/可演示物/DoD/风险）→ [05-数据计划与里程碑.md](05-数据计划与里程碑.md)。

- M0 骨架（2026-10-05 ✅）：plan 00–06 定稿 + 可运行骨架（`bidchecker` 包：参数卡 schema/CLI/类目门控/解析预处理，30 项测试全绿，CI 四矩阵配置）+ HANDOFF-M1
- M1 数据先行（2026-10-05 ✅）：`bidchecker datagen` 生成器交付——招标 6 章/投标 7 章固定体例 + D1–D12 缺陷注入（互斥表）+ ground_truth.json（主期望+also_expect）+ 自研确定性随机源；seed=42 产出 3 个演示项目（货物×2、服务×1，含干净对照）入 examples/（fixtures 字节冻结 + CR 守门）；99 项测试全绿 + HANDOFF-M2
- M2 解析层（2026-10-05 ✅）：`parse_tender`/`parse_bid` 双侧解析器交付——LineDoc 行对齐 + 章节树五步流水线（预处理→章节切分→槽位抽取→合法性校验→证据绑定）；`bidchecker bench parse` 多 seed 全量对账 F1=1.0（65 文档 4185 字段）；D1–D12 注入值原样抽出（一致性判定留给 M3 引擎）；陷阱用例（CRLF/零宽字符/全角空格/中文路径）；156 项测试全绿 + HANDOFF-M3
- M3 知识与规则（2026-10-05 ✅）：法规三层知识库落库（87号令 8 条 + 实施条例 6 条官方原文逐字核验已核对、招标投标法 2 条待核对显式落库、rules.json 20 条 CheckRule）+ 符合性引擎交付（run_checks 投标侧六类 + run_tender_checks 招标侧，D1–D10/D12 确定性检出，多 seed 四元组对账全过、干净对照误报 0、basis 依据关联率 100%、only_if 门控对全部 check_type 生效）+ `bidchecker run` 端到端（3 演示项目 findings 与 ground_truth 全集合一致，退出码 0/1/2 定稿锁定）；pytest 184 项全绿 + HANDOFF-M4
- M4 LLM 兜底 + 内置基准（2026-10-05 ✅）：collusion 围标对按对检出（双信号交叉验证：同分钟编制时间戳+ 对照独有共享长句；CHK-CL-01 注册、依据挂实施条例 39/40 条 + 87号令 36/37 条）+ bench e2e 转正（多 seed × 3 项目全链，对账 ground_truth 全集合含 D11：检出率 1.0 / 误报 0 / 判定准确率 1.0，分缺陷类型报告）+ LLM 兜底通路（client.chat 标准库传输 + 宁缺槽位兜底：quote⊂原文硬校验、数值合法性校验、不覆盖确定性抽取、不可达降级纯规则通路、不改 status）+ 知识库检索 knowledge/search.py（TF 余弦 top_k，不引向量库）；指标写入 README；pytest 223 项全绿 + HANDOFF-M5
- M5 编排与交付（2026-10-05 ✅）：`bidchecker report` docx 评审报告（结论汇总 + 分级明细 + 依据/证据锚点 = 条文块原文与招标条款原文、符合性矩阵由报告层推导 `--all` 展开；docx 无外链/无时间戳断言）+ 围标图谱 HTML（5-gram shingle + Jaccard 两两矩阵 + 确定性力导向布局，问题边与 detect_collusion 同口径，0 外链、两次构建逐字节一致，`run --graph` 交付）+ `bidchecker serve` Web 面板（fastapi 单页，上传/内置演示一键加载，复用 pipeline 全链，LLM 固定禁用、0 外链断网可演示，/docs 关闭）；CLI 收口（report/serve 转正、退出码 0/2 锁进 test_cli）；断网全链演示（datagen→run→bench→report→serve 零 LLM env 全离线跑通）+ 干净环境冒烟（本地 clone + 全新 venv 按 README 逐字跑通，pytest 264 项全数对账、datagen 位级一致）；pytest 264 项全绿 + 双基线不回退 + HANDOFF-M6
- M6 脱敏发布（2026-10-05 ✅）：提交邮箱全历史改写（filter-branch env+tree 双滤 9 提交，main 三扫清零仅白名单命中）→ GitHub 公开仓库 yuluo554/bidding-document-checker push main（SSH 通道，OAuth token 缺 workflow scope 的替代）→ CI 四矩阵首跑全绿（push 数 = run 数 = 2 对账）→ tag v0.5.0 + GitHub Release + topics（经用户确认执行）。M6 收官。
- M7 迭代二（2026-10-21 ✅）：修 D1「pip 装完 rule_type 全变空串」——`[tool.setuptools.data-files]` 把 rules.json + blocks.jsonl 装到 `<prefix>/share/bidchecker/knowledge`，`find_knowledge_dir()` 加装态回落（保留"两文件同时存在"判定）；缺知识库仍可运行但 stderr 一行警告（DEC3=A）；blocks 16 条加 `reviewed_on`/`next_review_due` + 门；`rules.json 21 条` 口径三处对齐 + 条数门；floor 抬 `>=3.12` + actions v7 + CI 双矩阵；pytest **273 项全绿**、bench parse F1=1.0 / e2e PASS 不回退；wheel 39 条目（知识库 2 条）；tag `v0.6.0`（= main `761cd74`）+ Release 3 附件（whl/sdist/SHA256SUMS，三方 sha256 对撞 + 真下载真装复验）。详见 `plan/RELEASE-M7.md`。
