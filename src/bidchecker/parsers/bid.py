"""投标文件解析器：固定体例 → BidCard（plan/04 §三 五步流水线）。M2 交付。

五步同 tender（LineDoc 行对齐 → 章节切分 → 槽位抽取 → 合法性校验 → 证据绑定）。

槽位落点（体例契约 = datagen/templates.py 模块注释）：
- 头部键值行：项目编号/项目名称/投标人；第一章"致："行 = 招标人；
- 第二章 证明材料行（全角｜四槽）：按出现顺序编 Q<n>（体例固定按招标侧 Q 序渲染），
  类目按证书名称关键词表推导；"不限" → None；
- 第三章 S<n>： 偏差行 / 第四章 S<n>： 响应行——同前缀靠章节树区分（4.1 小节优先）；
  location 取第四章标题主干（去（…）后缀）；
- 第五章报价块：大写（words_to_amount 仅作合法性校验，大小写是否一致归 M3 引擎判定，
  D6/D7/D12 注入值必须原样抽出）；
- 第六章承诺函：投标有效期行、保证金缴纳行；第七章人员/业绩行（- 前缀，｜四槽）。
schema 无 Evidence 槽位的字段只有值无证据；Qualification.evidence 取原文行。
"""
from __future__ import annotations

import re
from typing import Dict, Optional

from bidchecker.amounts import words_to_amount
from bidchecker.parsers.common import (LineDoc, parse_amount, parse_date_str)
from bidchecker.schema import (CATEGORY_OTHER, BidCard, Bond, Evidence,
                               KeyDates, PerfItem, PersonItem, PriceItem,
                               Prices, ProjectInfo, Qualification,
                               StarResponse)

_UNLIMITED = "不限"

_KV_RE = re.compile(r"^(项目编号|项目名称|投标人)：\s*(.+?)\s*$")
_BUYER_RE = re.compile(r"^致：\s*(.+?)\s*$")
_S_ROW_RE = re.compile(r"^(S[0-9]+)：\s*(.+?)\s*$")
_QUAL_ROW_RE = re.compile(
    r"^证明材料：\s*(.+?)\s*｜\s*编号：\s*(.+?)\s*｜\s*有效期至：\s*(.+?)\s*｜\s*等级：\s*(.+?)\s*$")
_TOTAL_WORDS_RE = re.compile(r"^投标总价（大写）：\s*人民币\s*(.+?)\s*$")
_TOTAL_NUMBER_RE = re.compile(r"^投标总价（小写）：\s*(￥[0-9][0-9,]*\.[0-9]{2})\s*$")
_PRICE_ITEM_RE = re.compile(r"^-\s*(.+?)：\s*(￥[0-9][0-9,]*\.[0-9]{2})\s*$")
_ITEMS_SUM_RE = re.compile(r"^分项合计：\s*(￥[0-9][0-9,]*\.[0-9]{2})\s*$")
_VALIDITY_RE = re.compile(r"投标有效期为自投标截止之日起\s*([0-9]+)\s*日历天")
_BOND_RESP_RE = re.compile(
    r"缴纳投标保证金\s*(￥[0-9][0-9,]*\.[0-9]{2})\s*，\s*缴纳形式：\s*([^，。；|]+)")
_PERSON_RE = re.compile(
    r"^-\s*人员：\s*(.+?)\s*｜\s*证书名称：\s*(.+?)\s*｜\s*证书编号：\s*(.+?)\s*｜\s*有效期至：\s*(.+?)\s*$")
_PERF_RE = re.compile(
    r"^-\s*业绩：\s*(.+?)\s*｜\s*合同金额：\s*(￥[0-9][0-9,]*\.[0-9]{2})\s*｜\s*签订日期：\s*"
    r"(\d{4}-\d{2}-\d{2})\s*｜\s*合同对方：\s*(.+?)\s*$")

# 证明材料名称 → 资格类目（规则优先的槽位函数词表；未命中归 other，宁缺勿错不猜）
_QUAL_CATEGORY_KEYWORDS = (
    ("ISO9001", "qualification"),
    ("营业执照", "qualification"),
    ("财务审计报告", "finance"),
    ("信用等级", "qualification"),
)


def parse_bid(text: str) -> BidCard:
    """投标文件全文 → 投标响应参数卡（注入缺陷原样抽出，一致性判定归 M3 引擎）。"""
    doc = LineDoc(text)
    card = BidCard()
    _parse_header(doc, card)
    _parse_chapter2(doc, card)
    deviations: Dict[str, str] = {}
    _parse_chapter3(doc, deviations)
    _parse_chapter4(doc, card, deviations)
    _parse_chapter5(doc, card)
    _parse_chapter6(doc, card)
    _parse_chapter7(doc, card)
    return card


def _qual_category(cert_name: str) -> str:
    for kw, category in _QUAL_CATEGORY_KEYWORDS:
        if kw in cert_name:
            return category
    return CATEGORY_OTHER


# ---------------------------------------------------------------- 头部 + 第一章
def _parse_header(doc: LineDoc, card: BidCard) -> None:
    seen = {}
    buyer = None
    for i, ln in enumerate(doc.norm_lines):
        m = _KV_RE.match(ln)
        if m and m.group(1) not in seen:
            seen[m.group(1)] = m.group(2).strip()
        if buyer is None:
            bm = _BUYER_RE.match(ln)
            if bm is not None and bm.group(1).strip():
                buyer = bm.group(1).strip()
    card.project = ProjectInfo(name=seen.get("项目名称"), number=seen.get("项目编号"),
                               buyer=buyer)
    card.bidder = seen.get("投标人")


# ---------------------------------------------------------------- 第二章：证明材料
def _parse_chapter2(doc: LineDoc, card: BidCard) -> None:
    rng = doc.chapter("第二章")
    if rng is None:
        return
    start, end, _title = rng
    for i in range(start, end):
        m = _QUAL_ROW_RE.match(doc.norm_lines[i])
        if m is None:
            continue
        requirement, _cert_no, valid_raw, level_raw = m.groups()
        valid_raw, level_raw = valid_raw.strip(), level_raw.strip()
        card.qualifications.append(Qualification(
            item_id=f"Q{len(card.qualifications) + 1}",
            requirement=requirement.strip(),
            category=_qual_category(requirement),
            level=level_raw if level_raw and level_raw != _UNLIMITED else None,
            valid_until=(parse_date_str(valid_raw)
                         if valid_raw and valid_raw != _UNLIMITED else None),
            evidence=_evidence(doc, i),
        ))


# ---------------------------------------------------------------- 第三/四章：偏差与响应
def _parse_chapter3(doc: LineDoc, deviations: Dict[str, str]) -> None:
    """商务偏差表 S<n>： 行 → {star_id: 偏差声明}（响应行建立后回挂）。"""
    rng = doc.chapter("第三章")
    if rng is None:
        return
    start, end, _title = rng
    for i in range(start, end):
        m = _S_ROW_RE.match(doc.norm_lines[i])
        if m is not None:
            star_id, val = m.group(1), m.group(2).strip()
            if val and star_id not in deviations:
                deviations[star_id] = val


def _parse_chapter4(doc: LineDoc, card: BidCard, deviations: Dict[str, str]) -> None:
    """星号条款响应行（4.1 小节优先；未设小节则回退全章）。"""
    rng = doc.chapter("第四章")
    if rng is None:
        return
    start, end, title = rng
    location = title.split("（")[0].strip()
    sec = doc.subsection(start, end, "4.1")
    if sec is not None:
        start, end = sec
    for i in range(start, end):
        m = _S_ROW_RE.match(doc.norm_lines[i])
        if m is None:
            continue
        star_id, quote = m.group(1), m.group(2).strip()
        if not quote:
            continue
        card.star_responses.append(StarResponse(
            star_id=star_id, responded=True, location=location,
            quote=quote, deviation=deviations.get(star_id)))


# ---------------------------------------------------------------- 第五章：报价块
def _parse_chapter5(doc: LineDoc, card: BidCard) -> None:
    rng = doc.chapter("第五章")
    if rng is None:
        return
    start, end, _title = rng
    prices = Prices()
    found = False
    for i in range(start, end):
        ln = doc.norm_lines[i]
        if prices.total_words is None:
            m = _TOTAL_WORDS_RE.match(ln)
            if m is not None:
                words = m.group(1).strip()
                try:
                    words_to_amount(words)
                except ValueError:
                    words = ""  # 大写规范外：宁缺勿错，留待 LLM 兜底
                if words:
                    prices.total_words = words
                    found = True
                continue
        if prices.total_number is None:
            m = _TOTAL_NUMBER_RE.match(ln)
            if m is not None:
                prices.total_number = parse_amount(m.group(1))
                found = found or prices.total_number is not None
                continue
        if prices.items_sum is None:
            m = _ITEMS_SUM_RE.match(ln)
            if m is not None:
                prices.items_sum = parse_amount(m.group(1))
                found = found or prices.items_sum is not None
                continue
        m = _PRICE_ITEM_RE.match(ln)
        if m is not None:
            amount = parse_amount(m.group(2))
            if amount is not None:
                prices.items.append(PriceItem(name=m.group(1).strip(), amount=amount))
                found = True
    if found or prices.items:
        card.prices = prices


# ---------------------------------------------------------------- 第六章：承诺函
def _parse_chapter6(doc: LineDoc, card: BidCard) -> None:
    rng = doc.chapter("第六章")
    if rng is None:
        return
    start, end, _title = rng
    for i in range(start, end):
        ln = doc.norm_lines[i]
        if card.key_dates.validity_days is None:
            m = _VALIDITY_RE.search(ln)
            if m is not None:
                card.key_dates.validity_days = int(m.group(1))
        if card.bond_response is None:
            m = _BOND_RESP_RE.search(ln)
            if m is None:
                continue
            amount = parse_amount(m.group(1))
            forms = [x.strip() for x in m.group(2).split("、") if x.strip()]
            if amount is not None and forms:
                card.bond_response = Bond(amount=amount, currency="CNY",
                                          forms=forms, deadline=None)


# ---------------------------------------------------------------- 第七章：人员与业绩
def _parse_chapter7(doc: LineDoc, card: BidCard) -> None:
    rng = doc.chapter("第七章")
    if rng is None:
        return
    start, end, _title = rng
    mode = ""
    for i in range(start, end):
        stripped = doc.norm_lines[i].strip()
        if stripped == "拟投入人员：":
            mode = "personnel"
            continue
        if stripped == "类似业绩：":
            mode = "performance"
            continue
        if mode == "personnel":
            m = _PERSON_RE.match(doc.norm_lines[i])
            if m is None:
                continue
            name, cert_name, cert_no, valid_raw = m.groups()
            valid_raw = valid_raw.strip()
            card.personnel.append(PersonItem(
                name=name.strip(), cert_name=cert_name.strip(),
                cert_no=cert_no.strip(),
                valid_until=(parse_date_str(valid_raw)
                             if valid_raw and valid_raw != _UNLIMITED else None)))
        elif mode == "performance":
            m = _PERF_RE.match(doc.norm_lines[i])
            if m is None:
                continue
            name, amount_tok, date_raw, counterparty = m.groups()
            amount = parse_amount(amount_tok)
            perf_date = parse_date_str(date_raw)
            if amount is None or perf_date is None:
                continue
            card.performance.append(PerfItem(
                name=name.strip(), amount=amount, date=perf_date,
                counterparty=counterparty.strip()))


def _evidence(doc: LineDoc, idx: int) -> Evidence:
    return Evidence(section=doc.section(idx), quote=doc.quote(idx), line=idx + 1)
