"""合成数据生成器（M1 核心资产）：固定 seed 产出招标/投标文件 + 真值 + 缺陷注入。

CLI：`bidchecker datagen --seed 42 [--out examples]` → 3 个演示项目（货物×2、服务×1），
其中 demo-goods-2 为干净对照组。演示集与注入计划注册表见 generator.DEMO_PROJECTS。

== 真值语义（一次定清，plan/05 §1.4；M3/M4 必须与本契约对齐）==

- 每个注入缺陷记一条**主期望**（kind=main → ground_truth.expect_findings）；
  同一注入隐含的其余结论记 **also_expect**（kind=also）；每条形如
  {defect_id, rule_type, status, risk_level, target, note}；
- 端到端基准按"目标文档全部非 pass 集合"对账：注入缺陷必检出不漏报，
  干净对照组零误报，**不是逐条一一比对**；
- 四元组 (rule_type, status, risk_level, target) 唯一确定一条期望（构建期校验唯一性）；
- 隐含结论的既定映射：D4/D8/D9 同时命中否决条款 R4/R2/R3 → 隐含
  rejection_scan·不符合·high 记 also_expect；D5 打 ▲ 条款（R4 只覆盖 ★）无隐含；
  D12 主期望即 rejection_scan（R1）；price_check 只做"低于成本嫌疑提示"
  （报价 < 80% 最高限价），D6/D7/D12 不产生额外结论；
- D10 目标是招标文件（tender.md）；D11 目标是围标对 "bids/A.md|bids/B.md"
  （M4 引擎按对产出一条 collusion·待人工确认·mid）；
- 否决条款 R1 内嵌最高限价金额（schema 冻结无预算字段）：M3 从 R1 文本抽限价。

== 互斥坑记录（plan/05 §1.4"互斥坑当场记录"）==

- D6/D7/D12 都改写"开标一览表总价参数"（D6 改大写、D7 改分项合计、D12 抬总价）：
  同一投标内两两互斥（如 D12 抬价后 D7 的失配会凭空出现，真值即打架），
  由 defects.MUTUAL_EXCLUSIVE + validate_plan 静态拦截；
- D2（证书过期）与 D3（等级不足）固定打不同证书槽（Q3=ISO9001 / Q4=信用等级），不复用；
- D1 每次只清空一个业绩/人员槽——"先清旧行再注入"：响应内容全部由卡片渲染产生，
  不存在文本层叠写（渲染期参数化替代文本后改写）；
- 多值字段封顶：类目条款池固定槽位（Q1–Q6、S1–S3、R1–R4、分项 4 项），注入按槽位
  精确改写，不做列表级模糊追加；
- 干净对照组构建期跑 assert_clean（build.py）：任何"非符合方向"的取值当场大声失败，
  对照组零误报是结构保证。

== 解析真值契约（M2 bench parse）==

build_project(...) 返回注入后的 schema.TenderCard / schema.BidCard——文档由卡片渲染，
卡片即逐字段解析真值（F1 对账直接用卡对象，不经 JSON）；Evidence 由解析器自行给出，
基准另按 quote⊂原文 硬校验。

== 确定性纪律 ==

- 随机源：datagen/rng.py 自研 splitmix64（stdlib random 不承诺跨版本序列一致），
  各项目按 (seed, project_key) 派生子源；生成路径禁用 random 模块与 set 迭代
  （PYTHONHASHSEED 跨进程不一致）；实体池一律 tuple；
- 内容零时钟、金额整数运算、文件 write_bytes（UTF-8 无 BOM、\n 换行）——
  固定 seed 两次生成位级一致（tests/test_datagen.py 守门）；
- examples/ 下的演示包是"字节冻结 fixtures"：与 seed=42 再生成逐字节比对，手改即挂。

== 体例契约（M2 解析接口）==

行级格式（日期 ISO、｜分隔四槽行、S<n>：前缀行等）见 templates.py 模块注释；
招标 6 章 / 投标 7 章标题是解析器章节树锚点；"采购类别：货物/服务"行即 M3
only_if 类目门控关键词的文档落点。
"""
from bidchecker.datagen.build import assert_clean, build_project
from bidchecker.datagen.defects import (DEFECT_FINDINGS, MUTUAL_EXCLUSIVE,
                                        MUTATORS, validate_plan)
from bidchecker.datagen.generator import (DEMO_PROJECTS, DemoSpec, build_ground_truth,
                                          generate_project_package, run_datagen)
from bidchecker.datagen.spec import BidBundle, ProjectBundle, TruthFinding

__all__ = [
    "run_datagen", "generate_project_package", "build_ground_truth",
    "build_project", "assert_clean",
    "DEMO_PROJECTS", "DemoSpec",
    "DEFECT_FINDINGS", "MUTUAL_EXCLUSIVE", "MUTATORS", "validate_plan",
    "BidBundle", "ProjectBundle", "TruthFinding",
]
