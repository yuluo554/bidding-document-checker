"""招标文件解析器：固定体例 → TenderCard（plan/04 §三 五步流水线）。M2 交付。

五步：normalize_text 预处理（LineDoc 原文/归一行对齐）→ 章节切分（## 第X章锚点）
→ 槽位抽取（行级正则 + 金额/日期槽位函数）→ 合法性校验（不过即丢弃，宁缺勿错）
→ 证据绑定（Evidence.section/quote/line；quote 一律取原文行，保证 ⊂ 原文）。

槽位落点（体例契约 = datagen/templates.py 模块注释）：
- 头部键值行：项目编号/项目名称/招标人/招标代理机构（全角冒号）；
- 1.1 投标有效期行 / 1.2 资格 Q 行（尾部（类目标签，等级要求：X））/ 1.3 日期行；
- 2.1 前附表投标保证金行（表格行）；2.2 否决条款 R 行；
- 3.1 评标方法行 / 3.2 分值表行 + 价格分权重行；5.1 星号条款 ★/▲ 行。
schema 无 Evidence 槽位的字段（project/bond/key_dates/scoring）只取值不绑证据。
"""
from __future__ import annotations

import re
from typing import List, Optional

from bidchecker.parsers.common import (LineDoc, parse_amount, parse_datetime_str)
from bidchecker.schema import (CATEGORY_OTHER, Bond, Evidence, KeyDates,
                               ProjectInfo, Qualification, RejectionClause,
                               Scoring, ScoringItem, StarClause, TenderCard)

_CATEGORY_LABELS = {
    "资格类": "qualification", "财务类": "finance",
    "业绩类": "performance", "人员类": "personnel",
}

_KV_RE = re.compile(r"^(项目编号|项目名称|招标人|招标代理机构)：\s*(.+?)\s*$")
_QUAL_RE = re.compile(r"^(Q[0-9]+)[.．]\s*(.+?)\s*$")
_TAG_TAIL_RE = re.compile(r"（([^（）]*)）\s*[；;]?\s*$")
_LEVEL_IN_TAG_RE = re.compile(r"等级要求：\s*(.+?)\s*$")
_REJECTION_RE = re.compile(r"^(R[0-9]+)[.．]\s*(.+?)\s*$")
_LAW_CITE_RE = re.compile(r"《[^》]+》[^，。；]*第[0-9一二三四五六七八九十百]+条")
_STAR_RE = re.compile(r"^([★▲])\s*(S[0-9]+)：\s*(.+?)\s*$")
_METHOD_RE = re.compile(r"^评标方法：\s*(.+?)[。.]?\s*$")
_PRICE_WEIGHT_RE = re.compile(r"^价格分权重：\s*([0-9]+(?:\.[0-9]+)?)\s*%\s*[。.]?\s*$")
_VALIDITY_RE = re.compile(r"^投标有效期：自投标截止之日起\s*([0-9]+)\s*日历天\s*[。.]?\s*$")
_SUBMIT_RE = re.compile(r"投标文件递交截止时间（投标截止时间）：\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
_ISSUE_RE = re.compile(r"招标文件获取时间：\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*至")
_OPEN_RE = re.compile(r"开标时间：\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
_BOND_AMOUNT_RE = re.compile(r"金额：\s*(￥[0-9][0-9,]*\.[0-9]{2})")
_BOND_FORMS_RE = re.compile(r"形式：\s*([^；;|]+)")
_BOND_DEADLINE_RE = re.compile(r"缴纳截止时间：\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})")
_SCORE_VAL_RE = re.compile(r"^[0-9]+$")


def parse_tender(text: str) -> TenderCard:
    """招标文件全文 → 采购需求参数卡（注入缺陷原样抽出，一致性判定归 M3 引擎）。"""
    doc = LineDoc(text)
    card = TenderCard()
    _parse_header(doc, card)
    _parse_chapter1(doc, card)
    _parse_chapter2(doc, card)
    _parse_chapter3(doc, card)
    _parse_chapter5(doc, card)
    return card


# ---------------------------------------------------------------- 头部键值行
def _parse_header(doc: LineDoc, card: TenderCard) -> None:
    seen = {}
    for i, ln in enumerate(doc.norm_lines):
        m = _KV_RE.match(ln)
        if m and m.group(1) not in seen:
            seen[m.group(1)] = m.group(2).strip()
    card.project = ProjectInfo(
        name=seen.get("项目名称"), number=seen.get("项目编号"),
        buyer=seen.get("招标人"), agency=seen.get("招标代理机构"),
    )


# ---------------------------------------------------------------- 第一章：资格 + 日期
def _parse_chapter1(doc: LineDoc, card: TenderCard) -> None:
    rng = doc.chapter("第一章")
    if rng is None:
        return
    start, end, _title = rng
    for i in range(start, end):
        ln = doc.norm_lines[i]
        if card.key_dates.validity_days is None:
            m = _VALIDITY_RE.match(ln)
            if m:
                card.key_dates.validity_days = int(m.group(1))
        if card.key_dates.submit_deadline is None:
            m = _SUBMIT_RE.search(ln)
            if m:
                card.key_dates.submit_deadline = parse_datetime_str(m.group(1))
        if card.key_dates.open_time is None:
            m = _OPEN_RE.search(ln)
            if m:
                card.key_dates.open_time = parse_datetime_str(m.group(1))
        if card.key_dates.issue_start is None:
            m = _ISSUE_RE.search(ln)
            if m:
                card.key_dates.issue_start = parse_datetime_str(m.group(1))
    sec = doc.subsection(start, end, "1.2")
    if sec is not None:
        for i in range(sec[0], sec[1]):
            q = _parse_qual_line(doc.norm_lines[i])
            if q is not None:
                q.evidence = _evidence(doc, i)
                card.qualifications.append(q)


def _parse_qual_line(norm: str) -> Optional[Qualification]:
    """Q 行："Q4. 具有有效的企业信用等级证书（资格类，等级要求：AAA）；"。"""
    m = _QUAL_RE.match(norm)
    if m is None:
        return None
    item_id, rest = m.group(1), m.group(2)
    category = CATEGORY_OTHER
    level = None
    tails = list(_TAG_TAIL_RE.finditer(rest))
    if tails:
        tag = tails[-1].group(1).strip()
        rest = rest[: tails[-1].start()].rstrip("，,、 ")
        parts = [p.strip() for p in tag.split("，")]
        if parts and parts[0] in _CATEGORY_LABELS:
            category = _CATEGORY_LABELS[parts[0]]
        for p in parts[1:]:
            lm = _LEVEL_IN_TAG_RE.match(p)
            if lm:
                level = lm.group(1)
    requirement = rest.rstrip("；;。. ")
    if not requirement:
        return None
    return Qualification(item_id=item_id, requirement=requirement,
                         category=category, level=level)


# ---------------------------------------------------------------- 第二章：保证金 + 否决条款
def _parse_chapter2(doc: LineDoc, card: TenderCard) -> None:
    rng = doc.chapter("第二章")
    if rng is None:
        return
    start, end, _title = rng
    sec = doc.subsection(start, end, "2.1")
    if sec is not None:
        for i in range(sec[0], sec[1]):
            if card.bond is not None:
                break
            card.bond = _parse_bond_row(doc.norm_lines[i])
    sec = doc.subsection(start, end, "2.2")
    if sec is not None:
        for i in range(sec[0], sec[1]):
            r = _parse_rejection_line(doc.norm_lines[i])
            if r is not None:
                r.evidence = _evidence(doc, i)
                card.rejection_clauses.append(r)


def _parse_bond_row(norm: str) -> Optional[Bond]:
    """前附表行：| 投标保证金 | 金额：￥50,000.00；形式：a、b；缴纳截止时间：… |。"""
    cells = [c.strip() for c in norm.strip().split("|")]
    if len(cells) < 3 or cells[1] != "投标保证金":
        return None
    content = cells[2]
    am = _BOND_AMOUNT_RE.search(content)
    if am is None:
        return None
    amount = parse_amount(am.group(1))
    if amount is None:
        return None
    fm = _BOND_FORMS_RE.search(content)
    forms = [x.strip() for x in fm.group(1).split("、")] if fm else []
    forms = [x for x in forms if x]
    if not forms:
        return None
    dm = _BOND_DEADLINE_RE.search(content)
    deadline = parse_datetime_str(dm.group(1)) if dm else None
    return Bond(amount=amount, currency="CNY", forms=forms, deadline=deadline)


def _parse_rejection_line(norm: str) -> Optional[RejectionClause]:
    """R 行："R1. 投标报价超过最高限价（人民币3,580,000.00元）的，其投标无效。"。

    basis 依据（M3 知识库挂接前的解析口径）：条款文本含法规条号引用则取引用，
    否则招标文件中的否决条款即"招标文件自设"。
    """
    m = _REJECTION_RE.match(norm)
    if m is None:
        return None
    text = m.group(2).strip()
    if not text:
        return None
    cite = _LAW_CITE_RE.search(text)
    basis = cite.group(0) if cite else "招标文件自设"
    return RejectionClause(item_id=m.group(1), text=text, basis=basis)


# ---------------------------------------------------------------- 第三章：评标办法
def _parse_chapter3(doc: LineDoc, card: TenderCard) -> None:
    rng = doc.chapter("第三章")
    if rng is None:
        return
    start, end, _title = rng
    sec = doc.subsection(start, end, "3.1")
    if sec is not None:
        for i in range(sec[0], sec[1]):
            m = _METHOD_RE.match(doc.norm_lines[i])
            if m is not None:
                card.scoring = card.scoring or Scoring()
                if card.scoring.method is None:
                    card.scoring.method = m.group(1).strip()
    sec = doc.subsection(start, end, "3.2")
    if sec is not None:
        for i in range(sec[0], sec[1]):
            ln = doc.norm_lines[i]
            m = _PRICE_WEIGHT_RE.match(ln)
            if m is not None:
                card.scoring = card.scoring or Scoring()
                if card.scoring.price_weight is None:
                    card.scoring.price_weight = float(m.group(1))
                continue
            item = _parse_score_row(ln)
            if item is not None:
                card.scoring = card.scoring or Scoring()
                card.scoring.items.append(item)


def _parse_score_row(norm: str) -> Optional[ScoringItem]:
    """分值表行：| 技术分 | 45 |（表头/分隔行不取）。"""
    cells = [c.strip() for c in norm.strip().split("|")]
    if len(cells) < 3:
        return None
    name, val = cells[1], cells[2]
    if not name or not _SCORE_VAL_RE.match(val):
        return None
    return ScoringItem(name=name, weight=float(val))


# ---------------------------------------------------------------- 第五章：星号条款
def _parse_chapter5(doc: LineDoc, card: TenderCard) -> None:
    rng = doc.chapter("第五章")
    if rng is None:
        return
    start, end, _title = rng
    sec = doc.subsection(start, end, "5.1")
    if sec is not None:
        for i in range(sec[0], sec[1]):
            c = _parse_star_line(doc.norm_lines[i])
            if c is not None:
                c.evidence = _evidence(doc, i)
                card.star_clauses.append(c)


def _parse_star_line(norm: str) -> Optional[StarClause]:
    """星号条款行："★ S1：所投设备整体质保期不少于36个月。"（渲染期补的句号不属正文）。"""
    m = _STAR_RE.match(norm)
    if m is None:
        return None
    marker, item_id, text = m.group(1), m.group(2), m.group(3)
    if text.endswith("。"):
        text = text[:-1]
    if not text:
        return None
    return StarClause(item_id=item_id, marker=marker, text=text)


def _evidence(doc: LineDoc, idx: int) -> Evidence:
    return Evidence(section=doc.section(idx), quote=doc.quote(idx), line=idx + 1)
