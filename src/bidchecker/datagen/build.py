"""项目包构建：固定 seed 抽样 → 干净基线卡（schema 参数卡即解析真值）→ 注入缺陷。

构建顺序即随机源消费顺序（同 seed 逐位复现）：招标卡 → 各投标卡 → 注入计划。
干净对照（clean=True）不出计划，且构建末尾跑 assert_clean——"零误报对照组"是
结构保证而非口头承诺：任何与要求不满足方向沾边的字段都会在这里大声失败。
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from bidchecker.amounts import amount_to_words
from bidchecker.datagen import defects
from bidchecker.datagen.entities import (COUNTERPARTIES, PERSON_NAMES, cert_no,
                                         pick_bidders, pick_project_identity)
from bidchecker.datagen.rng import DetRng, project_rng
from bidchecker.datagen.spec import (PRICE_ITEMS, QUAL_DEFS, STAR_DEFS,
                                     BidBundle, ProjectBundle, rejection_texts)
from bidchecker.schema import (BidCard, Bond, KeyDates, PerfItem, PersonItem,
                               PriceItem, Prices, ProjectInfo, Qualification,
                               RejectionClause, Scoring, ScoringItem,
                               StarClause, StarResponse, TenderCard)

BUDGET_CAPS = {
    "goods": (1_980_000, 2_980_000, 3_580_000),
    "services": (880_000, 1_280_000, 1_680_000),
}
SCORING = {
    "goods": (("价格分", 30), ("技术分", 45), ("商务分", 15), ("售后服务分", 10)),
    "services": (("价格分", 30), ("技术分", 50), ("商务分", 20)),
}
BOND_FORMS = ("银行转账", "银行保函", "保证保险")
QUAL_CERT_NAMES = {
    "Q1": "营业执照",
    "Q2": "{fy}年度财务审计报告",
    "Q3": "ISO9001质量管理体系认证证书",
    "Q4": "企业信用等级证书",
}

# 合成基准日：围绕 2026 年秋（与题目定稿同期），全部由 seed 派生偏移
_BASE_DATE = date(2026, 10, 8)


def build_project(seed: int, key: str, category: str, clean: bool,
                  plan: Tuple[Tuple[str, str], ...] = (), n_bids: int = 3) -> ProjectBundle:
    """构建一个项目包（未渲染）。plan 位置串见 defects.validate_plan。"""
    if category not in STAR_DEFS:
        raise ValueError(f"未知类目: {category}")
    rng = project_rng(seed, key)
    identity = pick_project_identity(rng, category)

    issue_start = _BASE_DATE + timedelta(days=rng.randint(0, 60))
    issue_end = issue_start + timedelta(days=rng.randint(5, 8))
    submit_dt = datetime.combine(issue_start + timedelta(days=rng.randint(10, 15)), time(9, 30))
    validity = rng.choice((60, 90))
    budget_cap = rng.choice(BUDGET_CAPS[category])
    bond_amount = rng.choice((50_000, 100_000, 200_000))

    submit_str = submit_dt.strftime("%Y-%m-%d %H:%M")
    tender = TenderCard(
        project=ProjectInfo(name=identity["name"], number=identity["number"],
                            buyer=identity["buyer"], agency=identity["agency"]),
        qualifications=[
            Qualification(item_id=qid, category=cat, requirement=req, level=level)
            for qid, cat, req, level in QUAL_DEFS
        ],
        star_clauses=[
            StarClause(item_id=d["item_id"], marker=d["marker"],
                       text=d["text"].format(v=d["value"]))
            for d in STAR_DEFS[category]
        ],
        scoring=Scoring(
            method="综合评分法",
            items=[ScoringItem(name=name, weight=float(w)) for name, w in SCORING[category]],
            price_weight=30.0,
        ),
        bond=Bond(amount=float(bond_amount), currency="CNY", forms=list(BOND_FORMS),
                  deadline=submit_str),
        key_dates=KeyDates(
            issue_start=f"{issue_start.isoformat()} 09:00",
            submit_deadline=submit_str,
            open_time=submit_str,  # 干净口径：递交截止即开标；D10 注入为提前 30 分钟
            validity_days=validity,
        ),
        rejection_clauses=[
            RejectionClause(item_id=rid, text=text, basis="招标文件自设")
            for rid, text in rejection_texts(validity, budget_cap)
        ],
    )
    bundle = ProjectBundle(
        key=key, category=category, clean=clean, seed=seed, tender=tender, bids=[],
        meta={"subject": identity["subject"], "budget_cap": budget_cap,
              "issue_end": issue_end.isoformat()},
    )

    bidders = pick_bidders(rng, n_bids)
    for i, bidder in enumerate(bidders):
        bundle.bids.append(_build_bid(rng, bundle, bidder, i, submit_dt))

    if plan:
        defects.apply_plan(bundle, plan, rng)
    if clean:
        assert not bundle.findings, "干净对照组出现期望结论（缺陷泄漏）"
        assert_clean(bundle)
    return bundle


def _build_bid(rng: DetRng, bundle: ProjectBundle, bidder: str, index: int,
               submit_dt: datetime) -> BidBundle:
    t = bundle.tender
    submit_date = submit_dt.date()
    fy = submit_dt.year - 1
    cert_nos = {qid: cert_no(rng) for qid, _, _, _ in QUAL_DEFS[:4]}
    iso_valid = submit_date + timedelta(days=rng.randint(400, 700))
    credit_valid = submit_date + timedelta(days=rng.randint(300, 400))
    quals = [
        Qualification(item_id="Q1", category="qualification", requirement=QUAL_CERT_NAMES["Q1"],
                      level=None, valid_until=(submit_date + timedelta(days=1000)).isoformat()),
        Qualification(item_id="Q2", category="finance",
                      requirement=QUAL_CERT_NAMES["Q2"].format(fy=fy),
                      level=None, valid_until=None),
        Qualification(item_id="Q3", category="qualification",
                      requirement=QUAL_CERT_NAMES["Q3"], level=None,
                      valid_until=iso_valid.isoformat()),
        Qualification(item_id="Q4", category="qualification",
                      requirement=QUAL_CERT_NAMES["Q4"], level="AAA",
                      valid_until=credit_valid.isoformat()),
    ]
    star_responses = [
        StarResponse(star_id=d["item_id"], responded=True, location="第四章 技术方案",
                     quote=d["response"].format(v=d["value"]), deviation="无偏离")
        for d in STAR_DEFS[bundle.category]
    ]
    total = _total_price(rng, int(bundle.meta["budget_cap"]))
    prices = _build_prices(rng, bundle.category, total)
    names = rng.sample(PERSON_NAMES, 2)
    personnel = [
        PersonItem(name=names[0], cert_name="PMP项目管理证书",
                   cert_no=f"PMP-{rng.randint(2015, 2022)}-{rng.randint(1000, 9999)}",
                   valid_until=(submit_date + timedelta(days=rng.randint(200, 500))).isoformat()),
        PersonItem(name=names[1], cert_name="中级工程师职称证书",
                   cert_no=f"ENG-{rng.randint(2018, 2024)}-{rng.randint(1000, 9999)}",
                   valid_until=None),
    ]
    cp = rng.choice(COUNTERPARTIES)
    perf_date = date(rng.randint(2023, 2025), rng.randint(1, 12), rng.randint(1, 28))
    performance = [
        PerfItem(name=f"{cp}{bundle.meta['subject']}采购项目",
                 amount=float(rng.choice((800_000, 1_200_000, 1_500_000))),
                 date=perf_date.isoformat(), counterparty=cp),
    ]
    card = BidCard(
        project=ProjectInfo(name=t.project.name, number=t.project.number,
                            buyer=t.project.buyer, agency=t.project.agency),
        bidder=bidder,
        qualifications=quals,
        star_responses=star_responses,
        prices=prices,
        bond_response=Bond(amount=t.bond.amount, currency="CNY",
                           forms=[rng.choice(("银行转账", "银行保函"))], deadline=None),
        key_dates=KeyDates(validity_days=t.key_dates.validity_days),
        personnel=personnel,
        performance=performance,
    )
    extras: Dict[str, Any] = {
        "signer": rng.choice(PERSON_NAMES),
        "cert_nos": cert_nos,
        "voucher_no": f"PAY-2026-{rng.randint(1000, 9999)}",
        # 编制时间戳按投标序号错开（干净口径各不相同；D11 注入时被覆盖为同串）
        "compile_ts": f"2026-10-14 17:{30 + index * 7:02d}",
    }
    return BidBundle(bidder=bidder, card=card, extras=extras)


def _total_price(rng: DetRng, budget_cap: int) -> int:
    """干净总价：最高限价的 88%~95%（为 D12 留出向上越限空间，也为低于成本提示留余量）。"""
    return budget_cap * rng.choice((88, 90, 92, 95)) // 100


def _build_prices(rng: DetRng, category: str, total: int) -> Prices:
    defs = PRICE_ITEMS[category]
    items: List[PriceItem] = []
    allocated = 0
    for name, pct in defs[:-1]:
        amount = total * pct // 100
        items.append(PriceItem(name=name, amount=float(amount)))
        allocated += amount
    items.append(PriceItem(name=defs[-1][0], amount=float(total - allocated)))  # 残差找平
    return Prices(total_words=amount_to_words(total), total_number=float(total),
                  items=items, items_sum=float(total))


# ---------------------------------------------------------------- 干净对照自检
def assert_clean(bundle: ProjectBundle) -> None:
    """干净对照组结构断言：任何"非符合方向"的取值在这里大声失败（零误报的来源）。"""
    t = bundle.tender
    submit = date.fromisoformat(t.key_dates.submit_deadline[:10])
    assert t.key_dates.open_time >= t.key_dates.submit_deadline, "开标早于递交截止"
    assert t.key_dates.issue_start < t.key_dates.submit_deadline, "获取时间未早于截止"
    required_level = {q.item_id: q.level for q in t.qualifications}

    timestamps = []
    for bb in bundle.bids:
        b = bb.card
        for q in b.qualifications:
            if q.valid_until is not None:
                assert q.valid_until > submit.isoformat(), f"{bb.bidder} {q.item_id} 证书过期"
            need = required_level.get(q.item_id)
            if need:
                assert q.level == need, f"{bb.bidder} {q.item_id} 等级不足"
        assert len(b.star_responses) == len(t.star_clauses), f"{bb.bidder} 星号响应缺失"
        for d in STAR_DEFS[bundle.category]:
            r = next(r for r in b.star_responses if r.star_id == d["item_id"])
            assert r.quote == d["response"].format(v=d["value"]), f"{bb.bidder} {d['item_id']} 响应偏离"
        p = b.prices
        assert p.total_words == amount_to_words(int(p.total_number)), f"{bb.bidder} 大小写金额不一致"
        assert int(p.items_sum) == int(p.total_number), f"{bb.bidder} 分项合计与总价不一致"
        assert sum(int(i.amount) for i in p.items) == int(p.total_number), f"{bb.bidder} 分项清单与总价不一致"
        assert int(p.total_number) <= int(bundle.meta["budget_cap"]), f"{bb.bidder} 报价超最高限价"
        assert int(b.bond_response.amount) == int(t.bond.amount), f"{bb.bidder} 保证金金额不符"
        assert set(b.bond_response.forms) <= set(t.bond.forms), f"{bb.bidder} 保证金形式不符"
        assert b.key_dates.validity_days >= t.key_dates.validity_days, f"{bb.bidder} 有效期不足"
        assert any("PMP" in (x.cert_name or "") for x in b.personnel), f"{bb.bidder} 缺PMP人员"
        assert b.performance, f"{bb.bidder} 缺类似业绩"
        timestamps.append(bb.extras["compile_ts"])
    assert len(set(timestamps)) == len(timestamps), "干净对照出现重复编制时间戳"
