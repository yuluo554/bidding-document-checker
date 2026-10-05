# HANDOFF-M2 —— 解析层里程碑交接快照

> 用法（新对话续接）：`/goal 读取 <项目根>/plan/HANDOFF-M2.md 继续完成任务`（启动命令里的绝对路径由用户侧拼接，本文件内一律相对路径）。
> 落盘：2026-10-05，由完成 M1 的工作对话写入。

## 一、当前进度（M0、M1 已完成）

- **计划文档**：plan/00–06 定稿；M1 新增决策 D16/D17（体例与确定性口径、数据真值契约细化）已入 06；
- **M1 交付（已验证）**：
  - `bidchecker datagen --seed 42` 产出 3 个演示项目入 `examples/`（货物×2、服务×1；
    demo-goods-2 为干净对照），`--seed/--out` 可调；
  - 固定体例：招标 6 章 / 投标 7 章 Markdown，行级格式契约写在
    `src/bidchecker/datagen/templates.py` 模块注释（= M2 解析接口）；
  - D1–D12 缺陷注入全部实现（`datagen/defects.py`）：互斥表（D6/D7/D12 同投标互斥）、
    位置形态校验、真值四元组唯一性校验；干净对照有 `assert_clean` 结构自检；
  - `ground_truth.json`：expect_findings（主期望）+ also_expect（隐含结论）+ clean 标记；
    **真值语义与互斥坑记录全文在 `src/bidchecker/datagen/__init__.py` 模块注释**；
  - `bidchecker/amounts.py`：人民币大小写双向换算（M2 解析大写金额直接用 `words_to_amount`）；
  - `datagen/rng.py`：自研 splitmix64 确定性随机源（跨 py3.8/3.12 位级一致）；
  - 守门测试：固定 seed 两次生成位级一致 / **examples/ fixtures 字节冻结**（再生成逐字节
    比对）/ 无 CR 无 BOM / D1–D12 演示集全覆盖 / 互斥表负例 / 体例章节结构；
  - 演示数据缺陷分布（M2/M3/M4 调试速查）：demo-goods-1 = D10(招标)+D4(bid0)+D2(bid1)
    +D1(bid2)+D6(bid2)+D3(bid3)+D11(bid0↔bid1 对)；demo-services-1 = D7(bid0)+D8(bid0)
    +D5(bid1)+D9(bid1)+D12(bid2)；demo-goods-2 全净；
  - **tests 99 项全绿（0.4s）**：M0 的 30 项 + 金额 22 + datagen 守门 ~40 + CLI datagen；
- **git**：本地已提交；未建远端、未 push（建仓 = M6 动作）。

## 二、下一里程碑 M2（解析层）待办

1. `parsers/tender.py` `parse_tender(text) -> TenderCard`：normalize_text 预处理 →
   章节切分（"第X章"正则）→ 槽位抽取（头部键值行 / 1.2 资格 Q 行 / 1.3 日期行 /
   2.1 前附表 / 2.2 否决条款 R 行 / 3.1–3.2 评标分值 / 5.1 星号条款），
   每槽位带 Evidence(section, quote, line)，**quote 必须是原文子串**（基准硬校验）；
2. `parsers/bid.py` `parse_bid(text) -> BidCard`：证明材料｜四槽行 / S\<n\>：响应行与
   偏差行（同前缀靠章节树区分） / 第五章报价块（大小写↔`words_to_amount`、分项、合计） /
   第六章承诺函（有效期、保证金响应） / 第七章人员与业绩行；
3. 解析真值对账：`datagen.build_project(seed, key, ...)` 返回注入后参数卡 = 逐字段真值
   （**不经 JSON**）；建议遍历 examples 三项目 + 多 seed（1/7/42/123/2026）做回归；
4. `bidchecker bench parse`（CLI，M2 范围）：字段级 P/R/F1 输出，门槛 F1 ≥ 0.95；
5. 陷阱用例：CRLF / 零宽字符 / 全角空格（`common.normalize_text` 已备）、中文路径
   （examples 的 bids/ 文件名即中文）、抽取值合法性校验（宁缺勿错）；
6. 更新 `tests/test_package.py::test_stub_paths_raise_not_implemented`
   （parse_tender/parse_bid 转正后不再抛 NotImplementedError）；
7. `bidchecker run` 保持退出码 2（端到端引擎 M3 交付）；bench e2e 是 M4；
8. DoD 全过后：写 HANDOFF-M3、回写 plan/00/05/06 状态，再结束会话。

## 三、既定口径清单（动了会打挂基准）

- `schema.py` 字段与结构 = plan/04 §1（同 M0 冻结）；
- **真值语义**（datagen/__init__ 注释为权威）：注入缺陷记主期望，隐含结论记 also_expect
  （D4/D8/D9 → rejection_scan；D5 打 ▲ 无隐含；D12 主期望即 R1）；e2e 按"目标文档全部
  非 pass 集合"对账；四元组 (rule_type, status, risk_level, target) 唯一；
- **体例行级格式 = 解析接口**（templates.py 注释）：日期 ISO、金额 ￥x,xxx.00 + 大写、
  证明材料/人员/业绩行全角｜四槽、S\<n\>： 前缀行、头部键值行、采购类别行（=M3 门控关键词）；
- **R1 条款内嵌最高限价金额**（schema 无预算字段）——M3 引擎从 R1 文本抽取限价；
- Finding 三级判定常量与 7 种 rule_type 集合不变；
- `only_if` 类目门控对全部 check_type 生效（M3 引擎分派前必过 `rules/gates.py`）；
- 基准门槛不放宽：解析 F1 ≥ 0.95、检出率 ≥ 0.95、误报 0、零 API 依赖；
- **examples/ 是字节冻结 fixtures**：改体例/生成器 → test_examples_fixture_frozen 会挂，
  属预期——用 `bidchecker datagen --seed 42` 重新生成后整目录提交，**禁止手改**；
- 生成路径禁 stdlib random / set 迭代 / 系统时钟（DetRng 纪律，见 datagen/rng.py）；
- 测试全离线 mock；core 零依赖（加测试期依赖必须同步 extras 并过守门测试）；
- CLI 未交付命令 = 退出码 2 + 指向 plan/05 的提示（test_cli 锁定）；
- EOL：`.gitattributes` `* text=auto eol=lf`；fixtures 出现 CR 即大声失败。

## 四、本机环境坑（只记实测过的）

- **系统 Python 3.8.8 + setuptools 49.2.1 过老**：`pip install -e .` 报 `invalid command 'bdist_wheel'`；
  需先 `py -m pip install -U setuptools wheel`（75.3.4 / 0.45.1 已装，新机器需重装）；
- 用 `py` 不用 `python`（商店占位符）；脚本一律 `py -X utf8`（中文控制台 GBK）；
  全程 `PYTHONDONTWRITEBYTECODE=1`（pip install 也要带）；单轮崩溃/随机失败先重试再深挖；
- pip 已配置 tsinghua 镜像；若注册表系统代理污染 → 前缀 `NO_PROXY="*" no_proxy="*"`；
- `bidchecker.exe` 装到 `Python38\Scripts`（不在 PATH）→ 统一用 `py -X utf8 -m bidchecker`；
- Git Bash 以 `/` 开头的参数会被 MSYS 静默转写（路径类字面值用包含形式，"0 命中"先跑阳性对照）；
- **提交元数据邮箱是个人 QQ 邮箱**（06 D13）：M6 发布前必须 filter-branch 全历史改写
  GitHub noreply，本地 `git config user.email` 同步改——列入 M6 DoD。
- （M1 无新增坑；py3.8 下 f-string/dataclasses/中文路径均实测正常）

## 五、M2 DoD checklist

- [ ] parse_tender / parse_bid 交付：examples 三项目解析出完整参数卡（含 Evidence）
- [ ] 全部 Evidence.quote 为原文逐字子串（硬校验测试）
- [ ] bench parse 字段级 F1 ≥ 0.95（多 seed 回归，不挑 seed）
- [ ] 陷阱用例：CRLF/零宽/全角空格归一后可解析；中文路径读写正常
- [ ] test_package stub 锁定测试更新；pytest 全绿（现基线 99 项）
- [ ] plan/00/05/06 状态回写；HANDOFF-M3 落盘

## 六、关键命令速查

```bash
cd <项目根>
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m pytest -q               # 全量测试（基线 99 项）
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker datagen --seed 42   # 再生成 examples/
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker --version
PYTHONDONTWRITEBYTECODE=1 py -X utf8 -m bidchecker run examples/demo-goods-1   # M2 阶段仍退出码 2
# 解析真值取用（bench/回归脚本）：
#   from bidchecker.datagen import build_project, DEMO_PROJECTS
#   bundle = build_project(seed, spec.key, spec.category, spec.clean, spec.plan, spec.n_bids)
#   # bundle.tender / bundle.bids[i].card = 注入后参数卡 = 解析真值
# 重装（先升级构建链）：
NO_PROXY="*" no_proxy="*" py -m pip install -U setuptools wheel
PYTHONDONTWRITEBYTECODE=1 NO_PROXY="*" no_proxy="*" py -X utf8 -m pip install -e . --no-build-isolation
```
