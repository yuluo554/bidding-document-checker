"""围标图谱 HTML（P1 加分项，plan/04 §五）。M5 交付：两两全量特征可视化。

口径（HANDOFF-M5）：M4 detect_collusion 已提供按对结论（双信号交叉验证，仅命中对
产出），图谱层做**两两全量特征可视化**——
- 相似度：字符 5-gram shingle + Jaccard 两两矩阵（N ≤ 10 规模足够）；
- 对照独有：共享 shingle / 共享长句先扣除招标文本与其余投标共有的部分（D23 同源
  口径在 shingle 粒度的推广），避免固定体例行污染相似度信号；
- 图谱：自绘 SVG 力导向布局（**布局在 Python 侧确定性计算后烘焙坐标**，JS 只负责
  绘制与交互——零随机零时钟，两次构建逐字节一致）；节点=投标人、边=相似度/
  一致性问题（标注类型与证据数），点击节点/边展开证据文本与行号锚点（可溯源联动）；
- 问题边 = detect_collusion 判定对（同一套双信号，图谱不另设判定口径）；非问题边
  也可点击查看对照独有共享行——**原始特征可视化，不构成任何定性结论**；
- **0 外链硬纪律**：单文件 HTML、内联 CSS/JS、不引任何外部资源（无 http(s) 引用、
  无 script src / link / iframe / @import / src= / href=）；SVG 由 JS 以 innerHTML
  字符串构建（避免 createElementNS 的 SVG 命名空间 URL 落进产物）；
- 确定性：文件序 sorted、证据序 (-长度, 文本)、布局常量固定、JSON 键序稳定。
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from bidchecker.collusion import SENTENCE_MIN_LEN, _compile_ts, detect_collusion

SHINGLE_K = 5          # 字符 5-gram shingle（plan/04 §五）
SHARED_LINE_CAP = 5    # 单对证据展开的共享长句上限（证据面板篇幅）
MAX_BIDS = 12          # 图谱规模上限（plan/04 §五：N ≤ 10 规模足够，留余量）

# ---------------------------------------------------------------- 力导向布局常量（固定，勿调参破坏确定性基线）
_CANVAS_W = 960.0
_CANVAS_H = 600.0
_LAYOUT_ITER = 420
_STEP0 = 14.0
_REPULSION = 26000.0
_ATTRACTION = 26.0
_GRAVITY = 0.012
_MIN_DIST = 30.0
_REST_DIST = 150.0
_FORCE_CAP = 60.0
_NODE_MARGIN = 46.0
_PROBLEM_PULL = 0.3    # 问题边最小引力（围标对视觉聚拢）


@dataclass
class PairSim:
    """两份投标的两两特征：相似度 + 对照独有共享 + 问题标记与证据。"""

    a: str
    b: str
    jaccard: float
    exclusive_shared: int                 # 对照独有共享 shingle 数
    problem: bool = False                 # detect_collusion 双信号命中
    timestamp_equal: bool = False
    shared_lines: List[Dict[str, Any]] = field(default_factory=list)
    # shared_lines 元素：{"text", "len", "a_line", "b_line"}

    @property
    def target(self) -> str:
        return f"{self.a}|{self.b}"

    @property
    def evidence_count(self) -> int:
        return len(self.shared_lines) + (1 if self.timestamp_equal else 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "a": self.a, "b": self.b,
            "jaccard": round(self.jaccard, 4),
            "exclusive_shared": self.exclusive_shared,
            "problem": self.problem,
            "evidence_count": self.evidence_count,
        }


# ---------------------------------------------------------------- 特征计算
def shingle_set(text: str, k: int = SHINGLE_K) -> set:
    """文本 → 字符 k-gram 集合（剔除全部空白字符后切分；确定性）。"""
    compact = "".join((text or "").split())
    if len(compact) < k:
        return set()
    return {compact[i:i + k] for i in range(len(compact) - k + 1)}


def _line_first_occurrence(text: str, line: str) -> Optional[int]:
    """行在原文中的首次出现行号（1 基）；不存在 → None。"""
    for i, ln in enumerate(text.splitlines()):
        if ln == line:
            return i + 1
    return None


def _exclusive_shared_lines(text_a: str, text_b: str, others: Sequence[str],
                            exclude_text: str) -> List[str]:
    """两份投标间"对照独有"的相同行（≥ SENTENCE_MIN_LEN，扣除招标与其余投标）。

    返回按 (-长度, 文本) 排序的行列表（并列确定性）；与 collusion._exclusive_shared_line
    同一口径的**全量版**（图谱需要全部证据，不只取最长一条）。
    """
    common = set(text_a.splitlines()) & set(text_b.splitlines())
    out = []
    for line in common:
        stripped = line.strip()
        if len(stripped) < SENTENCE_MIN_LEN:
            continue
        if any(stripped in other for other in others):
            continue
        if stripped in exclude_text:
            continue
        out.append(stripped)
    return sorted(out, key=lambda s: (-len(s), s))


def _build_similarity(bid_texts: Mapping[str, str], exclude_text: str) -> List[PairSim]:
    """两两特征矩阵（文件序枚举，确定性）。"""
    files = sorted(bid_texts)
    tender_shingles = shingle_set(exclude_text)
    shingles = {f: shingle_set(bid_texts[f]) for f in files}
    others_shingles = {
        f: set().union(*(shingles[g] for g in files if g != f)) if len(files) > 1 else set()
        for f in files
    }
    out: List[PairSim] = []
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            fa, fb = files[i], files[j]
            sa, sb = shingles[fa], shingles[fb]
            union = sa | sb
            jac = (len(sa & sb) / len(union)) if union else 0.0
            exclusive_ab = (sa & sb) - tender_shingles - others_shingles[fa] - others_shingles[fb]
            others = [bid_texts[f] for f in files if f not in (fa, fb)]
            shared = _exclusive_shared_lines(bid_texts[fa], bid_texts[fb], others, exclude_text)
            ts_a, ts_b = _compile_ts(bid_texts[fa]), _compile_ts(bid_texts[fb])
            ts_equal = ts_a is not None and ts_a == ts_b
            lines = [{"text": s, "len": len(s),
                      "a_line": _line_first_occurrence(bid_texts[fa], s),
                      "b_line": _line_first_occurrence(bid_texts[fb], s)}
                     for s in shared[:SHARED_LINE_CAP]]
            out.append(PairSim(a=fa, b=fb, jaccard=jac,
                               exclusive_shared=len(exclusive_ab),
                               timestamp_equal=ts_equal, shared_lines=lines))
    # 问题边标记：与 detect_collusion 同一套双信号判定（图谱不另设口径）
    problems = {pf.target for pf in detect_collusion(bid_texts, exclude_text=exclude_text)}
    for ps in out:
        ps.problem = ps.target in problems
    return out


# ---------------------------------------------------------------- 力导向布局（确定性）
def _layout(n: int, edge_weights: Dict[Tuple[int, int], float]) -> List[List[float]]:
    """确定性力导向布局：圆环初始化 + 固定迭代（零随机零时钟）。

    返回 n×2 坐标（保留 1 位小数）。同输入恒同输出（DetRng 纪律同源）。
    """
    cx, cy = _CANVAS_W / 2.0, _CANVAS_H / 2.0
    radius = min(_CANVAS_W, _CANVAS_H) * 0.34
    pos = [[cx + radius * math.cos(2.0 * math.pi * i / max(n, 1)),
            cy + radius * math.sin(2.0 * math.pi * i / max(n, 1))] for i in range(n)]
    for it in range(_LAYOUT_ITER):
        step = _STEP0 * (1.0 - it / _LAYOUT_ITER) + 0.4
        fx = [0.0] * n
        fy = [0.0] * n
        for i in range(n):
            for j in range(i + 1, n):
                dx = pos[i][0] - pos[j][0]
                dy = pos[i][1] - pos[j][1]
                d = max(math.hypot(dx, dy), _MIN_DIST)
                ux, uy = dx / d, dy / d
                rep = _REPULSION / (d * d)
                fx[i] += rep * ux
                fy[i] += rep * uy
                fx[j] -= rep * ux
                fy[j] -= rep * uy
                wgt = edge_weights.get((i, j), 0.0)
                if wgt > 0.0:
                    att = _ATTRACTION * wgt * (d - _REST_DIST) / _REST_DIST
                    fx[i] -= att * ux
                    fy[i] -= att * uy
                    fx[j] += att * ux
                    fy[j] += att * uy
            fx[i] += (cx - pos[i][0]) * _GRAVITY
            fy[i] += (cy - pos[i][1]) * _GRAVITY
        for i in range(n):
            mag = math.hypot(fx[i], fy[i])
            if mag > 1e-9:
                move = min(mag, _FORCE_CAP) * step / mag
                pos[i][0] = min(max(pos[i][0] + fx[i] * move, _NODE_MARGIN),
                                _CANVAS_W - _NODE_MARGIN)
                pos[i][1] = min(max(pos[i][1] + fy[i] * move, _NODE_MARGIN),
                                _CANVAS_H - _NODE_MARGIN)
    return [[round(p[0], 1), round(p[1], 1)] for p in pos]


# ---------------------------------------------------------------- 图谱数据组装
def build_graph_data(bid_texts: Mapping[str, str], *, exclude_text: str = "",
                     bidder_stats: Optional[Mapping[str, Mapping[str, Any]]] = None,
                     title: str = "围标文本特征图谱") -> Dict[str, Any]:
    """投标文本表 → 图谱数据（节点/边/证据/矩阵，供 HTML 与 Web 面板共用）。

    bidder_stats（可选）：{相对路径: 摘要 dict}，节点点击面板展示（如结论计数）。
    """
    files = sorted(bid_texts)[:MAX_BIDS]
    texts = {f: bid_texts[f] for f in files}
    sims = _build_similarity(texts, exclude_text) if len(files) >= 2 else []
    weights = {(files.index(ps.a), files.index(ps.b)):
               max(ps.jaccard, _PROBLEM_PULL if ps.problem else 0.0) for ps in sims}
    coords = _layout(len(files), weights)
    nodes = []
    for i, f in enumerate(files):
        stem = f.rsplit("/", 1)[-1][:-3] if f.endswith(".md") else f
        node: Dict[str, Any] = {
            "id": f, "label": stem,
            "chars": len(texts[f]),
            "shingles": len(shingle_set(texts[f])),
            "x": coords[i][0], "y": coords[i][1],
        }
        if bidder_stats and f in bidder_stats:
            node["stats"] = dict(bidder_stats[f])
        nodes.append(node)
    evidence: Dict[str, Any] = {}
    edges = []
    for ps in sims:
        edges.append(ps.to_dict())
        evidence[ps.target] = {
            "a": ps.a, "b": ps.b,
            "jaccard": round(ps.jaccard, 4),
            "exclusive_shared": ps.exclusive_shared,
            "problem": ps.problem,
            "timestamp_equal": ps.timestamp_equal,
            "shared_lines": ps.shared_lines,
        }
    return {
        "schema_version": "1",
        "title": title,
        "k": SHINGLE_K,
        "min_sentence": SENTENCE_MIN_LEN,
        "canvas": {"w": int(_CANVAS_W), "h": int(_CANVAS_H)},
        "nodes": nodes,
        "edges": edges,
        "evidence": evidence,
        "problem_count": sum(1 for e in edges if e["problem"]),
    }


# ---------------------------------------------------------------- 内联资产（单文件 HTML / Web 面板共用）
GRAPH_CSS = """
body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;margin:0;background:#f5f6f8;color:#222}
.g-wrap{max-width:1020px;margin:0 auto;padding:16px}
.g-title{font-size:18px;font-weight:700;margin:6px 0 2px}
.g-sub{font-size:12px;color:#667;margin-bottom:10px}
.g-legend{font-size:12px;color:#445;margin:8px 0}
.g-legend .chip{display:inline-block;width:22px;height:4px;border-radius:2px;vertical-align:middle;margin:0 4px 2px 12px}
.g-svgbox{background:#fff;border:1px solid #dde;border-radius:8px}
.g-panel{background:#fff;border:1px solid #dde;border-radius:8px;margin-top:10px;padding:10px 14px;min-height:52px;font-size:13px;line-height:1.7}
.g-panel h4{margin:2px 0 6px;font-size:14px}
.g-panel .bad{color:#b42318;font-weight:600}
.g-panel .muted{color:#667}
.g-panel .anchor{color:#345;background:#eef2f7;border-radius:3px;padding:0 4px}
.g-matrix{margin-top:12px;background:#fff;border:1px solid #dde;border-radius:8px;padding:10px 14px;font-size:12px}
.g-matrix table{border-collapse:collapse}
.g-matrix td,.g-matrix th{border:1px solid #e3e6ec;padding:3px 8px;text-align:center}
.g-matrix th{background:#f0f3f8;font-weight:600}
.g-matrix .prob{background:#fde8e6;color:#b42318;font-weight:700}
.g-matrix .self{background:#f6f7f9}
.g-foot{font-size:12px;color:#667;margin-top:10px}
"""

GRAPH_JS = """
(function () {
  "use strict";
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function pct(x) { return (x * 100).toFixed(1) + "%"; }
  function pairTitle(id) {
    return id.replace(/bids\\//g, "").replace(/\\.md/g, "").replace(/\\|/g, " ↔ ");
  }
  function renderPanelPair(panel, ev) {
    var h = "<h4>" + esc(pairTitle(ev.a + "|" + ev.b)) + "</h4>";
    h += "<div>相似度（字符 " + ev.k + "-gram Jaccard，全量）：<b>" + pct(ev.jaccard)
      + "</b>；对照独有共享 shingle：" + ev.exclusive_shared + "</div>";
    if (ev.problem) {
      h += "<div class='bad'>双信号交叉验证命中：异常一致文本特征提示（待人工确认，非定性结论）</div>";
    } else {
      h += "<div class='muted'>未构成异常一致提示（仅原始特征展示，不构成任何结论）</div>";
    }
    if (ev.timestamp_equal) {
      h += "<div>信号① 同分钟编制时间戳：两份投标「编制完成时间」取值相同</div>";
    }
    if (ev.shared_lines && ev.shared_lines.length) {
      h += "<div>信号② 对照独有共享长句（≥" + ev.min_sentence + " 字，扣除招标文本与其余投标共有）："
        + ev.shared_lines.length + " 条</div>";
      for (var i = 0; i < ev.shared_lines.length; i++) {
        var ln = ev.shared_lines[i];
        h += "<div class='anchor'>A 第 " + ln.a_line + " 行 / B 第 " + ln.b_line + " 行</div>"
          + "<div>「" + esc(ln.text) + "」（" + ln.len + " 字）</div>";
      }
    } else if (!ev.timestamp_equal) {
      h += "<div class='muted'>无对照独有共享长句、编制时间戳不同</div>";
    }
    panel.innerHTML = h;
  }
  function renderPanelNode(panel, node, data) {
    var h = "<h4>" + esc(node.label) + "</h4>";
    h += "<div class='muted'>" + esc(node.id) + "</div>";
    h += "<div>字符数 " + node.chars + "；" + node.k + "-gram shingle " + node.shingles + " 个</div>";
    if (node.stats) {
      var st = node.stats, parts = [];
      for (var key in st) { if (st.hasOwnProperty(key)) { parts.push(esc(key) + " " + esc(st[key])); } }
      if (parts.length) { h += "<div>本侧结论：" + parts.join("；") + "</div>"; }
    }
    var sims = [];
    for (var i = 0; i < data.edges.length; i++) {
      var e = data.edges[i];
      if (e.a === node.id) { sims.push([e.b, e]); } else if (e.b === node.id) { sims.push([e.a, e]); }
    }
    sims.sort(function (x, y) { return y[1].jaccard - x[1].jaccard; });
    if (sims.length) {
      h += "<div>与其他投标相似度：</div>";
      for (var j = 0; j < sims.length; j++) {
        h += "<div>· " + esc(pairTitle(sims[j][0].replace(/^.*bids\\//, "bids/").replace(/\\.md$/, "")))
          + "：" + pct(sims[j][1].jaccard)
          + (sims[j][1].problem ? "（<span class='bad'>异常一致提示</span>）" : "") + "</div>";
      }
    }
    panel.innerHTML = h;
  }
  window.initGraph = function (root, data) {
    var W = data.canvas.w, H = data.canvas.h;
    var byId = {};
    for (var i = 0; i < data.nodes.length; i++) { byId[data.nodes[i].id] = data.nodes[i]; }
    var svg = [];
    svg.push("<svg viewBox='0 0 " + W + " " + H + "' style='width:100%;height:auto;display:block'>");
    for (var e = 0; e < data.edges.length; e++) {
      var ed = data.edges[e], na = byId[ed.a], nb = byId[ed.b];
      var cls = ed.problem ? "prob" : "sim";
      var width = (0.8 + ed.jaccard * 9).toFixed(2);
      var color = ed.problem ? "#b42318" : "#9db3cc";
      svg.push("<line x1='" + na.x + "' y1='" + na.y + "' x2='" + nb.x + "' y2='" + nb.y
        + "' stroke='" + color + "' stroke-width='" + width + "'"
        + (ed.problem ? " stroke-dasharray='7 4'" : "") + " opacity='0.85'/>");
      svg.push("<line x1='" + na.x + "' y1='" + na.y + "' x2='" + nb.x + "' y2='" + nb.y
        + "' stroke='rgba(0,0,0,0)' stroke-width='14' data-edge='" + e + "' style='cursor:pointer'/>");
    }
    for (var n = 0; n < data.nodes.length; n++) {
      var no = data.nodes[n];
      var inProblem = false;
      for (var e2 = 0; e2 < data.edges.length; e2++) {
        if (data.edges[e2].problem && (data.edges[e2].a === no.id || data.edges[e2].b === no.id)) { inProblem = true; break; }
      }
      var fill = inProblem ? "#b42318" : "#3b5f8a";
      svg.push("<g data-node='" + n + "' style='cursor:pointer'>");
      svg.push("<circle cx='" + no.x + "' cy='" + no.y + "' r='17' fill='" + fill + "'/>");
      svg.push("<text x='" + no.x + "' y='" + (no.y + 34) + "' text-anchor='middle' font-size='13' fill='#223'>"
        + esc(no.label) + "</text>");
      svg.push("</g>");
    }
    svg.push("</svg>");
    var legend = "<div class='g-legend'>节点=投标人（红=涉及异常一致提示）；"
      + "<span class='chip' style='background:#9db3cc'></span>相似度边（线宽∝Jaccard）；"
      + "<span class='chip' style='background:#b42318'></span>异常一致提示边（双信号命中，虚线）"
      + "；点击节点/边展开证据与行号锚点</div>";
    var matrix = "<div class='g-matrix'><b>两两相似度矩阵（字符 " + data.k + "-gram Jaccard，%）</b><table>";
    matrix += "<tr><th></th>";
    for (var c = 0; c < data.nodes.length; c++) { matrix += "<th>" + esc(data.nodes[c].label) + "</th>"; }
    matrix += "</tr>";
    for (var r = 0; r < data.nodes.length; r++) {
      matrix += "<tr><th>" + esc(data.nodes[r].label) + "</th>";
      for (var c2 = 0; c2 < data.nodes.length; c2++) {
        if (r === c2) { matrix += "<td class='self'>—</td>"; continue; }
        var e3 = null;
        for (var k = 0; k < data.edges.length; k++) {
          var ee = data.edges[k];
          if ((ee.a === data.nodes[r].id && ee.b === data.nodes[c2].id)
            || (ee.b === data.nodes[r].id && ee.a === data.nodes[c2].id)) { e3 = ee; break; }
        }
        if (e3 === null) { matrix += "<td>·</td>"; }
        else { matrix += "<td" + (e3.problem ? " class='prob'" : "") + ">" + (e3.jaccard * 100).toFixed(1) + "</td>"; }
      }
      matrix += "</tr>";
    }
    matrix += "</table></div>";
    root.innerHTML = "<div class='g-title'>" + esc(data.title) + "</div>"
      + "<div class='g-sub'>异常一致提示 " + data.problem_count
      + " 对；仅文本特征（同分钟编制时间戳 + 对照独有共享长句，双信号交叉验证），非定性结论</div>"
      + legend + "<div class='g-svgbox'>" + svg.join("") + "</div>"
      + "<div class='g-panel'>点击图中节点或连线查看证据与行号锚点。</div>" + matrix
      + "<div class='g-foot'>围标分析仅文本特征辅助提示，不出「围标」定性结论（依据《招标投标法实施条例》第三十九条/第四十条）。</div>";
    var panel = root.querySelector(".g-panel");
    root.addEventListener("click", function (evt) {
      var t = evt.target;
      var edgeEl = t.getAttribute && t.getAttribute("data-edge");
      if (edgeEl !== null && edgeEl !== undefined && edgeEl !== "") {
        var ed = data.edges[parseInt(edgeEl, 10)];
        var ev = data.evidence[ed.a + "|" + ed.b];
        if (ev) { renderPanelPair(panel, ev); }
        return;
      }
      var nodeEl = t.parentNode && t.parentNode.getAttribute && t.parentNode.getAttribute("data-node");
      if (nodeEl !== null && nodeEl !== undefined && nodeEl !== "") {
        renderPanelNode(panel, data.nodes[parseInt(nodeEl, 10)], data);
      }
    });
  };
})();
"""


def _embed_json(data: Dict[str, Any]) -> str:
    """图谱数据 → 可内嵌 <script> 的 JSON（防 </script> 提前闭合；ensure_ascii=False）。"""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"),
                      sort_keys=False).replace("</", "<\\/")


def build_graph_html(bid_texts: Mapping[str, str], *, exclude_text: str = "",
                     bidder_stats: Optional[Mapping[str, Mapping[str, Any]]] = None,
                     title: str = "围标文本特征图谱") -> str:
    """投标文本表 → 单文件图谱 HTML（0 外链、确定性，两次构建逐字节一致）。"""
    data = build_graph_data(bid_texts, exclude_text=exclude_text,
                            bidder_stats=bidder_stats, title=title)
    if len(bid_texts) < 2:
        data["note"] = "投标不足 2 份，无两两特征可展示"
    bootstrap = ("var gd=JSON.parse(document.getElementById('graph-data').textContent);"
                 "initGraph(document.getElementById('graph-root'),gd);")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{title}</title>\n"
        f"<style>{GRAPH_CSS}</style>\n</head>\n<body>\n"
        '<div class="g-wrap" id="graph-root"></div>\n'
        '<script type="application/json" id="graph-data">' + _embed_json(data) + "</script>\n"
        "<script>" + GRAPH_JS + bootstrap + "</script>\n</body>\n</html>\n"
    )


def write_graph_html(bid_texts: Mapping[str, str], out_path, *, exclude_text: str = "",
                     bidder_stats: Optional[Mapping[str, Mapping[str, Any]]] = None,
                     title: str = "围标文本特征图谱") -> Path:
    """图谱 HTML 落盘（write_bytes，UTF-8 无 BOM，\\n 换行；产物无时间戳）。"""
    html = build_graph_html(bid_texts, exclude_text=exclude_text,
                            bidder_stats=bidder_stats, title=title)
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(html.encode("utf-8"))
    return path


__all__ = ["SHINGLE_K", "MAX_BIDS", "PairSim", "shingle_set", "build_graph_data",
           "build_graph_html", "write_graph_html", "GRAPH_CSS", "GRAPH_JS"]
