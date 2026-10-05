"""符合性引擎（M3）：真值四元组对账、干净对照零误报、类目门控、依据关联率。

对账口径（datagen/__init__ 真值契约 + HANDOFF-M3）：
- 真值 = build_project 返回 bundle.findings（DEFECT_FINDINGS 同源）；
- M3 对账排除 rule_type=collusion（D11 围标对归 M4 引擎产出）；
- 注入缺陷必检出不漏报、干净对照零误报，多 seed 回归不挑 seed；
- Finding.basis 依据关联率 100%：法规引用逐字命中 blocks.jsonl，条款 id 命中 TenderCard。
"""
import pytest

from bidchecker.datagen import DEFECT_FINDINGS, DEMO_PROJECTS, build_project
from bidchecker.knowledge import basis_resolves, load_blocks, load_rules
from bidchecker.rules import engine
from bidchecker.rules.engine import run_checks, run_tender_checks
from bidchecker.schema import BidCard, TenderCard

DEFAULT_SEEDS = (1, 7, 42, 123, 2026)
M3_EXCLUDED = {"collusion"}  # D11 围标对归 M4


def _rule_type_by_id():
    return {r["id"]: r.get("rule_type", "") for r in load_rules()}


def _engine_tuples(bundle, rt_by_id):
    """引擎对 bundle 的全部非符合四元组（tender 侧 + 逐投标侧）。"""
    out = set()
    for f in run_tender_checks(bundle.tender):
        out.add((rt_by_id[f.check_id], f.status, f.risk_level, "tender.md"))
    for i, bb in enumerate(bundle.bids):
        for f in run_checks(bundle.tender, bb.card):
            out.add((rt_by_id[f.check_id], f.status, f.risk_level, bundle.bid_target(i)))
    return out


def _truth_tuples(bundle):
    out = set()
    for f in bundle.findings:
        if f.rule_type in M3_EXCLUDED:
            continue
        out.add((f.rule_type, f.status, f.risk_level, f.target))
    return out


def _build(spec_idx, seed=42):
    spec = DEMO_PROJECTS[spec_idx]
    return build_project(seed, spec.key, spec.category, spec.clean,
                         spec.plan, spec.n_bids)


# ---------------------------------------------------------------- 基础行为
def test_empty_cards_produce_no_findings():
    assert run_checks(TenderCard(), BidCard()) == []
    assert run_tender_checks(TenderCard()) == []


def test_check_ids_registered_in_rules_json():
    registered = {r["id"] for r in load_rules()}
    assert registered == set(engine.CHECK_IDS)


# ---------------------------------------------------------------- 多 seed 真值对账
def test_defects_detected_and_clean_silent_multi_seed():
    """多 seed × 3 演示项目：注入缺陷四元组全检出（排除 collusion），干净对照零误报。"""
    rt_by_id = _rule_type_by_id()
    for seed in DEFAULT_SEEDS:
        for spec in DEMO_PROJECTS:
            bundle = build_project(seed, spec.key, spec.category, spec.clean,
                                   spec.plan, spec.n_bids)
            actual = _engine_tuples(bundle, rt_by_id)
            expected = _truth_tuples(bundle)
            missed = expected - actual
            false_positives = actual - expected
            assert not missed, f"seed={seed} {spec.key} 漏报: {missed}"
            assert not false_positives, f"seed={seed} {spec.key} 误报: {false_positives}"
            if spec.clean:
                assert not actual, f"seed={seed} 干净对照出现结论: {actual}"


def test_every_deterministic_rule_type_fires_across_sweep():
    """D1–D10/D12 六个确定性 rule_type 在多 seed 回归中全部被命中（防某族整体静默），
    且不出现六族之外的非符合结论类型。"""
    rt_by_id = _rule_type_by_id()
    seen = set()
    for seed in DEFAULT_SEEDS:
        for spec in DEMO_PROJECTS:
            bundle = build_project(seed, spec.key, spec.category, spec.clean,
                                   spec.plan, spec.n_bids)
            seen |= {t[0] for t in _engine_tuples(bundle, rt_by_id)}
    expected = {rows[0][1] for rows in DEFECT_FINDINGS.values()} - M3_EXCLUDED
    assert seen == expected


# ---------------------------------------------------------------- 依据关联率 100%
@pytest.mark.parametrize("seed", DEFAULT_SEEDS)
def test_basis_resolution_rate_is_100_percent(seed):
    blocks = load_blocks()
    registered = {r["id"] for r in load_rules()}
    checked = 0
    for spec in DEMO_PROJECTS:
        bundle = build_project(seed, spec.key, spec.category, spec.clean,
                               spec.plan, spec.n_bids)
        findings = list(run_tender_checks(bundle.tender))
        for bb in bundle.bids:
            findings += run_checks(bundle.tender, bb.card)
        for f in findings:
            assert f.check_id in registered, f"check_id 未注册: {f.check_id}"
            assert f.basis, f"{f.check_id} basis 为空"
            for entry in f.basis:
                assert basis_resolves(entry, blocks, bundle.tender), \
                    f"{f.check_id} basis 无法解析: {entry!r}"
                checked += 1
            assert f.message
    assert checked > 0


# ---------------------------------------------------------------- 类目门控（对全部 check_type 生效）
def _firing_fixtures():
    """多 seed 扫描出每个确定性 rule_type 的实际命中点 (seed, spec, bid 下标)。"""
    rt_by_id = _rule_type_by_id()
    fixtures = {}
    for seed in DEFAULT_SEEDS:
        for spec in DEMO_PROJECTS:
            bundle = build_project(seed, spec.key, spec.category, spec.clean,
                                   spec.plan, spec.n_bids)
            for i, bb in enumerate(bundle.bids):
                for f in run_checks(bundle.tender, bb.card):
                    rt = rt_by_id[f.check_id]
                    if rt != "price_check" and rt not in fixtures:
                        fixtures[rt] = (seed, spec, i)
    return fixtures


def _apply_price_hint_mutation(bundle):
    """干净项目上构造低于成本嫌疑报价（< 80% 最高限价；干净报价 88%~95% 不触发）。"""
    bb = bundle.bids[0]
    bb.card.prices.total_number = float(int(bundle.meta["budget_cap"]) * 70 // 100)
    bb.card.prices.total_words = None
    bb.card.prices.items_sum = float(bb.card.prices.total_number)


def test_only_if_gate_applies_to_every_rule_type():
    """引擎分派前逐条过 gates.rule_applies：only_if 不命中则该 check 不产出结论。"""
    rt_by_id = _rule_type_by_id()
    fixtures = _firing_fixtures()
    # collusion（CHK-CL-01）由 M4 collusion 模块产出，不在引擎 RULE_TYPES 分派表内
    expected_types = set(rt_by_id.values()) - {"price_check", "collusion"}
    assert expected_types <= set(fixtures), \
        f"缺少命中点的 rule_type: {expected_types - set(fixtures)}"
    fixtures["price_check"] = (42, DEMO_PROJECTS[1], 0)

    gated_rules = [{"id": r["id"], "rule_type": r.get("rule_type", ""),
                    "only_if": {"keywords": ["服务类目专属"]}} for r in load_rules()]

    for rule_type, (seed, spec, bid_idx) in fixtures.items():
        bundle = build_project(seed, spec.key, spec.category, spec.clean,
                               spec.plan, spec.n_bids)
        if rule_type == "price_check":
            _apply_price_hint_mutation(bundle)
        target_check_ids = {cid for cid, rt in rt_by_id.items() if rt == rule_type}

        def fired(doc_text):
            found = run_checks(bundle.tender, bundle.bids[bid_idx].card,
                               doc_text=doc_text, rules=gated_rules)
            return {f.check_id for f in found} & target_check_ids

        assert fired("本项目采购类别：服务类目专属"), f"{rule_type}: 门控命中时应有结论"
        assert not fired("本项目采购类别：货物"), f"{rule_type}: 门控不命中时不应有结论"
        assert not fired(None), f"{rule_type}: doc_text=None 时 only_if 规则不应激活"


# ---------------------------------------------------------------- 专项回归
def test_d5_deviation_detected_for_both_clause_forms():
    """▲偏离检出：上限形态（"不超过N小时"）与期限形态（"X日内完成"）都要检出。"""
    rt_by_id = _rule_type_by_id()
    # services ▲ S2 = "合同签订后5日内完成进场"（demo-services-1 计划内 D5，bid:1）
    bundle = _build(2)
    got = {(rt_by_id[f.check_id], f.status, f.risk_level)
           for f in run_checks(bundle.tender, bundle.bids[1].card)}
    assert ("star_response", "不符合", "mid") in got

    # goods ▲ S2 = "交货期：合同签订后60日内…"（期限形态）：手工注入更晚交付（>60）仍须检出
    bundle2 = _build(0)
    clause = next(c for c in bundle2.tender.star_clauses if c.marker == "▲")
    resp = next(r for r in bundle2.bids[0].card.star_responses if r.star_id == clause.item_id)
    resp.quote = "响应。交货期：合同签订后90日内完成供货并安装调试，满足招标文件要求。"
    got2 = {(rt_by_id[f.check_id], f.status, f.risk_level)
            for f in run_checks(bundle2.tender, bundle2.bids[0].card)}
    assert ("star_response", "不符合", "mid") in got2


def test_tender_side_d10_target_is_tender():
    bundle = _build(0)
    findings = run_tender_checks(bundle.tender)
    assert len(findings) == 1
    assert findings[0].check_id == "CHK-DT-02"
    assert findings[0].status == "不符合" and findings[0].risk_level == "mid"
    assert findings[0].basis == ["《政府采购货物和服务招标投标管理办法》第三十九条"]


def test_price_hint_and_over_cap_are_mutually_exclusive():
    rt_by_id = _rule_type_by_id()
    bundle = _build(2)
    bid = bundle.bids[2].card  # D12 超限价
    got = {rt_by_id[f.check_id] for f in run_checks(bundle.tender, bid)}
    assert "rejection_scan" in got and "price_check" not in got


def test_over_cap_uses_cap_extracted_from_r1_text():
    """D12 判定用 R1 条款内嵌限价（schema 冻结无预算字段的既定口径）。"""
    bundle = _build(2)
    bid = bundle.bids[2].card
    r1 = next(r for r in bundle.tender.rejection_clauses if "最高限价" in r.text)
    assert "人民币" in r1.text
    got = [f for f in run_checks(bundle.tender, bid) if f.check_id == "CHK-RJ-01"]
    assert len(got) == 1
    assert r1.item_id in got[0].basis
