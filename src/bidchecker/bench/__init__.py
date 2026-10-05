"""内置评测基准（零 API 依赖可重复，plan/04 §七）。

bench parse（M2）：生成器项目 → 双侧文档 + 字段级真值 → 逐字段对账 → P/R/F1。

对账口径（与 datagen/__init__ 解析真值契约对齐）：
- 解析真值 = ``datagen.build_project(...)`` 返回的注入后参数卡（不经 JSON，文档由卡片渲染）；
- **对账字段集 = 体例渲染进文档的字段**（FIELD_SCOPE，即"文档可携带"口径）：
  文档没有落点的字段不参与扣分（如投标侧 project.agency、证明材料证书编号——后者
  真值在 extras 不入卡）；schema 无证据槽位的字段只对值不对证据；
- 列表行按业务键对齐：资格/星号/否决按 item_id（投标侧资格按体例 Q 序）、
  分项按名称、人员按证书编号、业绩按名称；
- Evidence 另按"quote ⊂ 原文"硬校验（不计入 F1，但违例即该文档判 0 并在报告中列出）；
- 门槛：总体 F1 ≥ 0.95（不放宽），--threshold 可上调用于守门演示。

bench e2e（M4）：生成器配对集（多 seed × 3 演示项目，含干净对照）→ pipeline 全链
（落盘目录 → run_pipeline，**固定禁用 LLM 兜底**，零 API 依赖）→ findings。
- 对账口径 = datagen 真值契约全集合：expect_findings + also_expect **含 D11（collusion）**
  的四元组 (rule_type, status, risk_level, target) vs findings 非符合四元组集合；
- 指标（plan/04 §七）：检出率（分缺陷类型：该缺陷全部期望四元组被覆盖才算检出）/
  误报数（干净对照 + 非目标文档的全集合差集）/ 判定准确率（四元组微平均 tp/(tp+fp+fn)）；
- 门槛：检出率 ≥ 0.95、误报 0、判定准确率 ≥ 0.95；固定 seed 可重复。
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from bidchecker.datagen import DEMO_PROJECTS, build_project
from bidchecker.datagen.generator import generate_project_package
from bidchecker.datagen.templates import render_bid, render_tender
from bidchecker.parsers.bid import parse_bid
from bidchecker.parsers.tender import parse_tender
from bidchecker.schema import BidCard, TenderCard

DEFAULT_SEEDS: Tuple[int, ...] = (1, 7, 42, 123, 2026)
F1_THRESHOLD = 0.95
E2E_DETECTION_THRESHOLD = 0.95
E2E_ACCURACY_THRESHOLD = 0.95

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


# ================================================================ bench e2e（M4）

TruthTuple = Tuple[str, str, Optional[str], str]


def _load_truth_tuples(gt: Dict) -> Tuple[Set[TruthTuple], Dict[str, Set[TruthTuple]]]:
    """ground_truth.json → （全集合四元组, {defect_id: 该缺陷期望四元组集}）。

    全集合 = expect_findings + also_expect（**含 D11 collusion**，M4 恢复口径）。
    """
    all_tuples: Set[TruthTuple] = set()
    by_defect: Dict[str, Set[TruthTuple]] = {}
    for row in gt["expect_findings"] + gt["also_expect"]:
        t = (row["rule_type"], row["status"], row["risk_level"], row["target"])
        all_tuples.add(t)
        by_defect.setdefault(row["defect_id"], set()).add(t)
    return all_tuples, by_defect


@dataclass
class E2EProjectResult:
    """单项目 e2e 对账：全集合四元组比对 + 缺陷级检出。"""

    seed: int
    project_key: str
    clean: bool
    n_findings: int
    expected: Set[TruthTuple]
    actual: Set[TruthTuple]
    defect_hit: Dict[str, bool] = field(default_factory=dict)

    @property
    def missed(self) -> Set[TruthTuple]:
        return self.expected - self.actual

    @property
    def false_positives(self) -> Set[TruthTuple]:
        return self.actual - self.expected

    @property
    def full_set_equal(self) -> bool:
        return self.expected == self.actual


@dataclass
class E2EBenchReport:
    """bench e2e 汇总：缺陷级检出率 + 误报数 + 判定准确率 + 门槛判定。"""

    seeds: Tuple[int, ...]
    projects: List[E2EProjectResult] = field(default_factory=list)
    detection_by_defect: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    threshold: float = E2E_DETECTION_THRESHOLD

    @property
    def detection_rate(self) -> float:
        hit = sum(h for h, _ in self.detection_by_defect.values())
        total = sum(t for _, t in self.detection_by_defect.values())
        return hit / total if total else 1.0

    @property
    def false_positives(self) -> int:
        return sum(len(p.false_positives) for p in self.projects)

    @property
    def accuracy(self) -> float:
        tp = sum(len(p.expected & p.actual) for p in self.projects)
        fp = sum(len(p.false_positives) for p in self.projects)
        fn = sum(len(p.missed) for p in self.projects)
        return tp / (tp + fp + fn) if tp + fp + fn else 1.0

    @property
    def passed(self) -> bool:
        return (self.detection_rate >= self.threshold
                and self.false_positives == 0
                and self.accuracy >= E2E_ACCURACY_THRESHOLD)


def run_e2e_bench(seeds: Optional[Sequence[int]] = None) -> E2EBenchReport:
    """多 seed × 3 演示项目全链基准：生成落盘 → run_pipeline → 全集合对账。

    LLM 兜底固定禁用（llm_fallback=False）——基准零 API 依赖、纯规则通路可重复；
    真值从落盘 ground_truth.json 读回（不经内存传递，对账口径与 datagen 契约同源）。
    """
    seeds = DEFAULT_SEEDS if seeds is None else tuple(seeds)
    report = E2EBenchReport(seeds=tuple(seeds))
    defect_stat: Dict[str, List[int]] = {}
    with tempfile.TemporaryDirectory(prefix="bidchecker-e2e-") as td:
        root = Path(td)
        for seed in seeds:
            for spec in DEMO_PROJECTS:
                proj_dir = generate_project_package(root / f"seed{seed}", seed, spec)
                result = run_pipeline_quiet(proj_dir)
                gt = json.loads((proj_dir / "ground_truth.json").read_text(encoding="utf-8"))
                expected, by_defect = _load_truth_tuples(gt)
                actual = {(d["rule_type"], d["status"], d["risk_level"], d["target"])
                          for d in result.finding_dicts()}
                hit = {did: tuples <= actual for did, tuples in by_defect.items()}
                for did, ok in hit.items():
                    stat = defect_stat.setdefault(did, [0, 0])
                    stat[0 if ok else 1] += 1  # [0]=检出 [1]=漏检
                report.projects.append(E2EProjectResult(
                    seed=seed, project_key=spec.key, clean=spec.clean,
                    n_findings=len(actual), expected=expected, actual=actual,
                    defect_hit=hit))
    report.detection_by_defect = {d: (v[0], v[0] + v[1])
                                  for d, v in sorted(defect_stat.items())}
    return report


def run_pipeline_quiet(project_dir):
    """e2e 基准专用 pipeline 入口：强制纯规则通路（禁用 LLM 兜底）。"""
    from bidchecker.pipeline import run_pipeline
    return run_pipeline(project_dir, llm_fallback=False)


def format_e2e_report(report: E2EBenchReport) -> str:
    """bench e2e 人类可读报告（CLI 输出）：总体指标 + 分缺陷检出 + 项目对账明细。"""
    lines = [
        f"bench e2e（端到端校核基准）  seeds={','.join(str(s) for s in report.seeds)}  "
        f"项目数={len(report.projects)}",
        f"总体  检出率={report.detection_rate:.4f} [门槛 >= {report.threshold:.2f}]  "
        f"误报={report.false_positives}  判定准确率={report.accuracy:.4f}",
        "分缺陷类型检出（含隐含结论，全部期望四元组被覆盖才算检出）：",
    ]
    for did in sorted(report.detection_by_defect):
        hit, total = report.detection_by_defect[did]
        lines.append(f"  {did:<4} {hit}/{total}  {hit / total:.0%}")
    bad = [p for p in report.projects if not p.full_set_equal]
    lines.append("项目对账：全部项目与 ground_truth 全集合一致（含 D11）"
                 if not bad else f"项目对账：{len(bad)} 个项目不一致：")
    for p in bad:
        lines.append(f"  seed{p.seed}/{p.project_key}（clean={p.clean}）")
        for t in sorted(p.missed):
            lines.append(f"    漏报 {t}")
        for t in sorted(p.false_positives):
            lines.append(f"    误报 {t}")
    verdict = "PASS" if report.passed else "FAIL"
    lines.append(f"结论：{verdict}")
    return "\n".join(lines)


def run_bench_e2e(seeds: Optional[Sequence[int]] = None) -> Tuple[E2EBenchReport, str]:
    """bench e2e 入口（CLI 与测试共用）：返回（报告, 可打印文本）。"""
    report = run_e2e_bench(seeds=seeds)
    return report, format_e2e_report(report)


__all__ = [
    "DEFAULT_SEEDS", "F1_THRESHOLD", "E2E_DETECTION_THRESHOLD", "E2E_ACCURACY_THRESHOLD",
    "DocResult", "ParseBenchReport", "E2EProjectResult", "E2EBenchReport",
    "flatten_tender", "flatten_bid", "compare_fields", "collect_evidence_violations",
    "run_parse_bench", "run_bench_parse", "format_report",
    "run_e2e_bench", "run_bench_e2e", "format_e2e_report",
]
