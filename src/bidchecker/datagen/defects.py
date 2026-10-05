"""D1–D12 缺陷注入器：互斥表、真值契约、逐缺陷变更（plan/05 §1.2 / §1.4）。

真值契约（M3 引擎必须精确对齐，动了要同步引擎并重跑基准）：
- 主期望记 expect_findings；同一注入隐含的其余结论记 also_expect；
- D4/D8/D9 命中否决条款 R4/R2/R3 → 隐含 rejection_scan·不符合·high 记 also_expect；
- D5 注入 ▲ 条款（R4 只覆盖 ★，故无否决隐含）；D12 主期望即 rejection_scan（R1）；
- price_check 只做"低于成本嫌疑提示"（报价 < 80% 最高限价），D6/D7/D12 不产生额外结论；
- D10 目标是招标文件；D11 目标是围标对 "bids/A.md|bids/B.md"（M4 引擎按对出一条
  待人工确认结论）。

互斥坑记录（plan/05 §1.4"互斥坑当场记录"）：
- D6/D7/D12 都改写"开标一览表总价参数"：D6 改大写、D7 改小写与分项、D12 抬高总价——
  同一投标内两两互斥（D12 抬价后 D7 的失配会凭空出现，真值即打架），见 MUTUAL_EXCLUSIVE；
- D2（过期）与 D3（等级不足）固定打在不同证书槽（Q3=ISO9001 / Q4=信用等级），不复用槽位；
- D1 每次只清空一个业绩/人员槽（先清旧行再注入——响应行由卡片渲染，不存在文本叠写）；
- 干净对照组在构建期即断言"零期望"，防止缺陷泄漏进对照组。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Sequence, Tuple

from bidchecker.amounts import amount_to_words, render_amount
from bidchecker.datagen.entities import TEMPLATE_SENTENCES
from bidchecker.datagen.rng import DetRng
from bidchecker.datagen.spec import STAR_DEFS, ProjectBundle, TruthFinding
from bidchecker.schema import STATUS_NONCONFORM, STATUS_MANUAL

RISK_HIGH = "high"
RISK_MID = "mid"

# ---------------------------------------------------------------- 真值契约表
# defect_id → [(kind, rule_type, status, risk_level)]；kind: main=主期望 / also=隐含结论。
DEFECT_FINDINGS: Dict[str, Tuple[Tuple[str, str, str, str], ...]] = {
    "D1": (("main", "qualification_match", STATUS_NONCONFORM, RISK_HIGH),),
    "D2": (("main", "qualification_match", STATUS_NONCONFORM, RISK_HIGH),),
    "D3": (("main", "qualification_match", STATUS_NONCONFORM, RISK_MID),),
    "D4": (("main", "star_response", STATUS_NONCONFORM, RISK_HIGH),
           ("also", "rejection_scan", STATUS_NONCONFORM, RISK_HIGH)),
    "D5": (("main", "star_response", STATUS_NONCONFORM, RISK_MID),),
    "D6": (("main", "arithmetic_consistency", STATUS_NONCONFORM, RISK_HIGH),),
    "D7": (("main", "arithmetic_consistency", STATUS_NONCONFORM, RISK_HIGH),),
    "D8": (("main", "bond_check", STATUS_NONCONFORM, RISK_MID),
           ("also", "rejection_scan", STATUS_NONCONFORM, RISK_HIGH)),
    "D9": (("main", "date_logic", STATUS_NONCONFORM, RISK_MID),
           ("also", "rejection_scan", STATUS_NONCONFORM, RISK_HIGH)),
    "D10": (("main", "date_logic", STATUS_NONCONFORM, RISK_MID),),
    "D11": (("main", "collusion", STATUS_MANUAL, RISK_MID),),
    "D12": (("main", "rejection_scan", STATUS_NONCONFORM, RISK_HIGH),),
}

# 项目级互斥表：同键双方不得落在同一投标上（总价参数家族，plan/05 §1.4 点名 D6×D7）。
MUTUAL_EXCLUSIVE: Dict[str, Tuple[str, ...]] = {
    "D6": ("D7", "D12"),
    "D7": ("D6", "D12"),
    "D12": ("D6", "D7"),
}

# 位置形态：D10 只打招标文件，D11 只打投标对，其余只打单份投标。
DEFECT_LOCATION = {
    "D10": "tender", "D11": "pair",
}
_DEFAULT_LOCATION = "bid"


# ---------------------------------------------------------------- 逐缺陷注入器
def _d1_missing_qualification(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    card = bundle.bids[points[0]].card
    if rng.choice(("performance", "personnel")) == "performance":
        card.performance = []
        note = "未提供类似项目业绩（招标文件Q5要求至少1个）"
    else:
        kept = [p for p in card.personnel if "PMP" not in (p.cert_name or "")]
        assert len(kept) < len(card.personnel), "人员槽无 PMP 行可清（先清旧行再注入被破坏）"
        card.personnel = kept
        note = "未提供项目负责人PMP证书（招标文件Q6要求）"
    return [TruthFinding("D1", "main", "qualification_match", STATUS_NONCONFORM, RISK_HIGH, note=note)]


def _d2_cert_expired(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    submit = date.fromisoformat(bundle.tender.key_dates.submit_deadline[:10])
    row = _qual_row(bundle.bids[points[0]].card, "Q3")
    row.valid_until = (submit - timedelta(days=rng.choice((10, 20, 30)))).isoformat()
    note = f"ISO9001证书有效期{row.valid_until}早于投标截止{submit.isoformat()}"
    return [TruthFinding("D2", "main", "qualification_match", STATUS_NONCONFORM, RISK_HIGH, note=note)]


def _d3_level_insufficient(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    row = _qual_row(bundle.bids[points[0]].card, "Q4")
    row.level = "AA"
    note = "信用等级AA低于要求的AAA"
    return [TruthFinding("D3", "main", "qualification_match", STATUS_NONCONFORM, RISK_MID, note=note)]


def _d4_star_no_response(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    bid = bundle.bids[points[0]].card
    star_ids = [c.item_id for c in bundle.tender.star_clauses if c.marker == "★"]
    victim = rng.choice(star_ids)
    before = len(bid.star_responses)
    bid.star_responses = [r for r in bid.star_responses if r.star_id != victim]
    assert len(bid.star_responses) == before - 1, f"星号响应无 {victim} 行可清"
    return [TruthFinding("D4", "main", "star_response", STATUS_NONCONFORM, RISK_HIGH,
                         note=f"★条款{victim}未响应"),
           TruthFinding("D4", "also", "rejection_scan", STATUS_NONCONFORM, RISK_HIGH,
                         note=f"命中否决条款R4（★条款{victim}未响应）")]


def _d5_star_undeclared_deviation(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    bid = bundle.bids[points[0]].card
    clause = next(c for c in bundle.tender.star_clauses if c.marker == "▲")
    defd = next(d for d in STAR_DEFS[bundle.category] if d["item_id"] == clause.item_id)
    worse = rng.choice(defd["dev_pool"])  # 更差目标值（绝对值），方向由登记表 kind 约束
    resp = next(r for r in bid.star_responses if r.star_id == clause.item_id)
    resp.quote = defd["response"].format(v=worse)
    note = (f"▲条款{clause.item_id}响应值{worse}偏离要求值{defd['value']}，"
            "商务偏差表仍声明无偏离")
    return [TruthFinding("D5", "main", "star_response", STATUS_NONCONFORM, RISK_MID, note=note)]


def _d6_words_mismatch(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    prices = bundle.bids[points[0]].card.prices
    delta = rng.choice((10000, 20000, 50000))
    prices.total_words = amount_to_words(int(prices.total_number) - delta)
    note = (f"大写金额（{prices.total_words}）与小写金额"
            f"（{int(prices.total_number)}）不一致")
    return [TruthFinding("D6", "main", "arithmetic_consistency", STATUS_NONCONFORM, RISK_HIGH, note=note)]


def _d7_items_sum_mismatch(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    prices = bundle.bids[points[0]].card.prices
    delta = rng.choice((10000, 20000, 50000))
    new_total = int(prices.total_number) + delta
    prices.total_number = float(new_total)
    prices.total_words = amount_to_words(new_total)  # 大写随小写走：唯一失配留在 分项合计↔总价
    note = f"分项合计（{int(prices.items_sum)}）与投标总价（{new_total}）不一致"
    return [TruthFinding("D7", "main", "arithmetic_consistency", STATUS_NONCONFORM, RISK_HIGH, note=note)]


def _d8_bond_mismatch(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    bid = bundle.bids[points[0]].card
    required = bundle.tender.bond
    resp = bid.bond_response
    if rng.choice(("amount", "form")) == "amount":
        short = rng.choice((10000, 20000))
        resp.amount = float(required.amount - short)
        note = f"保证金金额{int(resp.amount)}低于要求的{int(required.amount)}"
    else:
        resp.forms = ["现金"]
        note = f"保证金形式'现金'不在允许形式{list(required.forms)}内"
    return [TruthFinding("D8", "main", "bond_check", STATUS_NONCONFORM, RISK_MID, note=note),
           TruthFinding("D8", "also", "rejection_scan", STATUS_NONCONFORM, RISK_HIGH,
                         note="命中否决条款R2（未按要求提交投标保证金）")]


def _d9_validity_insufficient(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    required = bundle.tender.key_dates.validity_days
    bid = bundle.bids[points[0]].card
    bid.key_dates.validity_days = required - 30
    note = f"投标有效期{bid.key_dates.validity_days}日历天，不足要求的{required}日历天"
    return [TruthFinding("D9", "main", "date_logic", STATUS_NONCONFORM, RISK_MID, note=note),
           TruthFinding("D9", "also", "rejection_scan", STATUS_NONCONFORM, RISK_HIGH,
                         note="命中否决条款R3（投标有效期不足）")]


def _d10_tender_date_contradiction(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    dates = bundle.tender.key_dates
    submit = datetime.fromisoformat(dates.submit_deadline)
    dates.open_time = (submit - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M")
    note = f"开标时间{dates.open_time}早于递交截止{dates.submit_deadline}"
    return [TruthFinding("D10", "main", "date_logic", STATUS_NONCONFORM, RISK_MID, note=note)]


def _d11_collusion_traces(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    sentence = rng.choice(TEMPLATE_SENTENCES)
    stamp = f"2026-10-15 10:{rng.randint(10, 59):02d}"
    for p in points:
        extras = bundle.bids[p].extras
        extras["template_sentence"] = sentence
        extras["compile_ts"] = stamp  # 覆盖各自独立的时间戳：同分钟编制特征即证据
    note = "两份投标共享同模板句与同一分钟编制时间戳"
    return [TruthFinding("D11", "main", "collusion", STATUS_MANUAL, RISK_MID, note=note)]


def _d12_over_budget(bundle: ProjectBundle, points, rng: DetRng) -> List[TruthFinding]:
    # 最高限价不在冻结 schema 里：真值经 bundle.meta["budget_cap"] 传递，
    # 文档落点 = 招标公告"最高限价"行 + R1 条款内嵌金额（M3 引擎从 R1 文本抽取）。
    cap = int(bundle.meta["budget_cap"])
    bid = bundle.bids[points[0]].card
    over = rng.choice((50000, 100000, 150000))
    new_total = cap + over
    prices = bid.prices
    prices.total_number = float(new_total)
    prices.total_words = amount_to_words(new_total)
    prices.items_sum = float(new_total)
    last = prices.items[-1]
    rest = sum(int(p.amount or 0) for p in prices.items[:-1])
    last.amount = float(new_total - rest)  # 分项同步抬平：唯一失配留给 总价↔最高限价
    note = f"投标总价{render_amount(new_total)}超过最高限价{render_amount(cap)}"
    return [TruthFinding("D12", "main", "rejection_scan", STATUS_NONCONFORM, RISK_HIGH, note=note)]


def _qual_row(card, item_id: str):
    row = next((q for q in card.qualifications if q.item_id == item_id), None)
    assert row is not None, f"投标卡缺资格行 {item_id}（先清旧行再注入被破坏）"
    return row


MUTATORS = {
    "D1": _d1_missing_qualification,
    "D2": _d2_cert_expired,
    "D3": _d3_level_insufficient,
    "D4": _d4_star_no_response,
    "D5": _d5_star_undeclared_deviation,
    "D6": _d6_words_mismatch,
    "D7": _d7_items_sum_mismatch,
    "D8": _d8_bond_mismatch,
    "D9": _d9_validity_insufficient,
    "D10": _d10_tender_date_contradiction,
    "D11": _d11_collusion_traces,
    "D12": _d12_over_budget,
}


# ---------------------------------------------------------------- 计划校验与应用
def validate_plan(plan: Sequence[Tuple[str, str]], n_bids: int) -> None:
    """注入计划静态校验：位置形态、互斥表、同目标真值四元组唯一。"""
    seen: Dict[str, set] = {}
    for location, defect_id in plan:
        if defect_id not in MUTATORS:
            raise ValueError(f"未知缺陷 {defect_id}")
        expect_kind = DEFECT_LOCATION.get(defect_id, _DEFAULT_LOCATION)
        got_kind = location.split(":")[0]
        if got_kind != expect_kind:
            raise ValueError(f"{defect_id} 期望位置 {expect_kind}，得到 {location}")
        if got_kind == "bid":
            if int(location.split(":")[1]) >= n_bids:
                raise ValueError(f"{location} 越界（n_bids={n_bids}）")
        if got_kind == "pair":
            i, j = (int(x) for x in location.split(":")[1].split("-"))
            if not (0 <= i < j < n_bids):
                raise ValueError(f"围标对 {location} 非法（n_bids={n_bids}）")
        for other_loc, other_defect in plan:
            if other_loc == location and other_defect in MUTUAL_EXCLUSIVE.get(defect_id, ()):
                raise ValueError(f"互斥缺陷同目标：{defect_id} × {other_defect} @ {location}")
        tuples = seen.setdefault(location, set())
        for kind, rule_type, status, risk in DEFECT_FINDINGS[defect_id]:
            key = (rule_type, status, risk)
            if key in tuples:
                raise ValueError(f"同目标真值四元组冲突：{key} @ {location}（{defect_id}）")
            tuples.add(key)


def parse_points(location: str) -> Tuple[int, ...]:
    """位置串 → 注入点下标：tender=() / bid:i=(i,) / pair:i-j=(i, j)。"""
    kind, _, rest = location.partition(":")
    if kind == "tender":
        return ()
    if kind == "bid":
        return (int(rest),)
    if kind == "pair":
        i, j = (int(x) for x in rest.split("-"))
        return (i, j)
    raise ValueError(f"非法位置: {location}")


def apply_plan(bundle: ProjectBundle, plan: Sequence[Tuple[str, str]],
               rng: DetRng) -> List[TruthFinding]:
    """按计划逐条注入并回填真值 target；bundle.findings 就地追加。"""
    validate_plan(plan, len(bundle.bids))
    findings: List[TruthFinding] = []
    for location, defect_id in plan:
        points = parse_points(location)
        produced = MUTATORS[defect_id](bundle, points, rng)
        for f in produced:
            if f.target == "":
                if points:
                    f.target = (bundle.pair_target(*points) if len(points) == 2
                                else bundle.bid_target(points[0]))
                else:
                    f.target = "tender.md"
            findings.append(f)
    bundle.findings.extend(findings)
    return findings
