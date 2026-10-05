"""招标文件解析器测试：固定体例全槽位 + 注入值原样抽出 + 证据硬校验 + 陷阱归一。"""
import re

import pytest

from bidchecker.bench import compare_fields, flatten_tender
from bidchecker.datagen import DEMO_PROJECTS, build_project
from bidchecker.datagen.templates import render_tender
from bidchecker.parsers.common import normalize_text
from bidchecker.parsers.tender import parse_tender
from bidchecker.schema import TenderCard

PROJECT_KEYS = ("demo-goods-1", "demo-goods-2", "demo-services-1")
REGRESSION_SEEDS = (1, 7, 42, 123, 2026)


def _bundle(seed=42, key="demo-goods-1"):
    spec = next(s for s in DEMO_PROJECTS if s.key == key)
    return build_project(seed, spec.key, spec.category, spec.clean, spec.plan, spec.n_bids)


def _assert_parse_equal(text, truth, doc_id="tender"):
    result = compare_fields(doc_id, flatten_tender(truth),
                            flatten_tender(parse_tender(text)))
    assert not result.mismatches, \
        "\n".join(f"{p}: 期望 {e} 实得 {a}" for p, e, a in result.mismatches)


def test_full_card_seed42_demo_goods_1():
    bundle = _bundle()
    _assert_parse_equal(render_tender(bundle), bundle.tender, "seed42/demo-goods-1/tender.md")


def test_all_slots_extracted():
    card = parse_tender(render_tender(_bundle()))
    assert card.project.number.startswith("ZB-2026-")
    assert card.project.name and card.project.buyer and card.project.agency
    assert [q.item_id for q in card.qualifications] == ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]
    q2, q4 = card.qualifications[1], card.qualifications[3]
    assert q2.category == "finance" and q2.level is None
    assert q4.requirement == "具有有效的企业信用等级证书"
    assert q4.category == "qualification" and q4.level == "AAA"
    assert card.key_dates.validity_days in (60, 90)
    assert card.key_dates.submit_deadline == card.bond.deadline
    assert card.bond.amount > 0
    assert card.bond.forms == ["银行转账", "银行保函", "保证保险"]
    assert card.scoring.method == "综合评分法"
    assert card.scoring.price_weight == 30.0
    assert sum(i.weight for i in card.scoring.items) == 100.0
    assert [c.marker for c in card.star_clauses] == ["★", "▲", "★"]
    assert card.star_clauses[0].text.endswith("个月")
    r1 = card.rejection_clauses[0]
    assert "最高限价" in r1.text and r1.basis == "招标文件自设"


def test_d10_injected_value_extracted_verbatim():
    """D10 注入痕迹必须原样抽出（解析器不做一致性判定，开标早于递交截止归 M3 引擎）。"""
    bundle = _bundle(key="demo-goods-1")
    assert bundle.tender.key_dates.open_time < bundle.tender.key_dates.submit_deadline
    _assert_parse_equal(render_tender(bundle), bundle.tender)


def test_evidence_quote_is_verbatim_substring():
    text = render_tender(_bundle())
    card = parse_tender(text)
    evs = ([q.evidence for q in card.qualifications]
           + [c.evidence for c in card.star_clauses]
           + [r.evidence for r in card.rejection_clauses])
    assert evs and all(e is not None for e in evs)
    lines = normalize_text(text).split("\n")
    for e in evs:
        assert e.quote and e.quote in text, f"quote 非原文子串: {e.quote!r}"
        assert lines[e.line - 1].strip() == e.quote, "行号未指向原文同一直行"
        assert e.section


def test_trap_crlf_zero_width_fullwidth():
    """陷阱归一：CRLF/零宽字符/全角空格/BOM 不影响字段值；quote 仍是原文子串。"""
    bundle = _bundle()
    text = render_tender(bundle)
    dirty = "\ufeff" + text.replace("项目编号：", "项目编号：\u200b") \
        .replace("。\n", "。\r\n") \
        .replace("## 第一章 招标公告", "##\u3000第一章　招标公告") \
        .replace("R2.", "R2.\u200c")
    card = parse_tender(dirty)
    _assert_parse_equal(dirty, bundle.tender, "dirty-tender")
    for q in card.qualifications:
        assert q.evidence.quote in dirty


def test_malformed_amount_dropped():
    """合法性校验（宁缺勿错）：货币符形态破坏 → 保证金槽位丢弃，不误取。"""
    text = render_tender(_bundle(key="demo-goods-2")).replace("￥", "¥")
    card = parse_tender(text)
    assert card.bond is None


def test_malformed_datetime_dropped():
    text = render_tender(_bundle(key="demo-goods-2"))
    bad = re.sub(r"(投标文件递交截止时间（投标截止时间）：)[0-9\- :]+",
                 r"\g<1>2026-13-40 99:99", text)
    card = parse_tender(bad)
    assert card.key_dates.submit_deadline is None


def test_empty_text_yields_empty_card():
    card = parse_tender("")
    assert isinstance(card, TenderCard)
    assert card.qualifications == []
    assert card.scoring is None and card.bond is None
    assert card.project.name is None


@pytest.mark.parametrize("seed", REGRESSION_SEEDS)
@pytest.mark.parametrize("key", PROJECT_KEYS)
def test_multi_seed_field_exact(seed, key):
    bundle = _bundle(seed=seed, key=key)
    _assert_parse_equal(render_tender(bundle), bundle.tender, f"seed{seed}/{key}/tender.md")
