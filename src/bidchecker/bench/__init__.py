"""内置评测基准（零 API 依赖可重复，plan/04 §七）。

bench parse（M2）：生成器项目 → 双侧文档 + 字段级真值 → 逐字段对账 → P/R/F1。

对账口径（与 datagen/__init__ 解析真值契约对齐）：
- 解析真值 = ``datagen.build_project(...)`` 返回的注入后参数卡（不经 JSON，文档由卡片渲染）；
- **对账字段集 = 体例渲染进文档的字段**（FIELD_SCOPE，即"文档可携带"口径）：
  文档没有落点的字段不参与扣分（如投标侧 project.agency、证明材料证书编号——后者
  真值在 extras 不入卡）；schema 无证据槽位的字段只对值不对证据；
- 列表行按业务键对齐：资格/星号/否决按 item_id（投标侧资格按体例 Q 序）、分项按名称、
  人员按证书编号、业绩按名称；
- Evidence 另按"quote ⊂ 原文"硬校验（不计入 F1，但违例即该文档判 0 并在报告中列出）；
- 门槛：总体 F1 ≥ 0.95（不放宽），--threshold 可上调用于守门演示。

bench e2e（检出率/误报率/判定准确率）按 plan/05 排期 M4 交付。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from bidchecker.datagen import DEMO_PROJECTS, build_project
from bidchecker.datagen.templates import render_bid, render_tender
from bidchecker.parsers.bid import parse_bid
from bidchecker.parsers.tender import parse_tender
from bidchecker.schema import BidCard, TenderCard

DEFAULT_SEEDS: Tuple[int, ...] = (1, 7, 42, 123, 2026)
F1_THRESHOLD = 0.95

_MISSING = object()  # 区分"真值有解析缺"与"值为 None"


# ---------------------------------------------------------------- 字段抽取（对账口径）
def flatten_tender(t: TenderCard) -> Dict[str, object]:
    """TenderCard → {字段路径: 值}，仅含文档有落点的字段（见模块 docstring 口径）。"""
    out: Dict[str, object] = {}
    for name, value in (("project.name", t.project.name), ("project.number", t.project.number),
                        ("project.buyer", t.project.buyer), ("project.agency", t.project.agency)):
        out[name] = value
    for q in t.qualifications:
        for f in ("item_id", "requirement", "category", "level"):
            out[f"qualifications[{q.item_id}].{f}"] = getattr(q, f)
    for c in t.star_clauses:
        for f in ("item_id", "marker", "text"):
            out[f"star_clauses[{c.item_id}].{f}"] = getattr(c, f)
    if t.scoring is not None:
        out["scoring.method"] = t.scoring.method
        out["scoring.price_weight"] = t.scoring.price_weight
        for it in t.scoring.items:
            out[f"scoring.items[{it.name}].name"] = it.name
            out[f"scoring.items[{it.name}].weight"] = it.weight
    if t.bond is not None:
        out["bond.amount"] = t.bond.amount
        out["bond.forms"] = tuple(t.bond.forms)
        out["bond.deadline"] = t.bond.deadline
    for name, value in (("key_dates.issue_start", t.key_dates.issue_start),
                        ("key_dates.submit_deadline", t.key_dates.submit_deadline),
                        ("key_dates.open_time", t.key_dates.open_time),
                        ("key_dates.validity_days", t.key_dates.validity_days)):
        out[name] = value
    for r in t.rejection_clauses:
        for f in ("item_id", "text", "basis"):
            out[f"rejection_clauses[{r.item_id}].{f}"] = getattr(r, f)
    return out


def flatten_bid(b: BidCard) -> Dict[str, object]:
    """BidCard → {字段路径: 值}（投标侧：agency/证书编号等无文档落点字段不入对账）。"""
    out: Dict[str, object] = {}
    for name, value in (("project.name", b.project.name), ("project.number", b.project.number),
                        ("project.buyer", b.project.buyer)):
        out[name] = value
    out["bidder"] = b.bidder
    for q in b.qualifications:
        for f in ("item_id", "requirement", "category", "level", "valid_until"):
            out[f"qualifications[{q.item_id}].{f}"] = getattr(q, f)
    for r in b.star_responses:
        for f in ("star_id", "responded", "location", "quote", "deviation"):
            out[f"star_responses[{r.star_id}].{f}"] = getattr(r, f)
    if b.prices is not None:
        out["prices.total_words"] = b.prices.total_words
        out["prices.total_number"] = b.prices.total_number
        for it in b.prices.items:
            out[f"prices.items[{it.name}].name"] = it.name
            out[f"prices.items[{it.name}].amount"] = it.amount
        out["prices.items_sum"] = b.prices.items_sum
    if b.bond_response is not None:
        out["bond_response.amount"] = b.bond_response.amount
        out["bond_response.forms"] = tuple(b.bond_response.forms)
    out["key_dates.validity_days"] = b.key_dates.validity_days
    for j, p in enumerate(b.personnel):
        key = p.cert_no or f"#row{j}"
        for f in ("name", "cert_name", "cert_no", "valid_until"):
            out[f"personnel[{key}].{f}"] = getattr(p, f)
    for j, pf in enumerate(b.performance):
        key = pf.name or f"#row{j}"
        for f in ("name", "amount", "date", "counterparty"):
            out[f"performance[{key}].{f}"] = getattr(pf, f)
    return out


# ---------------------------------------------------------------- 证据硬校验
def collect_evidence_violations(text: str, card) -> List[str]:
    """Evidence.quote 必须是原文逐字子串（基准硬校验，违例返回路径清单）。"""
    bad: List[str] = []
    ev_items: List[Tuple[str, object]] = []
    if isinstance(card, TenderCard):
        ev_items += [(f"qualifications[{q.item_id}]", q.evidence) for q in card.qualifications]
        ev_items += [(f"star_clauses[{c.item_id}]", c.evidence) for c in card.star_clauses]
        ev_items += [(f"rejection_clauses[{r.item_id}]", r.evidence)
                     for r in card.rejection_clauses]
    else:
        ev_items += [(f"qualifications[{q.item_id}]", q.evidence) for q in card.qualifications]
    for path, ev in ev_items:
        if ev is None:
            bad.append(f"{path}.evidence=<缺失>")
        elif not ev.quote or ev.quote not in text:
            bad.append(f"{path}.evidence.quote={ev.quote!r}")
    return bad


# ---------------------------------------------------------------- 对账与指标
def _prf(tp: int, fp: int, fn: int) -> Tuple[float, float, float]:
    if tp + fp + fn == 0:
        return (1.0, 1.0, 1.0)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return (precision, recall, f1)


def compare_fields(doc_id: str, truth_flat: Dict[str, object],
                   pred_flat: Dict[str, object]) -> "DocResult":
    """逐字段对账：同路径值相等计 tp；缺失计 fn；多抽计 fp；值不符同时计 fp+fn。"""
    tp = fp = fn = 0
    mismatches: List[Tuple[str, str, str]] = []
    for k in sorted(set(truth_flat) | set(pred_flat)):
        tv = truth_flat.get(k, _MISSING)
        pv = pred_flat.get(k, _MISSING)
        if tv is _MISSING:
            fp += 1
            mismatches.append((k, "<真值无此字段>", repr(pv)))
        elif pv is _MISSING:
            fn += 1
            mismatches.append((k, repr(tv), "<未抽出>"))
        elif tv != pv:
            fp += 1
            fn += 1
            mismatches.append((k, repr(tv), repr(pv)))
        else:
            tp += 1
    precision, recall, f1 = _prf(tp, fp, fn)
    return DocResult(doc_id=doc_id, tp=tp, fp=fp, fn=fn, precision=precision,
                     recall=recall, f1=f1, mismatches=mismatches)


@dataclass
class DocResult:
    """单文档对账结果：字段级 tp/fp/fn + 证据违例清单。"""

    doc_id: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float
    mismatches: List[Tuple[str, str, str]] = field(default_factory=list)
    evidence_violations: List[str] = field(default_factory=list)


@dataclass
class ParseBenchReport:
    """bench parse 汇总：总体微平均 + 按字段类别分解 + 门槛判定。"""

    seeds: Tuple[int, ...]
    docs: List[DocResult] = field(default_factory=list)
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    categories: Dict[str, Tuple[int, int, int]] = field(default_factory=dict)
    threshold: float = F1_THRESHOLD

    @property
    def passed(self) -> bool:
        return self.f1 >= self.threshold and not any(d.evidence_violations for d in self.docs)

    def category_lines(self) -> List[str]:
        lines = []
        for cat in sorted(self.categories):
            tp, fp, fn = self.categories[cat]
            p, r, f = _prf(tp, fp, fn)
            lines.append(f"  {cat:<18} P={p:.4f} R={r:.4f} F1={f:.4f} (tp={tp} fp={fp} fn={fn})")
        return lines


def run_parse_bench(seeds: Optional[Sequence[int]] = None,
                    threshold: float = F1_THRESHOLD) -> ParseBenchReport:
    """对全部演示项目 × seeds 构建生成器真值并逐文档对账（构建→渲染→解析→比卡）。

    seeds 缺省 = DEFAULT_SEEDS（1/7/42/123/2026，多 seed 回归不挑 seed）。
    """
    seeds = DEFAULT_SEEDS if seeds is None else tuple(seeds)
    report = ParseBenchReport(seeds=seeds, threshold=threshold)
    cat_agg: Dict[str, List[int]] = {}
    total_tp = total_fp = total_fn = 0
    for seed in seeds:
        for spec in DEMO_PROJECTS:
            bundle = build_project(seed, spec.key, spec.category, spec.clean,
                                   spec.plan, spec.n_bids)
            cases = [("tender.md", render_tender(bundle), bundle.tender)]
            for bb in bundle.bids:
                cases.append((f"bids/{bb.bidder}.md", render_bid(bundle, bb), bb.card))
            for name, text, truth_card in cases:
                doc_id = f"seed{seed}/{spec.key}/{name}"
                if isinstance(truth_card, TenderCard):
                    parsed_card = parse_tender(text)
                    truth_flat, pred_flat = flatten_tender(truth_card), flatten_tender(parsed_card)
                else:
                    parsed_card = parse_bid(text)
                    truth_flat, pred_flat = flatten_bid(truth_card), flatten_bid(parsed_card)
                result = compare_fields(doc_id, truth_flat, pred_flat)
                result.evidence_violations = collect_evidence_violations(text, parsed_card)
                report.docs.append(result)
                total_tp += result.tp
                total_fp += result.fp
                total_fn += result.fn
                for k in truth_flat:
                    cat = k.split("[")[0].split(".")[0]
                    agg = cat_agg.setdefault(cat, [0, 0, 0])
                    if k not in pred_flat:
                        agg[2] += 1  # fn：真值有、解析缺
                    elif truth_flat[k] == pred_flat[k]:
                        agg[0] += 1  # tp
                    else:
                        agg[1] += 1  # 值不符：同时计 fp+fn
                        agg[2] += 1
                for k in pred_flat:
                    if k not in truth_flat:
                        cat = k.split("[")[0].split(".")[0]
                        cat_agg.setdefault(cat, [0, 0, 0])[1] += 1  # 多抽 fp
    report.precision, report.recall, report.f1 = _prf(total_tp, total_fp, total_fn)
    report.categories = {c: tuple(v) for c, v in cat_agg.items()}
    return report


def format_report(report: ParseBenchReport, verbose: bool = False) -> str:
    """人类可读报告（CLI 输出）；verbose 时列出全部字段级失配与证据违例。"""
    lines = [
        f"bench parse（解析层基准）  seeds={','.join(str(s) for s in report.seeds)}  "
        f"文档数={len(report.docs)}",
        f"总体  P={report.precision:.4f} R={report.recall:.4f} F1={report.f1:.4f}  "
        f"[门槛 F1 >= {report.threshold:.2f}]",
    ]
    if report.categories:
        lines.append("按字段类别：")
        lines += report.category_lines()
    bad_docs = [d for d in report.docs if d.mismatches or d.evidence_violations]
    if bad_docs:
        lines.append(f"失配文档 {len(bad_docs)} 个：")
        for d in bad_docs:
            lines.append(f"  {d.doc_id}: tp={d.tp} fp={d.fp} fn={d.fn}")
            for path, expect, actual in d.mismatches:
                lines.append(f"    {path}: 期望 {expect} 实得 {actual}")
            for v in d.evidence_violations:
                lines.append(f"    证据违例 {v}")
    elif report.f1 == 1.0:
        lines.append("全部文档逐字段一致；证据 quote 均为原文子串。")
    verdict = "PASS" if report.passed else "FAIL"
    lines.append(f"结论：{verdict}")
    return "\n".join(lines)


def run_bench_parse(seeds: Sequence[int] = DEFAULT_SEEDS,
                    threshold: float = F1_THRESHOLD,
                    verbose: bool = False) -> Tuple[ParseBenchReport, str]:
    """基准入口（CLI 与测试共用）：返回（报告, 可打印文本）。"""
    report = run_parse_bench(seeds=seeds, threshold=threshold)
    return report, format_report(report, verbose=verbose)


__all__ = [
    "DEFAULT_SEEDS", "F1_THRESHOLD", "DocResult", "ParseBenchReport",
    "flatten_tender", "flatten_bid", "compare_fields", "collect_evidence_violations",
    "run_parse_bench", "run_bench_parse", "format_report",
]
