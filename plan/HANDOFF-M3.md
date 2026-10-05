# HANDOFF-M3 —— 知识与规则里程碑交接快照

> 用法（新对话续接）：`/goal 读取 <项目根>/plan/HANDOFF-M3.md 继续完成任务`（启动命令里的绝对路径由用户侧拼接，本文件内一律相对路径）。
> 落盘：2026-10-05，由完成 M2 的工作对话写入。

## 一、当前进度（M0、M1、M2 已完成）

- **计划文档**：plan/00–06 定稿；M2 新增决策 D18（解析对账口径）已入 06；
- **M2 交付（已验证）**：
  - `parsers/common.py`：normalize_text（CRLF/零宽/全角空格，M0 已备）+ **LineDoc**——
    原文行/归一行 1:1 对齐（两种归一都不动 \n）+ 章节树（`## 第X章` 锚点定位章内容区间，
    `### x.y` 小节区间）+ 金额/日期槽位校验函数（形态不符返回 None，宁缺勿错）；
  - `parsers/tender.py` `parse_tender(text) -> TenderCard`：头部键值行 / 1.2 资格 Q 行
    （尾部（类目标签，等级要求：X））/ 1.1–1.3 日期行 / 2.1 前附表保证金表格行 /
    2.2 否决条款 R 行 / 3.1–3.2 评标分值 / 5.1 星号条款；Evidence(section=最近一级标题,
    quote=原文行, line=1-based)；
  - `parsers/bid.py` `parse_bid(text) -> BidCard`：头部键值行 + 第一章"致："=招标人 /
    第二章证明材料四槽行（item_id 按体例 Q 序位置推导、类目按证书名称关键词表、
    "不限"→None）/ 第三章偏差行与第四章响应行（同 `S<n>：` 前缀靠章节树区分，
    location=第四章标题主干）/ 第五章报价块（大写用 `words_to_amount` 仅作合法性校验，
    **不做大小写一致性判定**）/ 第六章承诺函（有效期+保证金缴纳）/ 第七章人员与业绩行；
  - **注入值原样抽出**：D1–D12 的缺陷痕迹（大小写失配/分项失配/超限价/开标早于截止/
    响应行缺失等）全部如实进卡，一致性判定归 M3 引擎——解析器不产 Finding；
  - `bench/__init__.py`：`run_parse_bench` 字段级对账（口径=D18，见 bench 模块 docstring）：
    对账字段集=体例渲染进文档的字段（投标侧 agency/证书编号等无落点字段不入 scope）、
    列表行按业务键对齐、Evidence.quote⊂原文独立硬校验（违例该文档判 0）；
    `bidchecker bench parse` CLI（`--seed` 可重复 / `--threshold` / `--verbose`），
    默认 seeds=1,7,42,123,2026 × 3 演示项目 = **65 文档 4185 字段，实测 F1=1.0000，PASS**；
  - 陷阱用例全过：CRLF/零宽字符/全角空格/BOM 归一后字段值不变且 quote 仍⊂原文；
    中文路径读写正常；破坏形态的金额/日期被丢弃不误取；
  - CLI 口径更新：`run` 提示 M3 交付、退出码 2；`bench e2e` 提示 M4、退出码 2；
    裸 `bench` 退出码 2；`report`/`serve` 不变；
  - **tests 156 项全绿（0.6s）**：M1 基线 99 + 解析器 tender/bid 专测 + bench 基准
    + test_package stub 锁定更新（parse_tender/parse_bid 转正，run_checks/run_pipeline 仍锁）；
- **git**：本地已提交；未建远端、未 push（建仓 = M6 动作）。

## 二、下一里程碑 M3（知识与规则）待办

1. **data/knowledge 三层落库**（plan/04 §四）：`raw/` 法规原文 txt（来源台账：URL+获取日期
   +sha256；渠道：国家法律法规数据库 flk.npc.gov.cn、政府/部委官网；613号令/87号令/16号令/
   195号文文号与日期已核，见 plan/01 §二.5）→ `blocks.jsonl`（{law, article_no, text,
   source_url, status: 已核对|待核对}）→ `rules.json`（CheckRule[]：阈值/否决情形映射 +
   only_if.keywords）；**查不到 → status=待核对 + 显式落库，不得以确定语气写进结论**；
2. `rules/engine.py` `run_checks(tender: TenderCard, bid: BidCard) -> List[Finding]`
   （签名已被 test_package 锁定）：6 种确定性 rule_type 对应 D1–D10/D12——
   qualification_match（D1 缺业绩/缺PMP、D2 证书过期、D3 等级不足）、star_response
   （D4 缺响应、D5 ▲ 值偏离但声明无偏离）、arithmetic_consistency（D6 大小写失配、
   D7 分项合计失配）、bond_check（D8 金额短缴/形式违规）、date_logic（D9 有效期不足、
   D10 开标早于递交截止）、rejection_scan（D12 超限价；D4/D8/D9 的隐含否决结论）；
   **collusion 归 M4**（D11 按围标对产出，参数卡不含 compile_ts/模板句——M4 按对重读文本）；
3. **R1 条款内嵌限价抽取**（schema 冻结无预算字段）：M3 从 TenderCard.rejection_clauses
   R1 文本抽 "人民币3,580,000.00元" 做超限价核验；price_check 规则只做"低于成本嫌疑提示"
   （报价 < 80% 最高限价；干净报价 88%~95% 不会误触发，D6/D7/D12 不经它产额外结论）；
4. **真值契约对齐**（datagen/__init__ 注释为权威，DEFECT_FINDINGS 表）：注入缺陷必检出不
   漏报、干净对照零误报；四元组 (rule_type, status, risk_level, target) 唯一；
   Finding 构造纪律：STATUS_NONCONFORM 时 risk_level 必填、basis 非空且可解析回知识库
   条文块或 TenderCard 条款 id（**依据关联率 100%**）；
5. **类目门控**：引擎分派任何 check_type 前必过 `rules/gates.py` 的 rule_applies
   （only_if 对全部 check_type 生效；文档落点="采购类别：货物/服务"行，M2 已验证解析侧
   可从头部键值行取到该关键词）；
6. **`bidchecker run <项目目录>` 端到端**：load → parse_tender → parse_bids → checks →
   findings JSON + 摘要（pipeline.py 状态机骨架已备）；3 个演示项目跑通，findings 与
   ground_truth.json 的 expect_findings + also_expect **全集合**一致；退出码语义 M3 定稿
   并锁进 test_cli；
7. 对账单测建议：build_project 逐缺陷注入 bundle → run_checks → 与 DEFECT_FINDINGS
   四元组集合匹配（多 seed 回归，不挑 seed）；demo-goods-2 零非符合结论；
8. DoD 全过后：写 HANDOFF-M4、回写 plan/00/05/06 状态，再结束会话。

## 三、既定口径清单（动了会打挂基准）

- `schema.py` 字段与结构 = plan/04 §1（M0 冻结，未动）；
- **真值语义**（datagen/__init__ 注释为权威）：注入缺陷记主期望，隐含结论记 also_expect
  （D4/D8/D9 → rejection_scan；D5 打 ▲ 无隐含；D12 主期望即 R1）；e2e 按"目标文档全部
  非 pass 集合"对账；四元组 (rule_type, status, risk_level, target) 唯一；
- **体例行级格式 = 解析接口**（templates.py 注释）：日期 ISO、金额 ￥x,xxx.00 + 大写、
  证明材料/人员/业绩行全角｜四槽、S\<n\>： 前缀行、头部键值行、采购类别行（=M3 门控关键词）；
- **M2 解析对账口径 = D18**（bench/__init__ docstring 为实现权威）：对账字段集=文档有落点
  字段；业务键对齐；投标侧资格 item_id 按体例 Q 序位置推导、类目按证书名称关键词表；
  否决条款 basis：含法规引用取引用，否则"招标文件自设"；Evidence.quote ⊂ 原文硬校验持续
  生效；**注入值原样抽出**（引擎不得假设解析器做了任何一致性判定）；
- **R1 条款内嵌最高限价金额**（schema 无预算字段）——M3 引擎从 R1 文本抽取限价；
- Finding 三级判定常量（符合/不符合/待人工确认）与 7 种 rule_type 集合不变
  （qualification_match/star_response/arithmetic_consistency/bond_check/date_logic/
  rejection_scan/collusion）；
- `only_if` 类目门控对全部 check_type 生效（引擎分派前必过 `rules/gates.py`）；
- 基准门槛不放宽：解析 F1 ≥ 0.95（M2 实测 1.0）、检出率 ≥ 0.95、误报 0、零 API 依赖；
- **examples/ 是字节冻结 fixtures**：改体例/生成器 → test_examples_fixture_frozen 会挂，
  属预期——用 `bidchecker datagen --seed 42` 重新生成后整目录提交，**禁止手改**；
- 生成路径禁 stdlib random / set 迭代 / 系统时钟（DetRng 纪律，见 datagen/rng.py）；
- 测试全离线 mock；core 零依赖（加测试期依赖必须同步 extras 并过守门测试）；
- CLI 未交付命令 = 退出码 2 + 指向 plan/05 的提示（test_cli 锁定；`run` 现指向 M3）；
- EOL：`.gitattributes` `* text=auto eol=lf`；fixtures 出现 CR 即大声失败。

## 四、本机环境坑（只记实测过的）

- **系统 Python 3.8.8 + setuptools 49.2.1 过老**：`pip install -e .` 报 `invalid command
  'bdist_wheel'`；需先 `py -m pip install -U setuptools wheel`（75.3.4 / 0.45.1 已装，
  新机器需重装）；
- 用 `py` 不用 `python`（商店占位符）；脚本一律 `py -X utf8`（中文控制台 GBK）；
  全程 `PYTHONDONTWRITEBYTECODE=1`（pip install 也要带）；单轮崩溃/随机失败先重试再深挖；
- pip 已配置 tsinghua 镜像；若注册表系统代理污染 → 前缀 `NO_PROXY="*" no_proxy="*"`；
- `bidchecker.exe` 装到 `Python38\Scripts`（不在 PATH）→ 统一用 `py -X utf8 -m bidchecker`；
- Git Bash 以 `/` 开头的参数会被 MSYS 静默转写（路径类字面值用包含形式，"0 命中"先跑阳性对照）；
- `Path.write_text()` 在 py3.8 无 `newline` 参数——写 UTF-8/LF 统一用 `write_bytes(x.encode("utf-8"))`；
- **提交元数据邮箱是个人 QQ 邮箱**（06 D13）：M6 发布前必须 filter-branch 全历史改写
  GitHub noreply，本地 `git config user.email` 同步改——列入 M6 DoD。
- （M2 无其他新增坑；解析器 156 项测试 0.6s 全绿，无环境差异型失败）

## 五、M3 DoD checklist

- [ ] data/knowledge 三层落库：raw 台账（URL+日期+sha256）/ blocks.jsonl（status 可查）/ rules.json
- [ ] run_checks 交付：D1–D10/D12 确定性检出（真值四元组对账测试，多 seed 回归）
- [ ] 干净对照 demo-goods-2 零非符合结论（误报 0）
- [ ] only_if 类目门控对全部 check_type 生效（单测覆盖）
- [ ] Finding.basis 依据关联率 100%（可解析回知识库条文或 TenderCard 条款 id）
- [ ] `bidchecker run` 端到端跑通 3 个演示项目，findings 与 ground_truth.json 全集合一致
- [ ] pytest 全绿（现基线 156 项）；CLI 退出码语义定稿并锁定
- [ ] plan/00/05/06 状态回写；HANDOFF-M4 落盘

## 六、关键命令速查

```bash
cd <项目根>
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest -q               # 全量测试（基线 156 项）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker bench parse  # 解析基准（默认 5 seed，F1=1.0）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker bench parse --seed 42 --verbose
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker datagen --seed 42   # 再生成 examples/
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker run examples/demo-goods-1   # M3 交付后出 findings
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker --version
# 校核真值取用（引擎对账脚本）：
#   from bidchecker.datagen import build_project, DEMO_PROJECTS
#   bundle = build_project(seed, spec.key, spec.category, spec.clean, spec.plan, spec.n_bids)
#   # bundle.tender / bundle.bids[i].card = 注入后参数卡（引擎输入）
#   # bundle.findings = TruthFinding 列表（expect 四元组真值）；ground_truth.json 同源
# 重装（先升级构建链）：
NO_PROXY="*" no_proxy="*" py -m pip install -U setuptools wheel
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -X utf8 -m pip install -e . --no-build-isolation
```
