# HANDOFF-M5 —— 编排与交付里程碑交接快照

> 用法（新对话续接）：`/goal 读取 <项目根>/plan/HANDOFF-M5.md 继续完成任务`（启动命令里的绝对路径由用户侧拼接，本文件内一律相对路径）。
> 落盘：2026-10-05，由完成 M4 的工作对话写入。

## 一、当前进度（M0、M1、M2、M3、M4 已完成）

- **计划文档**：plan/00–06 定稿；M4 新增决策 D23（围标文本特征检出口径）、
  D24（bench e2e 对账口径与指标）、D25（LLM 兜底范围与纪律）、
  D26（招标投标法 33/34 条补核结果：四渠道均无法逐字核验，维持待核对）已入 06；
- **M4 交付（已验证，pytest 223 项全绿 2.1s；bench parse F1=1.0 + bench e2e PASS）**：
  - **围标按对检出**（collusion/__init__.py）：**双信号交叉验证**——同分钟编制时间戳
    （`编制完成时间：` 行取值相同）+ 对照独有共享长句（≥24 字相同行，不在招标文本、
    不在其余投标文本；投标 <3 份不产出）同时命中才出一条 collusion·待人工确认·mid；
    单信号污染路径实测存在（干净投标的响应行/承诺行在第三份投标被注入偏离后成为
    "对照独有共享行"，同分钟编制也可能巧合）；target=围标对 "bids/A.md|bids/B.md"
    **按投标人名排序规范化**（spec.py pair_target 同步改，seed=42 examples 输出不变、
    fixtures 冻结测试未破坏）；CHK-CL-01 注册进 rules.json（21 条，rule_type=collusion
    不入引擎 RULE_TYPES 分派表，CHECK_IDS 注册表含之）；依据=实施条例 39/40 条 +
    87号令 36/37 条（全部已核对），仅文本特征不出定性结论；
  - **pipeline**：collusion 节点转正（findings 含围标对 target，summary/finding_dicts/
    落盘 findings.json 全链路携带）；`run_pipeline(..., llm_fallback=None|False)` 参数，
    False=强制纯规则通路；
  - **bench e2e**（bench/__init__.py 扩展）：多 seed × 3 演示项目（含干净对照）落盘 →
    run_pipeline → findings 四元组 vs ground_truth.json **全集合（expect_findings +
    also_expect 含 D11）**；指标=检出率（分缺陷类型，该缺陷全部期望四元组被覆盖才计
    检出）/误报数（全集合差集）/判定准确率（四元组微平均）；门槛检出率 ≥0.95、
    误报 0、准确率 ≥0.95；**实测默认 seeds 检出率 1.0 / 误报 0 / 准确率 1.0**，
    另抽 4 seed 无回归；
  - **CLI**：`bench e2e [--seed N]` 转正（退出码 0/1，裸 bench=用法提示 2），
    test_cli 锁定更新（future_commands 去掉 bench）；
  - **LLM 兜底通路**：llm/client.py `chat` 交付（OpenAI 兼容，**标准库 urllib 传输**，
    LLMError 收敛 + 有限重试 + 剥 <think>/围栏/截断 JSON 最小修复）；
    llm/fallback.py `fill_missing_slots`——只对解析后仍为 None 的"宁缺"槽位
    （投标侧 9 / 招标侧 11 字段白名单），候选行（关键词筛+行号）→ LLM 返回
    {field, value, quote}，**quote ⊂ 原文硬校验、数值过合法性校验才入卡、绝不覆盖
    确定性抽取值、容器缺失就地构建**；LLM 不产生/不修改任何 Finding；不可达/未启用/
    响应不合法 → 整链退化纯规则通路（阶段明细可解释）；降级/填充/超限价联动测试齐；
  - **知识库检索**（knowledge/search.py）：纯 Python TF 余弦 top_k（拉丁词+中文二字组，
    不引向量库），排序确定性 (-score, law, article_no)；
  - **指标写进 README**（内置基准指标节：F1=1.0 / 检出率 1.0 / 误报 0 / 准确率 1.0 +
    对账口径说明）；版本 0.4.0（pyproject 与 __init__ 首次同步）；
- **git**：本地已提交（至 M3）；M4 完成后本地提交；未建远端、未 push（建仓 = M6 动作）。

## 二、下一里程碑 M5（编排与交付）待办

1. **`bidchecker report` 交付**：findings.json + cards → docx 评审报告
   （report extra：python-docx；report/__init__.py 现为空壳）——报告结构按 plan/04 §六
   （结论汇总 + 分级明细 + 依据/证据锚点 + 符合项按需展开）；**docx 无外链断言**
   （测试期解析 docx XML 断言 0 个 http(s) 外链）；
2. **围标图谱 HTML**（P1 加分项，plan/04 §五）：字符 5-gram shingle + Jaccard 两两矩阵
   + 异常一致性 → 自绘 SVG 力导向布局，节点=投标人、边=相似度/一致性问题（标注类型与
   证据数），点击节点/边展开证据文本与锚点（可溯源联动）；**硬断言 0 外链**；
   M4 的 detect_collusion 已提供按对结论，图谱层做两两全量特征可视化；
3. **`bidchecker serve` 交付**：Web 面板（web extra：fastapi/uvicorn/python-multipart），
   免构建、**0 外链硬断言**、断网可演示（webapp/__init__.py 现为空壳）；
4. **CLI 收口**：report/serve 转正后 test_cli 的 future_commands 参数化清空/重写；
   退出码语义维持（0 成功 / 1 降级 / 2 未交付或输入错误）；
5. **断网全链演示**：datagen → run → bench parse/e2e → report → serve 全部离线跑通
   （LLM 通路默认关闭即离线；report/serve 不引入外链资源）；
6. **干净环境冒烟**：全新 venv 按 README 快速开始逐字跑通（收集数对账）；
7. **缓议闭环**（plan/06 §三）：D14 是否参赛——M5 收尾前必须拍板；D7 docx 输入适配
   ——M5 收尾评估余力，不采纳则显式顺延；
8. DoD 全过后：写 HANDOFF-M6、回写 plan/00/05/06 状态，再结束会话。

## 三、既定口径清单（动了会打挂基准）

- `schema.py` 字段与结构 = plan/04 §1（M0 冻结，未动）；
- **真值语义**（datagen/__init__ 注释为权威）：注入缺陷记主期望（expect_findings），
  隐含结论记 also_expect；**e2e 对账 = 全集合含 D11（M4 定稿，D24）**；四元组
  (rule_type, status, risk_level, target) 唯一；D4/D8/D9 → rejection_scan 隐含
  （R4/R2/R3）；D5 打 ▲ 无隐含；D12 主期望即 rejection_scan（R1）；D10 目标
  tender.md；**D11 目标围标对（两端按投标人名排序规范化，D23）**；
- **引擎接口口径**（=D19）：run_checks 投标侧 / run_tender_checks 招标侧分侧；
  doc_text=None → only_if 规则不激活；只产非符合结论；check_id 必须在 rules.json
  注册（**21 个 CHK-\***，含 CHK-CL-01）；
- **引擎引用条文 = D20**（全部官方逐字核验）：87号令 23/36/37/39/50/59/60/63 条 +
  实施条例 25/26/27/39/40/51 条 status=已核对；招标投标法 33/34 条 status=待核对
  **引擎不引用**（D26 四渠道补核失败后维持）；16号令/195号文条文 M5/M6 按需补；
- **围标双信号交叉验证 = D23**：SENTENCE_MIN_LEN=24；<3 份投标不产出；
  CHK-CL-01 的 rule_type=collusion 不在 RULE_TYPES 分派表内（test_gates/test_engine/
  test_knowledge 三处锁定口径）；
- **LLM 兜底纪律 = D25**：槽位白名单、quote ⊂ 原文硬校验、数值合法性校验、不覆盖
  确定性抽取、LLM 不改 Finding.status、不可达降级纯规则通路、bench 强制
  llm_fallback=False（零 API）；
- **R1 条款内嵌最高限价金额**：引擎从 R1 文本 `人民币x,xxx.00元` 抽取（schema 无预算字段）；
- ▲偏离方向语义 = D22：下限（不少于/不低于）、上限（不超过/不高于、"X日内完成"）；
  响应值更优不属偏离；数值不可提取宁缺勿错跳过；goods ▲S2 dev_pool 为更小值——
  未来若对 goods 注入 D5 须先修 dev_pool 方向；
- Finding 三级判定常量与 RULE_TYPES 7 类集合不变（test_gates 锁定）；
- `only_if` 类目门控对全部 check_type 生效（引擎分派前必过 gates.rule_applies）；
- **体例行级格式 = 解析接口**（templates.py 注释）；bench parse F1=1.0 不回退是每次
  收尾的必跑项；bench e2e PASS 同为必跑项；
- 基准门槛不放宽：解析 F1 ≥ 0.95、e2e 检出率 ≥ 0.95、误报 0、准确率 ≥ 0.95、零 API 依赖；
- **examples/ 是字节冻结 fixtures**：改体例/生成器 → test_examples_fixture_frozen 会挂，
  属预期——用 `bidchecker datagen --seed 42` 重新生成后整目录提交，**禁止手改**；
- 生成路径禁 stdlib random / set 迭代 / 系统时钟（DetRng 纪律）；落盘产物
  （findings.json）不含时间戳（两次运行逐字节一致）；search.py 排序确定性
  （-score, law, article_no，禁哈希序）；
- 测试全离线 mock；core 零依赖（llm/chat 用标准库 urllib，pyproject llm extra 的
  httpx 保留给 Web TestClient——D25）；加测试期依赖必须同步 extras 并过守门测试；
- CLI 退出码语义（M3/M4 定稿锁进 test_cli）：run 0/1/2；bench parse/e2e 0/1；
  report/serve 未交付 = 2 + 指向 plan/05 提示（M5 转正后重写该参数化）；
- EOL：`.gitattributes` `* text=auto eol=lf`；fixtures 出现 CR 即大声失败。

## 四、本机环境坑（只记实测过的）

- **系统 Python 3.8.8 + setuptools 49.2.1 过老**：`pip install -e .` 报 `invalid command
  'bdist_wheel'`；需先 `py -m pip install -U setuptools wheel`（75.3.4 / 0.45.1 已装，
  新机器需重装）；
- 用 `py` 不用 `python`（商店占位符）；脚本一律 `py -X utf8`（中文控制台 GBK）；
  全程 `PYTHONDONTWRITEBYTECODE=1`（pip install 也要带）；单轮崩溃/随机失败先重试再深挖；
- pip 已配置 tsinghua 镜像；若注册表系统代理污染 → 前缀 `NO_PROXY="*" no_proxy="*"`；
  curl 抓 gov.cn/mof.gov.cn 官网页面需同样前缀；
- `bidchecker.exe` 装到 `Python38\Scripts`（不在 PATH）→ 统一用 `py -X utf8 -m bidchecker`；
- Git Bash 以 `/` 开头的参数会被 MSYS 静默转写（路径类字面值用包含形式，"0 命中"先跑阳性对照）；
- Git Bash 的 `/tmp` 与 Windows Python 互不可见——curl 下载落盘用**工作区内相对路径**；
- **`py -X utf8 - <<heredoc` 含中文偶发 stdin 编码 SyntaxError**（M4 实测 1 次）——
  改写为工作区临时 .py 文件执行（用完即删）；
- `Path.write_text()` 在 py3.8 无 `newline` 参数——写 UTF-8/LF 统一用 `write_bytes(x.encode("utf-8"))`；
- **WebFetch 抓 flk.npc.gov.cn 与其 /api/ 端点返回空壳**（JS 渲染站点），WebFetch 对
  mof.gov.cn/gov.cn 正常；WebFetch 小模型引用限长（约 125 字/引文）——逐字条文用 curl 落盘
  后本地提取，不要靠摘要工具转述；
- **WebSearch 返回的域名级链接不可直接定位全文页**（如 zjw.sh.gov.cn），候选 URL 需逐个
  curl 验证（404/重定向/空页），M4 补核 33/34 条四渠道全败记录见 plan/06 D26；
- **提交元数据邮箱是个人 QQ 邮箱**（06 D13）：M6 发布前必须 filter-branch 全历史改写
  GitHub noreply，本地 `git config user.email` 同步改——列入 M6 DoD。
- （M4 无其他新增坑；223 项测试 2.1s 全绿，无环境差异型失败）

## 五、M5 DoD checklist

- [ ] `bidchecker report` 交付：findings → docx 评审报告（report extra），docx 无外链断言
- [ ] 围标图谱 HTML：5-gram shingle + Jaccard 两两矩阵、SVG 力导向、0 外链、证据溯源展开
- [ ] `bidchecker serve` 交付：Web 面板（web extra），0 外链硬断言、断网可演示
- [ ] CLI 收口：report/serve 转正、退出码锁定 test_cli；符合明细在报告层按需展开
- [ ] 断网全链演示（datagen→run→bench→report→serve 全离线）+ 干净环境冒烟
- [ ] 缓议闭环：D14 参赛拍板；D7 docx 适配评估（不采纳则显式顺延记录）
- [ ] pytest 全绿（现基线 223 项）；bench parse F1=1.0 + bench e2e PASS 不回退
- [ ] plan/00/05/06 状态回写；HANDOFF-M6 落盘；本地提交

## 六、关键命令速查

```bash
cd <项目根>
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest -q               # 全量测试（基线 223 项）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker bench parse  # 解析基准（默认 5 seed，F1=1.0）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker bench e2e    # e2e 基准（检出率/误报/准确率，含 D11）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker run examples/demo-goods-1 --out output
                                                                # 端到端：findings.json + cards/ + 摘要（含围标对结论）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker run examples/demo-goods-2 --out output  # 干净对照=0 条
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker datagen --seed 42   # 再生成 examples/
# 围标模块直用（M5 图谱层复用）：
#   from bidchecker.collusion import detect_collusion
#   detect_collusion({相对路径: 原文}, exclude_text=招标原文) -> [PairFinding(target, Finding)]
# 知识库检索（M5 报告层引用原文锚点）：
#   from bidchecker.knowledge.search import search
#   search("投标保证金", top_k=5) -> [(score, 条文块), ...]
# LLM 兜底（默认关闭；env 三件套齐备才启用，bench 强制禁用）：
#   from bidchecker.llm.client import is_enabled, chat
#   from bidchecker.llm.fallback import fill_missing_slots
# 引擎对账取用（e2e 同口径，落盘目录跑 pipeline）：
#   from bidchecker.bench import run_e2e_bench      # 报告对象/文本：run_bench_e2e / format_e2e_report
# 校验台账 sha256（tests/test_knowledge.py::test_raw_files_ledger_sha256_matches 自动做）
# 重装（先升级构建链）：
NO_PROXY="*" no_proxy="*" py -m pip install -U setuptools wheel
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -X utf8 -m pip install -e . --no-build-isolation
```
