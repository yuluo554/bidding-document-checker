# HANDOFF-M4 —— LLM 兜底与内置基准里程碑交接快照

> 用法（新对话续接）：`/goal 读取 <项目根>/plan/HANDOFF-M4.md 继续完成任务`（启动命令里的绝对路径由用户侧拼接，本文件内一律相对路径）。
> 落盘：2026-10-05，由完成 M3 的工作对话写入。

## 一、当前进度（M0、M1、M2、M3 已完成）

- **计划文档**：plan/00–06 定稿；M3 新增决策 D19（引擎接口与结论口径）、D20（知识库落库口径）、
  D21（run 退出码语义）、D22（▲偏离方向语义）已入 06；
- **M3 交付（已验证，pytest 184 项全绿 1.1s）**：
  - **知识库三层落库**（data/knowledge/）：
    - `raw/` 两份官方原文 txt（curl 直抓官方页面提取，UTF-8/LF）：87号令（财政部官网）+
      实施条例（gov.cn 公报）；台账（URL+获取日期+sha256）在 data/README.md，test_knowledge
      校验 sha256 与文件一致；
    - `blocks.jsonl` 16 条：87号令 8 条（第23/36/37/39/50/59/60/63 条）+ 实施条例 6 条
      （第25/26/27/39/40/51 条）status=**已核对**（官方页面逐字核验）+ 招标投标法 2 条
      （第33/34 条）status=**待核对**（flk 需 JS/gov.cn 旧链 404，公开转载转记，引擎不引用）；
    - `rules.json` 20 条 CheckRule（CHK-Q-01~05 / CHK-SR-01~03 / CHK-AR-01~03 /
      CHK-BD-01~02 / CHK-DT-01~02 / CHK-RJ-01~04 / CHK-PC-01），CHK-PC-01.params.ratio=0.8；
  - **引擎**（rules/engine.py）：`run_checks(tender, bid, *, doc_text=None, rules=None)` 投标侧
    （qualification_match/star_response/arithmetic_consistency/bond_check/date_logic(D9)/
    rejection_scan(R1 内嵌限价抽取 D12 + D4/D8/D9 隐含否决联动)/price_check(低于成本嫌疑
    <80%)）；`run_tender_checks(tender, …)` 招标侧（D10 开标早于递交截止）；分派前逐条过
    gates.rule_applies（doc_text=None → only_if 规则不激活）；只产非符合结论；
    **重要修正：87号令第37条是"视为串通投标"（不是保证金条），保证金/资格/超限价无效情形在
    第63条**——引擎引用全部落在官方逐字核验条文上；
  - **pipeline**（pipeline.py）：load → parse_tender → parse_bids → checks → aggregate 状态机
    （collusion/report 记跳过节点标注 M4/M5）；单文档解析失败落 failed 不中断；
    finding_dicts() 附 rule_type（查 rules.json）与 target（tender.md / bids/<投标人>.md）；
    out_dir 落 findings.json（无时间戳，两次运行逐字节一致）+ cards/*.card.json；
  - **CLI**：`bidchecker run <项目目录> [--out DIR]` 交付；退出码 0/1/2 定稿（0=完成、
    1=有解析失败降级、2=输入不可用），锁进 test_cli；
  - **真值对账**：多 seed（1/7/42/123/2026）× 3 演示项目，引擎四元组集合 == 真值集合
    （排除 rule_type=collusion，D11 归 M4）；demo-goods-2 干净对照零结论；basis 依据关联率
    100%（法规引用逐字命中 blocks.jsonl 或 TenderCard 条款 id）；examples 三项目经 pipeline
    与 ground_truth.json expect+also 全集合一致；
  - bench parse F1=1.0 不回退；test_package/test_cli 锁定更新（run_checks/run_pipeline 转正）；
- **git**：本地已提交；未建远端、未 push（建仓 = M6 动作）。

## 二、下一里程碑 M4（LLM 兜底 + bench e2e 达标）待办

1. **bench e2e**（bench/__init__ 扩展，口径=plan/04 §七 + datagen 真值契约）：
   - 生成器配对集（多 seed × 3 演示项目，含干净对照）→ pipeline 全链 → findings；
   - 对账口径升级：**恢复全集合**——expect_findings + also_expect **含 D11（collusion）**；
     指标 = 检出率（分缺陷类型）/ 误报数（干净对照+非目标文档）/ 判定准确率；
   - D11 围标对产出：collusion 模块按对读两份投标文本（模板句相同 + 编制时间戳同分钟），
     出一条 collusion·待人工确认·mid，target="bids/A.md|bids/B.md"（pair_target）；
     **只做文本特征，不出"围标"定性结论**（D3 合规红线；依据挂实施条例39/40条 + 87号令
     36/37条，blocks.jsonl 已入库）；
   - 门槛：检出率 ≥ 0.95、误报 0、固定 seed 可重复、零 API 依赖（规则通路不依赖 LLM）；
   - CLI `bench e2e` 转正（退出码 0/1），更新 test_cli 的 future_commands 参数化（去掉 bench）；
2. **LLM 兜底通路**（llm/client.py 已备 env 配置 + is_enabled/chat，默认关闭，D8）：
   - 解析兜底：对规则抽取失败的槽位（参数卡中值为 None 的"宁缺"位），输入候选行压缩后的
     行集合，要求返回 {field, value, quote}；quote 非原文子串即丢弃；数值过合法性校验才入卡；
   - LLM **不能改变 Finding.status**（数值与布尔类结论只由确定性规则产生）；
   - 降级测试：LLM 不可达（env 未配置/超时）时整链退化到纯规则通路，基准照常达标；
3. **知识库检索**（knowledge/search.py，plan/04 §四）：纯 Python TF 余弦 top_k，不引向量库
   （供报告层引用原文锚点与 LLM 兜底提供上下文）；
4. **补核招标投标法第33/34条**（blocks.jsonl 两条 status=待核对）：flk.npc.gov.cn 需 JS 交互
   （API 直连返回空壳）——可试 requests 带 UA/Referer 模拟、或中国政府网/人大网其他官方镜像；
   两渠道仍查不到则维持待核对并继续推进，不空转；
5. 指标写进 README（F1=1.0、e2e 检出率/误报、运行命令）；
6. DoD 全过后：写 HANDOFF-M5、回写 plan/00/05/06 状态，再结束会话。

## 三、既定口径清单（动了会打挂基准）

- `schema.py` 字段与结构 = plan/04 §1（M0 冻结，未动）；
- **真值语义**（datagen/__init__ 注释为权威）：注入缺陷记主期望（expect_findings），隐含结论记
  also_expect；**M3 对账排除 collusion，M4 bench e2e 恢复全集合（含 D11）**；四元组
  (rule_type, status, risk_level, target) 唯一；D4/D8/D9 → rejection_scan 隐含（R4/R2/R3）；
  D5 打 ▲ 无隐含；D12 主期望即 rejection_scan（R1）；D10 目标 tender.md；D11 目标围标对；
- **引擎接口口径**（=D19）：run_checks 投标侧 / run_tender_checks 招标侧分侧；doc_text=None →
  only_if 规则不激活；只产非符合结论；check_id 必须在 rules.json 注册（20 个 CHK-*）；
- **引擎引用条文 = D20**（全部官方逐字核验）：87号令 23/39/59/60/63 条 + 实施条例 51 条；
  87号令第37条=视为串通投标（围标 M4 用），保证金在 63条(一)；
- **R1 条款内嵌最高限价金额**：引擎从 R1 文本 `人民币x,xxx.00元` 抽取（schema 无预算字段）；
- ▲偏离方向语义 = D22：下限（不少于/不低于）、上限（不超过/不高于、"X日内完成"）；
  响应值更优不属偏离；数值不可提取宁缺勿错跳过；goods ▲S2 dev_pool 为更小值——未来若对
  goods 注入 D5 须先修 dev_pool 方向；
- Finding 三级判定常量与 RULE_TYPES 7 类集合不变（test_gates 锁定；collusion 是 M4 模块产出的
  rule_type 字符串，不在 RULE_TYPES 分派表内）；
- `only_if` 类目门控对全部 check_type 生效（引擎分派前必过 gates.rule_applies，test_engine 锁定）；
- **体例行级格式 = 解析接口**（templates.py 注释）；M2 解析对账口径 = D18（bench parse F1=1.0
  不回退是每次收尾的必跑项）；
- 基准门槛不放宽：解析 F1 ≥ 0.95、e2e 检出率 ≥ 0.95、误报 0、零 API 依赖；
- **examples/ 是字节冻结 fixtures**：改体例/生成器 → test_examples_fixture_frozen 会挂，属预期——
  用 `bidchecker datagen --seed 42` 重新生成后整目录提交，**禁止手改**；
- 生成路径禁 stdlib random / set 迭代 / 系统时钟（DetRng 纪律）；落盘产物（findings.json）
  不含时间戳（两次运行逐字节一致，test_pipeline 锁定）；
- 测试全离线 mock；core 零依赖（加测试期依赖必须同步 extras 并过守门测试）；
- CLI 未交付命令 = 退出码 2 + 指向 plan/05 的提示（`run` 已交付退出码 0/1/2 = D21）；
- EOL：`.gitattributes` `* text=auto eol=lf`；fixtures 出现 CR 即大声失败。

## 四、本机环境坑（只记实测过的）

- **系统 Python 3.8.8 + setuptools 49.2.1 过老**：`pip install -e .` 报 `invalid command
  'bdist_wheel'`；需先 `py -m pip install -U setuptools wheel`（75.3.4 / 0.45.1 已装，
  新机器需重装）；
- 用 `py` 不用 `python`（商店占位符）；脚本一律 `py -X utf8`（中文控制台 GBK）；
  全程 `PYTHONDONTWRITEBYTECODE=1`（pip install 也要带）；单轮崩溃/随机失败先重试再深挖；
- pip 已配置 tsinghua 镜像；若注册表系统代理污染 → 前缀 `NO_PROXY="*" no_proxy="*"`；
  （M3 实测：curl 抓 gov.cn/mof.gov.cn 官网页面需同样前缀，直抓成功）；
- `bidchecker.exe` 装到 `Python38\Scripts`（不在 PATH）→ 统一用 `py -X utf8 -m bidchecker`；
- Git Bash 以 `/` 开头的参数会被 MSYS 静默转写（路径类字面值用包含形式，"0 命中"先跑阳性对照）；
- `Path.write_text()` 在 py3.8 无 `newline` 参数——写 UTF-8/LF 统一用 `write_bytes(x.encode("utf-8"))`；
- **WebFetch 抓 flk.npc.gov.cn 与其 /api/ 端点返回空壳**（JS 渲染站点），WebFetch 对
  mof.gov.cn/gov.cn 正常；WebFetch 小模型引用限长（约 125 字/引文）——逐字条文用 curl 落盘
  后本地提取，不要靠摘要工具转述；
- **提交元数据邮箱是个人 QQ 邮箱**（06 D13）：M6 发布前必须 filter-branch 全历史改写
  GitHub noreply，本地 `git config user.email` 同步改——列入 M6 DoD。
- （M3 无其他新增坑；184 项测试 1.1s 全绿，无环境差异型失败）

## 五、M4 DoD checklist

- [ ] bench e2e 交付：多 seed 配对集全链跑通，检出率 ≥ 0.95（分缺陷类型报告）
- [ ] 干净对照误报 0；findings 与 ground_truth expect+also **含 D11 全集合**一致
- [ ] collusion 模块按对产出 待人工确认 结论（仅文本特征，挂 39/40 条，不出定性结论）
- [ ] LLM 兜底通路：默认关闭、quote ⊂ 原文硬校验、不可达降级测试；LLM 不改 status
- [ ] knowledge/search.py TF 余弦 top_k（不引向量库）
- [ ] `bench e2e` CLI 转正（退出码定稿锁进 test_cli）；指标写进 README
- [ ] pytest 全绿（现基线 184 项）；bench parse F1=1.0 不回退
- [ ] plan/00/05/06 状态回写；HANDOFF-M5 落盘

## 六、关键命令速查

```bash
cd <项目根>
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest -q               # 全量测试（基线 184 项）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker bench parse  # 解析基准（默认 5 seed，F1=1.0）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker run examples/demo-goods-1 --out output
                                                                # 端到端：findings.json + cards/ + 摘要
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker run examples/demo-goods-2 --out output  # 干净对照=0 条
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker datagen --seed 42   # 再生成 examples/
# 引擎对账取用（M4 bench e2e 同口径）：
#   from bidchecker.datagen import build_project, DEMO_PROJECTS
#   bundle = build_project(seed, spec.key, spec.category, spec.clean, spec.plan, spec.n_bids)
#   run_tender_checks(bundle.tender) + [run_checks(bundle.tender, bb.card) for bb in bundle.bids]
#   四元组 (rule_type 查 rules.json, status, risk_level, target) vs bundle.findings（M4 加回 D11）
# 知识库加载：
#   from bidchecker.knowledge import load_rules, load_blocks, find_knowledge_dir
# 校验台账 sha256（tests/test_knowledge.py::test_raw_files_ledger_sha256_matches 自动做）
# 重装（先升级构建链）：
NO_PROXY="*" no_proxy="*" py -m pip install -U setuptools wheel
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -X utf8 -m pip install -e . --no-build-isolation
```
