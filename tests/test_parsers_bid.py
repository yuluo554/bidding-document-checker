"""投标文件解析器测试：全槽位 + D1–D12 注入值原样抽出 + 证据硬校验 + 陷阱/中文路径。"""
import pytest

from bidchecker.bench import compare_fields, flatten_bid, flatten_tender
from bidchecker.datagen import DEMO_PROJECTS, build_project
from bidchecker.datagen.templates import render_bid, render_tender
from bidchecker.parsers.bid import parse_bid
from bidchecker.parsers.tender import parse_tender
from bidchecker.schema import BidCard

PROJECT_KEYS = ("demo-goods-1", "demo-goods-2", "demo-services-1")
REGRESSION_SEEDS = (1, 7, 42, 123, 2026)


def _bundle(seed=42, key="demo-goods-1"):
    spec = next(s for s in DEMO_PROJECTS if s.key == key)
    return build_project(seed, spec.key, spec.category, spec.clean, spec.plan, spec.n_bids)


def _assert_parse_equal(text, truth, doc_id="bid"):
    if isinstance(truth, BidCard):
        truth_flat, pred_flat = flatten_bid(truth), flatten_bid(parse_bid(text))
    else:
        truth_flat, pred_flat = flatten_tender(truth), flatten_tender(parse_tender(text))
    result = compare_fields(doc_id, truth_flat, pred_flat)
    assert not result.mismatches, \
        "\n".join(f"{p}: 期望 {e} 实得 {a}" for p, e, a in result.mismatches)


def _assert_project_equal(bundle, doc_prefix=""):
    """一个项目包内：招标卡 + 全部投标卡逐字段一致（注入值原样抽出）。"""
    _assert_parse_equal(render_tender(bundle), bundle.tender, f"{doc_prefix}tender.md")
    for i, bb in enumerate(bundle.bids):
        _assert_parse_equal(render_bid(bundle, bb), bb.card, f"{doc_prefix}bids[{i}]")


def test_all_slots_extracted():
    bundle = _bundle(key="demo-goods-2")  # 干净对照
    bid = parse_bid(render_bid(bundle, bundle.bids[0]))
    assert bid.bidder == bundle.bids[0].bidder
    assert bid.project.buyer == bundle.tender.project.buyer
    assert [q.item_id for q in bid.qualifications] == ["Q1", "Q2", "Q3", "Q4"]
    assert bid.qualifications[0].requirement == "营业执照"
    assert bid.qualifications[1].category == "finance"
    assert bid.qualifications[1].valid_until is None  # "不限" → None
    assert bid.qualifications[2].valid_until is not None
    assert bid.qualifications[3].level == "AAA"
    sr = bid.star_responses[0]
    assert sr.responded is True and sr.deviation == "无偏离"
    assert sr.location == "第四章 技术方案"
    assert sr.quote.startswith("响应。")
    prices = bid.prices
    assert prices.total_words and prices.total_number > 0
    assert len(prices.items) == 4 and prices.items_sum == prices.total_number
    assert bid.bond_response.amount == bundle.tender.bond.amount
    assert bid.bond_response.forms and bid.bond_response.deadline is None
    assert bid.key_dates.validity_days == bundle.tender.key_dates.validity_days
    assert len(bid.personnel) == 2
    assert any(p.valid_until is None for p in bid.personnel)
    assert len(bid.performance) == 1


def test_d_variants_extracted_verbatim_seed42():
    """M1 演示集全部注入缺陷（D1–D12）在 seed=42 下的解析对账（真值即注入后卡片）。"""
    for key in PROJECT_KEYS:
        _assert_project_equal(_bundle(key=key), doc_prefix=f"seed42/{key}/")


def test_d4_missing_response_row():
    """D4：★条款响应行被清——解析卡与真值同样缺失该 star_id（不存在≠漏抽）。"""
    bundle = _bundle(key="demo-goods-1")  # bid:0 注入 D4
    bb = bundle.bids[0]
    tender_ids = [c.item_id for c in bundle.tender.star_clauses]
    responded_ids = [r.star_id for r in bb.card.star_responses]
    victim = [sid for sid in tender_ids if sid not in responded_ids]
    assert len(victim) == 1, "D4 应恰好清空一条星号响应"
    bid = parse_bid(render_bid(bundle, bb))
    assert victim[0] not in [r.star_id for r in bid.star_responses]
    assert len(bid.star_responses) == len(bb.card.star_responses)


def test_d6_words_number_mismatch_preserved():
    """D6：大小写金额不一致必须双方原样抽出（解析器不做算术判定）。"""
    bundle = _bundle(key="demo-goods-1")  # bid:2 注入 D6
    bb = bundle.bids[2]
    assert bb.card.prices.total_words  # 真值本身大小写不一致
    bid = parse_bid(render_bid(bundle, bb))
    assert bid.prices.total_words == bb.card.prices.total_words
    assert bid.prices.total_number == bb.card.prices.total_number


def test_d7_items_sum_mismatch_preserved():
    bundle = _bundle(key="demo-services-1")  # bid:0 注入 D7
    bb = bundle.bids[0]
    bid = parse_bid(render_bid(bundle, bb))
    assert bid.prices.items_sum == bb.card.prices.items_sum
    assert bid.prices.total_number == bb.card.prices.total_number
    assert bb.card.prices.items_sum != bb.card.prices.total_number


def test_d5_undeclared_deviation_preserved():
    """D5：▲条款响应值偏离但偏差表仍"无偏离"——两个值都要原样抽出。"""
    bundle = _bundle(key="demo-services-1")  # bid:1 注入 D5
    bb = bundle.bids[1]
    bid = parse_bid(render_bid(bundle, bb))
    parsed = {r.star_id: r for r in bid.star_responses}
    assert all(r.deviation == "无偏离" for r in parsed.values())
    assert all(r.quote == t.quote for r, t in zip(
        sorted(parsed.values(), key=lambda r: r.star_id),
        sorted(bb.card.star_responses, key=lambda r: r.star_id)))


def test_d12_over_budget_preserved():
    bundle = _bundle(key="demo-services-1")  # bid:2 注入 D12
    bb = bundle.bids[2]
    bid = parse_bid(render_bid(bundle, bb))
    assert bid.prices.total_number == bb.card.prices.total_number
    assert bid.prices.total_number > bundle.meta["budget_cap"]


def test_evidence_quote_is_verbatim_substring():
    bundle = _bundle(key="demo-goods-1")
    for bb in bundle.bids:
        text = render_bid(bundle, bb)
        bid = parse_bid(text)
        assert bid.qualifications, f"{bb.bidder} 资格行未抽出"
        for q in bid.qualifications:
            assert q.evidence is not None
            assert q.evidence.quote and q.evidence.quote in text
            assert q.evidence.section


def test_trap_crlf_zero_width_fullwidth():
    """陷阱归一：CRLF/零宽字符/全角空格不影响字段值；quote 仍是原文子串。"""
    bundle = _bundle(key="demo-goods-2")
    bb = bundle.bids[0]
    text = render_bid(bundle, bb)
    dirty = "\ufeff" + text.replace("项目编号：", "项目编号：\u200b") \
        .replace("。\n", "。\r\n") \
        .replace("## 第二章 资格证明文件", "##\u3000第二章　资格证明文件") \
        .replace("S1：无偏离", "S1：\u200b无偏离")
    bid = parse_bid(dirty)
    _assert_parse_equal(dirty, bb.card, "dirty-bid")
    for q in bid.qualifications:
        assert q.evidence.quote in dirty


def test_chinese_path_roundtrip(tmp_path):
    """中文路径读写正常（examples 的 bids/ 文件名即中文）。"""
    bundle = _bundle(key="demo-goods-2")
    bb = bundle.bids[0]
    path = tmp_path / "演示项目" / "投标文件" / f"{bb.bidder}.md"
    path.parent.mkdir(parents=True)
    path.write_bytes(render_bid(bundle, bb).encode("utf-8"))
    text = path.read_text(encoding="utf-8")
    _assert_parse_equal(text, bb.card, f"中文路径/{bb.bidder}")


def test_empty_text_yields_empty_card():
    card = parse_bid("")
    assert isinstance(card, BidCard)
    assert card.qualifications == [] and card.prices is None
    assert card.bidder is None and card.star_responses == []


@pytest.mark.parametrize("seed", REGRESSION_SEEDS)
@pytest.mark.parametrize("key", PROJECT_KEYS)
def test_multi_seed_all_bids_field_exact(seed, key):
    _assert_project_equal(_bundle(seed=seed, key=key), doc_prefix=f"seed{seed}/{key}/")
