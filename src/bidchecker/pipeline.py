"""端到端流水线编排（状态机：节点/耗时/失败清单，plan/04 §六）。M3 解析与校核段 + M4 collusion/LLM 兜底。

节点顺序：load → parse_tender → parse_bids → checks → collusion(可选) → aggregate → report(可选)。
单节点失败落失败清单（PipelineResult.failed），不中断其余节点（可解释的降级）：
- 项目缺 tender.md → FileNotFoundError（CLI 退出码 2，输入不可用）；
- 单份文档解析失败 → 记入 failed，其余文档继续；
- collusion 节点（M4）：按对文本特征检出，target=围标对 "bids/A.md|bids/B.md"，
  仅 待人工确认 辅助提示（不出定性结论）；report 节点 M5 交付，记跳过节点；
- LLM 解析兜底（M4，默认关闭）：仅当 llm_fallback 启用且 env 配置齐备时，
  对解析后仍为 None 的"宁缺"槽位做 LLM 抽取（quote ⊂ 原文硬校验 + 数值合法性校验）；
  未启用/不可达 → 整链退化为纯规则通路（bench 基准固定禁用，零 API 依赖）。

target 归因：tender 侧结论 → tender.md；投标侧结论 → bids/<投标人>.md；
围标对 → "bids/A.md|bids/B.md"。findings JSON 含 check_id/rule_type/status/
risk_level/message/basis/evidence/target，无时间戳（落盘内容确定）。
"""

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from bidchecker.collusion import PairFinding, detect_collusion
from bidchecker.knowledge import load_rules
from bidchecker.parsers.bid import parse_bid
from bidchecker.parsers.tender import parse_tender
from bidchecker.rules.engine import run_checks, run_tender_checks
from bidchecker.schema import BidCard, Finding, TenderCard

STAGES = ("load", "parse_tender", "parse_bids", "checks", "collusion", "aggregate", "report")

TENDER_FILE = "tender.md"
_GRAPH_FILE = "collusion_graph.html"
_SKIP_DETAIL = {"report": "docx 报告用 bidchecker report 命令生成"}


@dataclass
class StageReport:
    """节点执行记录：ok/耗时/明细（耗时仅进摘要输出，不进落盘产物）。"""

    name: str
    ok: bool
    seconds: float = 0.0
    detail: str = ""


@dataclass
class BidResult:
    """单份投标的解析与校核产物。"""

    file: str          # 相对项目目录路径："bids/<投标人>.md"
    bidder: Optional[str]
    card: Optional[BidCard]
    findings: List[Finding] = field(default_factory=list)


@dataclass
class PipelineResult:
    """项目目录 → 解析/校核产物 + 节点记录（M3；collusion/LLM 兜底随 M4 补齐）。"""

    project_dir: str
    tender_card: Optional[TenderCard]
    tender_findings: List[Finding] = field(default_factory=list)
    bids: List[BidResult] = field(default_factory=list)
    collusion: List[PairFinding] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    stages: List[StageReport] = field(default_factory=list)

    # ---------------------------------------------------------------- 序列化
    def finding_dicts(self) -> List[Dict[str, Any]]:
        """全部结论 → 序列化 dict 列表（附加 rule_type 与 target，顺序确定）。

        缺知识库时规则映射为空，rule_type 会退化为空串——此时必须告警而非静默
        （DEC3=A：仍可运行 + stderr 一行，退出码语义不变）。
        """
        rules = load_rules()
        rule_type_by_id = {r.get("id"): r.get("rule_type", "")
                           for r in rules if isinstance(r, dict) and r.get("id")}
        if not rule_type_by_id:
            _warn_missing_knowledge()
        out: List[Dict[str, Any]] = []
        for f in self.tender_findings:
            out.append(_finding_dict(f, rule_type_by_id, TENDER_FILE))
        for b in self.bids:
            for f in b.findings:
                out.append(_finding_dict(f, rule_type_by_id, b.file))
        for pf in self.collusion:
            out.append(_finding_dict(pf.finding, rule_type_by_id, pf.target))
        return out

    def summary(self) -> Dict[str, Any]:
        n = {"符合": 0, "不符合": 0, "待人工确认": 0}
        for f in self.tender_findings:
            n[f.status] = n.get(f.status, 0) + 1
        for b in self.bids:
            for f in b.findings:
                n[f.status] = n.get(f.status, 0) + 1
        for pf in self.collusion:
            n[pf.finding.status] = n.get(pf.finding.status, 0) + 1
        return {
            "project_dir": self.project_dir,
            "status_counts": n,
            "total": sum(n.values()),
            "failed": list(self.failed),
        }

    def format_summary(self) -> str:
        s = self.summary()
        lines = [f"项目 {self.project_dir}：结论 {s['total']} 条"
                 f"（不符合 {s['status_counts'].get('不符合', 0)}、"
                 f"待人工确认 {s['status_counts'].get('待人工确认', 0)}）"]
        for d in self.finding_dicts():
            risk = f"({d['risk_level']})" if d.get("risk_level") else ""
            lines.append(f"  [{d['target']}] {d['check_id']} {d['rule_type']} · "
                         f"{d['status']}{risk} {d['message']}")
        if self.failed:
            lines.append(f"解析失败 {len(self.failed)} 份：" + "、".join(self.failed))
        stages = " / ".join(f"{st.name} {st.seconds:.3f}s" + ("" if st.ok else " ✗")
                            for st in self.stages)
        lines.append(f"节点：{stages}")
        return "\n".join(lines)


def _finding_dict(f: Finding, rule_type_by_id: Dict[str, str], target: str) -> Dict[str, Any]:
    d = f.to_dict()
    d["rule_type"] = rule_type_by_id.get(f.check_id, "")
    d["target"] = target
    return d


_WARNED_KB_MISSING = False


def reset_knowledge_warning() -> None:
    """清空"已告警"标记（测试用；进程内只告警一次，避免 summary/serialize 多次刷屏）。"""
    global _WARNED_KB_MISSING
    _WARNED_KB_MISSING = False


def _warn_missing_knowledge() -> None:
    """知识库不可用 → stderr 一行（DEC3=A：不改变退出码，但绝不静默）。"""
    global _WARNED_KB_MISSING
    if _WARNED_KB_MISSING:
        return
    _WARNED_KB_MISSING = True
    from bidchecker.knowledge import knowledge_status

    status = knowledge_status()
    reason = status.get("reason") or (
        f"知识库目录 {status.get('path')} 的 rules.json 解析后为空（无有效 check 规则）")
    print(f"警告：知识库不可用，findings 的 rule_type 将为空（法规依据仍保留）。{reason}",
          file=sys.stderr)


def run_pipeline(project_dir, out_dir: Optional[str] = None,
                 *, llm_fallback: Optional[bool] = None,
                 graph: bool = False) -> PipelineResult:
    """项目目录 → findings + 卡片产物（out_dir 给定时落盘 findings.json 与 cards/）。

    llm_fallback：None=自动（env 配置齐备即启用，默认关闭）；False=强制禁用
    （bench 基准固定走纯规则通路，保证零 API 依赖可重复）。
    graph：True 时在 out_dir 落盘围标图谱 HTML（collusion_graph.html，M5；
    投标 ≥2 份才生成——两两特征需要对照）。
    """
    root = Path(project_dir)
    result = PipelineResult(project_dir=str(root), tender_card=None)
    use_llm = _llm_fallback_enabled(llm_fallback)

    # ---- load
    t0 = time.perf_counter()
    if not root.is_dir():
        raise FileNotFoundError(f"项目目录不存在：{root}")
    tender_path = root / TENDER_FILE
    if not tender_path.is_file():
        raise FileNotFoundError(f"项目目录缺少 {TENDER_FILE}：{root}")
    tender_text = tender_path.read_text(encoding="utf-8")
    bid_paths = sorted((root / "bids").glob("*.md")) if (root / "bids").is_dir() else []
    result.stages.append(StageReport(
        "load", True, time.perf_counter() - t0,
        f"tender 1 份、投标 {len(bid_paths)} 份"
        + ("" if (root / "bids").is_dir() else "（缺 bids/ 目录）")))

    # ---- parse_tender（llm_fallback 启用时对"宁缺"槽位做 LLM 兜底）
    t0 = time.perf_counter()
    try:
        result.tender_card = parse_tender(tender_text)
        ok, detail = True, "解析成功"
    except Exception as exc:  # noqa: BLE001 —— 单节点失败不中断，落失败清单
        ok, detail = False, f"解析失败：{exc}"
        result.failed.append(TENDER_FILE)
    if ok and use_llm:
        detail += _llm_fill_detail(lambda: _fill_tender(result.tender_card, tender_text))
    result.stages.append(StageReport("parse_tender", ok, time.perf_counter() - t0, detail))

    # ---- parse_bids
    t0 = time.perf_counter()
    bid_texts: Dict[str, str] = {}
    llm_applied = llm_dropped = 0
    llm_unreachable = False
    for path in bid_paths:
        rel = f"bids/{path.name}"
        text = path.read_text(encoding="utf-8")
        try:
            card = parse_bid(text)
        except Exception:  # noqa: BLE001
            result.failed.append(rel)
            result.bids.append(BidResult(file=rel, bidder=None, card=None))
            bid_texts[rel] = text
            continue
        result.bids.append(BidResult(file=rel, bidder=card.bidder, card=card))
        if use_llm:
            try:
                report = _fill_bid(card, text)
                llm_applied += len(report.applied)
                llm_dropped += len(report.dropped)
            except Exception:  # noqa: BLE001 —— LLM 不可达不算解析失败
                llm_unreachable = True
        bid_texts[rel] = text
    ok_bids = sum(1 for b in result.bids if b.card is not None)
    parse_fail = [b.file for b in result.bids if b.card is None]
    detail = (f"成功 {ok_bids}/{len(bid_paths)}"
              + (f"，失败：{'、'.join(parse_fail)}" if parse_fail else ""))
    if use_llm and ok_bids:
        detail += (f"；LLM兜底不可达，纯规则通路继续" if llm_unreachable and not llm_applied
                   else f"；LLM兜底 应用{llm_applied}/丢弃{llm_dropped}")
    result.stages.append(StageReport("parse_bids", not parse_fail,
                                     time.perf_counter() - t0, detail))

    # ---- checks（招标侧 + 逐投标侧；门控文本 = 招标/投标原文）
    t0 = time.perf_counter()
    if result.tender_card is not None:
        result.tender_findings = run_tender_checks(result.tender_card, doc_text=tender_text)
        for b in result.bids:
            if b.card is None:
                continue
            b.findings = run_checks(result.tender_card, b.card,
                                    doc_text=tender_text + "\n" + bid_texts[b.file])
    result.stages.append(StageReport(
        "checks", result.tender_card is not None, time.perf_counter() - t0,
        "招标侧 + 投标侧确定性检查" if result.tender_card is not None else "招标卡缺失，检查跳过"))

    # ---- collusion（M4：按对文本特征，仅 待人工确认 辅助提示）
    t0 = time.perf_counter()
    parsed_texts = {b.file: bid_texts[b.file] for b in result.bids if b.card is not None}
    if result.tender_card is None:
        result.stages.append(StageReport("collusion", True, time.perf_counter() - t0,
                                         "招标卡缺失，跳过"))
    elif len(parsed_texts) < 2:
        result.stages.append(StageReport("collusion", True, time.perf_counter() - t0,
                                         "投标不足 2 份，跳过"))
    else:
        result.collusion = detect_collusion(parsed_texts, exclude_text=tender_text)
        detail = (f"围标特征检出 {len(result.collusion)} 对"
                  if result.collusion else "按对核查无异常一致文本特征")
        result.stages.append(StageReport("collusion", True, time.perf_counter() - t0, detail))

    # ---- aggregate / report（M5：docx 报告为独立命令；可选围标图谱 HTML）
    t0 = time.perf_counter()
    result.stages.append(StageReport("aggregate", True, time.perf_counter() - t0,
                                     f"结论 {len(result.finding_dicts())} 条"))
    t0 = time.perf_counter()
    graph_detail = _SKIP_DETAIL["report"]
    if graph and out_dir is not None and len(parsed_texts) >= 2:
        from bidchecker.collusion.graph import write_graph_html

        bidder_stats: Dict[str, Dict[str, int]] = {}
        for b in result.bids:
            if b.card is None or not b.findings:
                continue
            n_nc = sum(1 for f in b.findings if f.status == "不符合")
            n_man = sum(1 for f in b.findings if f.status == "待人工确认")
            if n_nc or n_man:
                bidder_stats[b.file] = {"不符合": n_nc, "待人工确认": n_man}
        title = "围标文本特征图谱"
        if result.tender_card is not None and result.tender_card.project.name:
            title = f"围标文本特征图谱 · {result.tender_card.project.name[:24]}"
        gpath = write_graph_html(parsed_texts, Path(out_dir) / _GRAPH_FILE,
                                 exclude_text=tender_text,
                                 bidder_stats=bidder_stats, title=title)
        graph_detail = f"围标图谱已生成：{gpath.name}"
    elif graph:
        graph_detail = "围标图谱未生成（需 out_dir 且投标 ≥ 2 份）"
    result.stages.append(StageReport("report", True, time.perf_counter() - t0,
                                     graph_detail))

    if out_dir is not None:
        _write_outputs(result, Path(out_dir))
    return result


def _llm_fallback_enabled(llm_fallback: Optional[bool]) -> bool:
    if llm_fallback is False:
        return False
    from bidchecker.llm import client
    return client.is_enabled()


def _llm_fill_detail(fill) -> str:
    """执行一次 LLM 兜底填充并生成阶段明细；任何异常 → 记不可达（纯规则通路继续）。"""
    try:
        report = fill()
    except Exception as exc:  # noqa: BLE001 —— LLM 不可达不中断流水线
        return f"；LLM兜底不可达（{exc.__class__.__name__}），纯规则通路继续"
    return f"；LLM兜底 应用{len(report.applied)}/丢弃{len(report.dropped)}"


def _fill_tender(card: TenderCard, text: str):
    from bidchecker.llm.fallback import fill_missing_slots
    return fill_missing_slots(card, text)


def _fill_bid(card: BidCard, text: str):
    from bidchecker.llm.fallback import fill_missing_slots
    return fill_missing_slots(card, text)


def _write_outputs(result: PipelineResult, out: Path) -> List[str]:
    """落盘产物：findings.json + cards/*.card.json（write_bytes，UTF-8 无 BOM，\n 换行）。"""
    out.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    payload = {
        "schema_version": "1",
        "project_dir": result.project_dir,
        "summary": result.summary(),
        "findings": result.finding_dicts(),
    }
    findings_path = out / "findings.json"
    findings_path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    written.append(str(findings_path))
    cards_dir = out / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    if result.tender_card is not None:
        _write_card(cards_dir / "tender.card.json", result.tender_card)
        written.append(str(cards_dir / "tender.card.json"))
    for b in result.bids:
        if b.card is None:
            continue
        stem = b.card.bidder or Path(b.file).stem
        _write_card(cards_dir / f"{stem}.card.json", b.card)
        written.append(str(cards_dir / f"{stem}.card.json"))
    return written


def _write_card(path: Path, card: Any) -> None:
    path.write_bytes((json.dumps(card.to_dict(), ensure_ascii=False, indent=2) + "\n")
                     .encode("utf-8"))
