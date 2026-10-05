"""符合性校核引擎（plan/04 §二）：按 rule_type 分派确定性 handler。M3 交付。

口径（与 datagen/__init__ 真值契约、HANDOFF-M3 对齐）：
- :func:`run_checks`（tender, bid）做**投标侧**六类检查（D1–D9/D12 及隐含否决结论）；
  **招标侧**检查（D10 开标早于递交截止）在 :func:`run_tender_checks`——target 归因
  （tender.md / bids/<投标人>.md）由分侧天然确定，pipeline 不做猜测；
- 门控：分派任何 check_type 前逐条过 :func:`gates.rule_applies`（only_if 类目隔离，
  对全部 rule_type 生效）。门控文本 doc_text 由调用方传原文；缺省 None 视为空文本——
  带 only_if 的规则一律不激活（宁缺勿错），无 only_if 规则恒激活；
- 结论：只产"非符合"结论（不符合/待人工确认），符合明细由报告层（M5）按需展开；
  数值与布尔类判定只由本引擎产生（解析器注入值原样抽出，不做一致性判定）；
- 依据关联率 100%（tests/test_engine 对账）：Finding.basis 仅两类取值——法规引用
  "《法规名》第X条"（逐字命中 data/knowledge/blocks.jsonl 条文块）或 TenderCard 条款
  id（Q*/S*/R*）；check_id 必须在 rules.json 注册（21 个 CHK-*，含 M4 围标提示
  CHK-CL-01——该条由 collusion 模块产出，rule_type=collusion 不在本引擎
  RULE_TYPES 分派表内，见 HANDOFF-M4）；
- 查不到的确定性输入一律跳过不硬判（宁缺勿错，留待 M4 LLM 兜底或人工）。

rules.json 里本引擎引用的阈值参数（params）：CHK-PC-01.ratio = 低于成本嫌疑比例（0.8）。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from bidchecker.amounts import render_amount, words_to_amount
from bidchecker.knowledge import load_rules
from bidchecker.rules.gates import rule_applies
from bidchecker.schema import (BidCard, Finding, Qualification, TenderCard,
                               STATUS_MANUAL, STATUS_NONCONFORM)

RULE_TYPES = (
    "qualification_match",
    "star_response",
    "arithmetic_consistency",
    "date_logic",
    "bond_check",
    "rejection_scan",
    "price_check",
)

# ---------------------------------------------------------------- 法规引用（blocks.jsonl 同名键）
# 全部条目已在官方渠道逐字核验（2026-10-05）：87号令=财政部官网、实施条例=中国政府网公报；
# 《招标投标法》条文官方直连未获（flk 数据库 JS 不可直连）→ blocks.jsonl 标"待核对"，引擎不引用。
LAW_TENDER_LAW = "中华人民共和国招标投标法"
LAW_IMPL_REG = "招标投标法实施条例"
LAW_87 = "政府采购货物和服务招标投标管理办法"

CITE_IMPL_REJECT = "《%s》第五十一条" % LAW_IMPL_REG  # 否决投标情形（资格/超限价/实质响应）
CITE_87_VALIDITY = "《%s》第二十三条" % LAW_87        # 承诺有效期不得少于招标文件载明
CITE_87_OPEN = "《%s》第三十九条" % LAW_87            # 开标=截止同一时间进行
CITE_87_PRICE_FIX = "《%s》第五十九条" % LAW_87       # 报价前后不一致修正（大写金额优先）
CITE_87_LOW_PRICE = "《%s》第六十条" % LAW_87         # 明显低价：书面说明+证明，否则无效
CITE_87_INVALID = "《%s》第六十三条" % LAW_87         # 投标无效情形（保证金/资格/超限价）

# ---------------------------------------------------------------- check_id 注册表（rules.json 同名）
CHK_Q_MISSING = "CHK-Q-01"        # 资格/财务类证明材料缺失
CHK_Q_EXPIRED = "CHK-Q-02"        # 证书过期（早于投标截止/要求有效期）
CHK_Q_LEVEL = "CHK-Q-03"          # 资质等级不足
CHK_Q_PERF = "CHK-Q-04"           # 业绩类要求未满足
CHK_Q_PERSONNEL = "CHK-Q-05"      # 人员类要求未满足
CHK_SR_MISSING = "CHK-SR-01"      # 星号条款未响应
CHK_SR_DEV = "CHK-SR-02"          # 星号条款响应值偏离且未如实声明
CHK_SR_DECLARED = "CHK-SR-03"     # ▲条款声明负偏离（提请人工确认是否接受）
CHK_AR_WORDS = "CHK-AR-01"        # 大写金额与小写金额不一致
CHK_AR_SUM = "CHK-AR-02"          # 分项合计与投标总价不一致
CHK_AR_ITEMS = "CHK-AR-03"        # 分项明细合计与分项合计不一致
CHK_BD_AMOUNT = "CHK-BD-01"       # 保证金金额低于要求
CHK_BD_FORM = "CHK-BD-02"         # 保证金形式不在允许形式内
CHK_DT_VALIDITY = "CHK-DT-01"     # 投标有效期不足
CHK_DT_ORDER = "CHK-DT-02"        # 开标时间早于递交截止（招标侧）
CHK_RJ_CAP = "CHK-RJ-01"          # 投标报价超过最高限价（R1）
CHK_RJ_BOND = "CHK-RJ-02"         # 未按要求提交保证金 → 否决联动（R2）
CHK_RJ_VALIDITY = "CHK-RJ-03"     # 投标有效期不足 → 否决联动（R3）
CHK_RJ_STAR = "CHK-RJ-04"         # ★条款不满足/未响应 → 否决联动（R4）
CHK_PC_LOW = "CHK-PC-01"          # 低于成本嫌疑提示（报价 < ratio × 最高限价）
CHK_CL_PAIRS = "CHK-CL-01"        # 围标文本特征提示（collusion 模块产出，非本引擎分派）

CHECK_IDS = (
    CHK_Q_MISSING, CHK_Q_EXPIRED, CHK_Q_LEVEL, CHK_Q_PERF, CHK_Q_PERSONNEL,
    CHK_SR_MISSING, CHK_SR_DEV, CHK_SR_DECLARED,
    CHK_AR_WORDS, CHK_AR_SUM, CHK_AR_ITEMS,
    CHK_BD_AMOUNT, CHK_BD_FORM,
    CHK_DT_VALIDITY, CHK_DT_ORDER,
    CHK_RJ_CAP, CHK_RJ_BOND, CHK_RJ_VALIDITY, CHK_RJ_STAR,
    CHK_PC_LOW, CHK_CL_PAIRS,
)

# 信用等级有序量表（可比较时按序比较；表外等级退化为等值比较）
LEVEL_RANK = {"C": 1, "CC": 2, "CCC": 3, "B": 4, "BB": 5, "BBB": 6,
              "A": 7, "AA": 8, "AAA": 9}

_STAR_VALUE_RE = re.compile(r"([0-9]+)\s*(个月|日内|天内|小时|分钟|天|日)")
_YEAR_RE = re.compile(r"(20[0-9]{2})年")
_AT_LEAST_RE = re.compile(r"至少\s*([0-9]+)\s*个")
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_CAP_RE = re.compile(r"人民币\s*([0-9][0-9,]*)\.([0-9]{2})\s*元")

_AMT_EPS = 0.005  # 金额比较容差（半分）


def run_checks(tender: TenderCard, bid: BidCard, *, doc_text: Optional[str] = None,
               rules: Optional[List[Dict[str, Any]]] = None) -> List[Finding]:
    """TenderCard + BidCard → List[Finding]（投标侧确定性检查，见模块 docstring 口径）。"""
    ck = _Checker(tender, bid, doc_text, rules)
    ck.check_qualifications()
    ck.check_star_responses()
    ck.check_arithmetic()
    ck.check_bond()
    ck.check_dates()
    ck.check_rejections()
    ck.check_price_hint()
    return ck.findings


def run_tender_checks(tender: TenderCard, *, doc_text: Optional[str] = None,
                      rules: Optional[List[Dict[str, Any]]] = None) -> List[Finding]:
    """TenderCard → List[Finding]（招标侧确定性检查：D10 时间顺序）。"""
    ck = _Checker(tender, None, doc_text, rules)
    ck.check_tender_dates()
    return ck.findings


class _Checker:
    """单次校核上下文：规则注册表 + 门控文本 + 违规旗标（否决联动用）。"""

    def __init__(self, tender: TenderCard, bid: Optional[BidCard],
                 doc_text: Optional[str], rules: Optional[List[Dict[str, Any]]]):
        self.tender = tender
        self.bid = bid
        self.doc_text = doc_text or ""
        resolved = list(rules) if rules is not None else load_rules()
        self._by_id: Dict[str, Dict[str, Any]] = {
            r.get("id"): r for r in resolved if isinstance(r, dict) and r.get("id")
        }
        self.findings: List[Finding] = []
        self.flags: Dict[str, Any] = {}
        self._clause_cache: Dict[str, Any] = {}

    # ---------------------------------------------------------------- 基础设施
    def _active(self, check_id: str) -> bool:
        """分派门控：规则带 only_if 时关键词必须全部命中门控文本（plan/04 §2.2）。"""
        rule = self._by_id.get(check_id)
        if rule is None:
            return True  # 未注册规则恒激活；注册缺失由依据关联率测试把关
        return rule_applies(rule, self.doc_text)

    def _param(self, check_id: str, key: str, default: Any) -> Any:
        rule = self._by_id.get(check_id) or {}
        params = rule.get("params") or {}
        return params.get(key, default)

    def emit(self, check_id: str, rule_type: str, status: str, risk_level: str,
             basis: List[str], message: str, evidence: Optional[List[Any]] = None) -> None:
        self.findings.append(Finding(
            check_id=check_id, status=status, risk_level=risk_level,
            message=message, basis=list(basis),
            evidence=[e for e in (evidence or ()) if e is not None],
        ))

    def _rejection_clause(self, *keywords: str):
        """按文本关键词定位否决条款（R1–R4 由文本语义识别，不硬编码条号顺序）。"""
        key = "|".join(keywords)
        if key not in self._clause_cache:
            self._clause_cache[key] = next(
                (r for r in self.tender.rejection_clauses
                 if any(kw in r.text for kw in keywords)), None)
        return self._clause_cache[key]

    def _price_cap(self) -> Optional[float]:
        """最高限价：从否决条款"最高限价（人民币x,xxx.00元）"内嵌金额抽取（既定口径）。"""
        clause = self._rejection_clause("最高限价")
        if clause is None:
            return None
        m = _CAP_RE.search(clause.text)
        if m is None:
            return None
        try:
            return float(f"{m.group(1).replace(',', '')}.{m.group(2)}")
        except ValueError:
            return None

    # ---------------------------------------------------------------- 招标侧
    def check_tender_dates(self) -> None:
        kd = self.tender.key_dates
        if not self._active(CHK_DT_ORDER):
            return
        if kd.open_time and kd.submit_deadline and kd.open_time < kd.submit_deadline:
            self.emit(CHK_DT_ORDER, "date_logic", STATUS_NONCONFORM, "mid",
                      [CITE_87_OPEN],
                      f"开标时间 {kd.open_time} 早于投标文件递交截止时间 {kd.submit_deadline}")

    # ---------------------------------------------------------------- 资格比对（D1/D2/D3）
    def check_qualifications(self) -> None:
        bid_rows = {q.item_id: q for q in (self.bid.qualifications or [])}
        for tq in self.tender.qualifications:
            bid_row = bid_rows.get(tq.item_id)
            if tq.category in ("qualification", "finance"):
                if bid_row is None:
                    if self._active(CHK_Q_MISSING):
                        self.emit(CHK_Q_MISSING, "qualification_match", STATUS_NONCONFORM,
                                  "high", [tq.item_id, CITE_87_INVALID],
                                  f"资格证明材料缺失：招标文件{tq.item_id}要求"
                                  f"“{tq.requirement}”，投标文件未提供对应证明材料",
                                  self._qual_evidence(tq, bid_row))
                    continue
                self._check_qual_validity(tq, bid_row)
                if tq.level:
                    self._check_qual_level(tq, bid_row)
            elif tq.category == "performance":
                self._check_performance(tq)
            elif tq.category == "personnel":
                self._check_personnel(tq)

    def _qual_evidence(self, tq: Qualification, bid_row: Optional[Qualification]):
        ev = []
        if bid_row is not None and bid_row.evidence is not None:
            ev.append(bid_row.evidence)
        if tq.evidence is not None:
            ev.append(tq.evidence)
        return ev

    def _check_qual_validity(self, tq: Qualification, bid_row: Qualification) -> None:
        if not self._active(CHK_Q_EXPIRED) or not bid_row.valid_until:
            return
        submit = self.tender.key_dates.submit_deadline
        deadline = submit[:10] if submit else None
        if tq.valid_until and (deadline is None or tq.valid_until < deadline):
            deadline = tq.valid_until
        if deadline and bid_row.valid_until < deadline:
            self.emit(CHK_Q_EXPIRED, "qualification_match", STATUS_NONCONFORM, "high",
                      [tq.item_id, CITE_87_INVALID],
                      f"{tq.item_id} 证明材料有效期至 {bid_row.valid_until}，"
                      f"早于要求的生效截止 {deadline}",
                      self._qual_evidence(tq, bid_row))

    def _check_qual_level(self, tq: Qualification, bid_row: Qualification) -> None:
        if not self._active(CHK_Q_LEVEL):
            return
        required, held = tq.level, bid_row.level
        if held is None:
            self.emit(CHK_Q_LEVEL, "qualification_match", STATUS_NONCONFORM, "mid",
                      [tq.item_id, CITE_87_INVALID],
                      f"{tq.item_id} 要求资质等级 {required}，投标文件未提供等级信息",
                      self._qual_evidence(tq, bid_row))
            return
        req_rank, held_rank = LEVEL_RANK.get(required), LEVEL_RANK.get(held)
        if req_rank is not None and held_rank is not None:
            insufficient = held_rank < req_rank
        else:
            insufficient = held != required
        if insufficient:
            self.emit(CHK_Q_LEVEL, "qualification_match", STATUS_NONCONFORM, "mid",
                      [tq.item_id, CITE_87_INVALID],
                      f"{tq.item_id} 资质等级 {held} 低于要求的 {required}",
                      self._qual_evidence(tq, bid_row))

    def _check_performance(self, tq: Qualification) -> None:
        if not self._active(CHK_Q_PERF):
            return
        perfs = self.bid.performance or []
        need = int(_AT_LEAST_RE.search(tq.requirement).group(1)) \
            if _AT_LEAST_RE.search(tq.requirement) else 1
        if not perfs:
            self.emit(CHK_Q_PERF, "qualification_match", STATUS_NONCONFORM, "high",
                      [tq.item_id, CITE_87_INVALID],
                      f"未提供类似项目业绩（招标文件{tq.item_id}要求：{tq.requirement}）")
            return
        year = _YEAR_RE.search(tq.requirement)
        if year is not None:
            since = f"{year.group(1)}-01-01"
            valid = [p for p in perfs if (p.date or "") >= since]
            if len(valid) < need:
                self.emit(CHK_Q_PERF, "qualification_match", STATUS_NONCONFORM, "high",
                          [tq.item_id, CITE_87_INVALID],
                          f"类似业绩签订日期早于 {since} 的超出允许数量：{tq.item_id} 要求 "
                          f"{year.group(1)}年以来至少 {need} 个，仅 {len(valid)} 个符合")

    def _check_personnel(self, tq: Qualification) -> None:
        if not self._active(CHK_Q_PERSONNEL):
            return
        people = self.bid.personnel or []
        if not people:
            self.emit(CHK_Q_PERSONNEL, "qualification_match", STATUS_NONCONFORM, "high",
                      [tq.item_id, CITE_87_INVALID],
                      f"未提供拟投入人员信息（招标文件{tq.item_id}要求：{tq.requirement}）")
            return
        for token in _LATIN_TOKEN_RE.findall(tq.requirement):
            if not any(token in (p.cert_name or "") for p in people):
                self.emit(CHK_Q_PERSONNEL, "qualification_match", STATUS_NONCONFORM,
                          "high", [tq.item_id, CITE_87_INVALID],
                          f"未提供“{token}”人员证书（招标文件{tq.item_id}要求：{tq.requirement}）")

    # ---------------------------------------------------------------- 星号条款（D4/D5）
    def check_star_responses(self) -> None:
        by_id = {r.star_id: r for r in (self.bid.star_responses or [])}
        for clause in self.tender.star_clauses:
            resp = by_id.get(clause.item_id)
            if resp is None:
                self._star_missing(clause)
                continue
            required = _star_value(clause.text)
            actual = _star_value(resp.quote or "")
            if required is None or actual is None or required[1] != actual[1]:
                continue  # 数值/单位不可提取：宁缺勿错，留待 M4 LLM 兜底
            if not _star_violated(clause.text, required[0], actual[0]):
                continue
            declared = bool(resp.deviation and resp.deviation.strip() != "无偏离")
            if clause.marker == "★":
                self.flags["star_rejection"] = clause
                detail = "，且商务偏差表声明无偏离" if not declared else ""
                self.emit(CHK_SR_DEV, "star_response", STATUS_NONCONFORM, "high",
                          [clause.item_id],
                          f"★条款{clause.item_id}响应值 {actual[0]}{actual[1]} 不满足要求值 "
                          f"{required[0]}{required[1]}{detail}（{clause.text}）",
                          [clause.evidence])
            elif declared:
                self.emit(CHK_SR_DECLARED, "star_response", STATUS_MANUAL, "low",
                          [clause.item_id],
                          f"▲条款{clause.item_id}响应值 {actual[0]}{actual[1]} 偏离要求值 "
                          f"{required[0]}{required[1]}，已声明负偏离，是否接受提请人工确认"
                          f"（{clause.text}）",
                          [clause.evidence])
            else:
                self.emit(CHK_SR_DEV, "star_response", STATUS_NONCONFORM, "mid",
                          [clause.item_id],
                          f"▲条款{clause.item_id}响应值 {actual[0]}{actual[1]} 偏离要求值 "
                          f"{required[0]}{required[1]}，商务偏差表仍声明无偏离"
                          f"（{clause.text}）",
                          [clause.evidence])

    def _star_missing(self, clause) -> None:
        if not self._active(CHK_SR_MISSING):
            return
        if clause.marker == "★":
            self.flags["star_rejection"] = clause
            self.emit(CHK_SR_MISSING, "star_response", STATUS_NONCONFORM, "high",
                      [clause.item_id],
                      f"★条款{clause.item_id}未响应（{clause.text}）",
                      [clause.evidence])
        else:
            self.emit(CHK_SR_MISSING, "star_response", STATUS_NONCONFORM, "mid",
                      [clause.item_id],
                      f"▲条款{clause.item_id}未响应（{clause.text}）",
                      [clause.evidence])

    # ---------------------------------------------------------------- 算术复核（D6/D7）
    def check_arithmetic(self) -> None:
        p = self.bid.prices
        if p is None:
            return
        if self._active(CHK_AR_WORDS) and p.total_words and p.total_number is not None:
            try:
                words_val = words_to_amount(p.total_words)
            except ValueError:
                words_val = None
            if words_val is not None and abs(words_val - p.total_number) > _AMT_EPS:
                self.emit(CHK_AR_WORDS, "arithmetic_consistency", STATUS_NONCONFORM,
                          "high", [CITE_87_PRICE_FIX],
                          f"大写金额（{p.total_words}）与小写金额"
                          f"（{render_amount(p.total_number)}）不一致")
        if self._active(CHK_AR_SUM) and p.items_sum is not None \
                and p.total_number is not None \
                and abs(p.items_sum - p.total_number) > _AMT_EPS:
            self.emit(CHK_AR_SUM, "arithmetic_consistency", STATUS_NONCONFORM, "high",
                      [CITE_87_PRICE_FIX],
                      f"分项合计（{render_amount(p.items_sum)}）与投标总价"
                      f"（{render_amount(p.total_number)}）不一致")
        if self._active(CHK_AR_ITEMS) and p.items and p.items_sum is not None:
            items_total = sum(float(i.amount or 0) for i in p.items)
            if abs(items_total - p.items_sum) > _AMT_EPS:
                self.emit(CHK_AR_ITEMS, "arithmetic_consistency", STATUS_NONCONFORM,
                          "high", [CITE_87_PRICE_FIX],
                          f"分项明细合计（{render_amount(items_total)}）与分项合计"
                          f"（{render_amount(p.items_sum)}）不一致")

    # ---------------------------------------------------------------- 保证金（D8）
    def check_bond(self) -> None:
        req = self.tender.bond
        resp = self.bid.bond_response
        if req is None or resp is None:
            return  # 缺缴纳响应：解析层缺口宁缺勿错（M4 LLM 兜底），不硬判
        clause = self._rejection_clause("保证金")
        basis = [clause.item_id, CITE_87_INVALID] if clause is not None else [CITE_87_INVALID]
        if self._active(CHK_BD_AMOUNT) and resp.amount is not None \
                and req.amount is not None and resp.amount < req.amount - _AMT_EPS:
            self.flags["bond"] = True
            self.emit(CHK_BD_AMOUNT, "bond_check", STATUS_NONCONFORM, "mid", basis,
                      f"投标保证金 {render_amount(resp.amount)} 低于要求的 "
                      f"{render_amount(req.amount)}")
        if self._active(CHK_BD_FORM) and resp.forms:
            invalid = [f for f in resp.forms if f not in (req.forms or [])]
            if invalid:
                self.flags["bond"] = True
                self.emit(CHK_BD_FORM, "bond_check", STATUS_NONCONFORM, "mid", basis,
                          f"保证金缴纳形式“{'、'.join(invalid)}”不在允许形式"
                          f"（{'、'.join(req.forms)}）内")

    # ---------------------------------------------------------------- 时间逻辑（D9）
    def check_dates(self) -> None:
        required = self.tender.key_dates.validity_days
        actual = self.bid.key_dates.validity_days
        if not self._active(CHK_DT_VALIDITY):
            return
        clause = self._rejection_clause("有效期")
        if required and actual is not None and actual < required and clause is not None:
            self.flags["validity"] = True
            self.emit(CHK_DT_VALIDITY, "date_logic", STATUS_NONCONFORM, "mid",
                      [clause.item_id, CITE_87_VALIDITY],
                      f"投标有效期 {actual} 日历天，不足要求的 {required} 日历天"
                      f"（{clause.item_id}）")

    # ---------------------------------------------------------------- 否决扫描（D12 + 隐含联动）
    def check_rejections(self) -> None:
        self._check_over_cap()
        self._check_implied_bond()
        self._check_implied_validity()
        self._check_implied_star()

    def _check_over_cap(self) -> None:
        if not self._active(CHK_RJ_CAP):
            return
        cap = self._price_cap()
        prices = self.bid.prices
        if cap is None or prices is None or prices.total_number is None:
            return
        if prices.total_number > cap + _AMT_EPS:
            clause = self._rejection_clause("最高限价")
            self.emit(CHK_RJ_CAP, "rejection_scan", STATUS_NONCONFORM, "high",
                      [clause.item_id, CITE_87_INVALID, CITE_IMPL_REJECT],
                      f"投标总价 {render_amount(prices.total_number)} 超过最高限价 "
                      f"{render_amount(cap)}，按 {clause.item_id} 投标无效")

    def _check_implied_bond(self) -> None:
        if not self.flags.get("bond") or not self._active(CHK_RJ_BOND):
            return
        clause = self._rejection_clause("保证金")
        if clause is not None:
            self.emit(CHK_RJ_BOND, "rejection_scan", STATUS_NONCONFORM, "high",
                      [clause.item_id, CITE_87_INVALID],
                      f"未按要求提交投标保证金，命中否决条款{clause.item_id}"
                      f"（{clause.text}）")

    def _check_implied_validity(self) -> None:
        if not self.flags.get("validity") or not self._active(CHK_RJ_VALIDITY):
            return
        clause = self._rejection_clause("有效期")
        if clause is not None:
            self.emit(CHK_RJ_VALIDITY, "rejection_scan", STATUS_NONCONFORM, "high",
                      [clause.item_id],
                      f"投标有效期不足，命中否决条款{clause.item_id}（{clause.text}）")

    def _check_implied_star(self) -> None:
        if not self.flags.get("star_rejection") or not self._active(CHK_RJ_STAR):
            return
        clause = self._rejection_clause("★")
        if clause is not None:
            self.emit(CHK_RJ_STAR, "rejection_scan", STATUS_NONCONFORM, "high",
                      [clause.item_id, CITE_IMPL_REJECT],
                      f"★条款不满足或未响应，命中否决条款{clause.item_id}（{clause.text}）")

    # ---------------------------------------------------------------- 价格提示（低于成本嫌疑）
    def check_price_hint(self) -> None:
        if not self._active(CHK_PC_LOW):
            return
        cap = self._price_cap()
        prices = self.bid.prices
        if cap is None or prices is None or prices.total_number is None:
            return
        ratio = float(self._param(CHK_PC_LOW, "ratio", 0.8))
        clause = self._rejection_clause("最高限价")
        basis = [CITE_87_LOW_PRICE] + ([clause.item_id] if clause is not None else [])
        if prices.total_number < ratio * cap - _AMT_EPS:
            self.emit(CHK_PC_LOW, "price_check", STATUS_MANUAL, "low", basis,
                      f"投标总价 {render_amount(prices.total_number)} 低于最高限价的 "
                      f"{ratio:.0%}，存在低于成本报价嫌疑，提请人工复核")


def _star_value(text: str) -> Optional[Tuple[int, str]]:
    """条款/响应文本 → (数值, 单位)；要求恰好一处"数字+单位"（多了少了都放弃，宁缺勿错）。"""
    matches = _STAR_VALUE_RE.findall(text or "")
    if len(matches) != 1:
        return None
    return int(matches[0][0]), matches[0][1]


def _star_violated(clause_text: str, required: int, actual: int) -> bool:
    """方向由条款文本限定词决定：不少于/不低于=下限；不超过/不高于、"X日内完成"=上限。"""
    floor = any(kw in clause_text for kw in ("不少于", "不低于"))
    ceil = any(kw in clause_text for kw in ("不超过", "不高于")) or "日内" in clause_text
    if floor and not ceil:
        return actual < required
    if ceil and not floor:
        return actual > required
    return False
