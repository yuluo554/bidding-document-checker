"""Web 面板（M5 交付，依赖 web extra；fastapi/uvicorn 惰性导入）。

免构建：FastAPI + 零依赖内联单页（vanilla JS + inline CSS），页面 0 外链、
断网可演示；/docs 与 /redoc 显式关闭（Swagger UI 引 CDN）。

纪律：
- 面板复用 pipeline 全链（run_pipeline，**llm_fallback=False 固定禁用**——
  与 bench 同口径，纯规则通路、零 API 依赖、断网可演示）；
- 围标图谱复用 collusion.graph 的数据与内联 JS/CSS（单源，无第二套渲染实现）；
- **0 外链硬纪律**：页面无 script src / link / iframe / @import / src= / href= /
  http(s) 引用；请求只打同源相对路径（/api/check、/api/demo）；
- 上传文件落临时目录跑 pipeline（复用全部已测逻辑），响应不含时间戳。
"""
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping

from bidchecker import __version__
from bidchecker.collusion.graph import GRAPH_CSS, GRAPH_JS, MAX_BIDS, build_graph_data

_DEPENDENCY_HINT = "需要 web extra：pip install bidchecker[web]"

# fastapi 惰性可用性：导入守卫（缺 web extra 时 import 本模块不崩，create_app 报可装提示）。
# 注意端点注解必须能被 pydantic 从模块 globals 解析，故 FastAPI 系在模块层导入，
# uvicorn 仍在 run_server 内惰性导入（无注解解析需求）。
try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError:  # pragma: no cover —— extras 缺失路径由 create_app 报错覆盖
    FastAPI = File = HTTPException = UploadFile = None
    HTMLResponse = JSONResponse = None

_DEMO_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class WebDependencyError(ImportError):
    """web extra 未安装（fastapi/uvicorn/python-multipart 缺失）。"""


def _sanitize_md_name(name: str, used: set) -> str:
    """上传文件名 → bids/ 内安全的 .md 文件名（去路径分隔、防重名，确定性）。"""
    stem = Path((name or "投标文件.md").replace("\\", "/")).name
    stem = stem.strip() or "投标文件"
    if stem.lower().endswith(".md"):
        stem = stem[:-3]
    elif stem.lower().endswith(".txt"):
        stem = stem[:-4]
    stem = stem.replace("\x00", "").strip() or "投标文件"
    candidate, n = stem, 1
    while candidate in used:
        n += 1
        candidate = f"{stem}-{n}"
    used.add(candidate)
    return candidate + ".md"


def analyze_texts(tender_text: str, bid_texts: Mapping[str, str], *,
                  title: str = "围标文本特征图谱") -> Dict[str, Any]:
    """tender/bid 原文 → 全链评审 + 图谱数据（复用 run_pipeline，LLM 固定禁用）。

    bid_texts 键名兼容 "bids/X.md"（findings target 口径）与裸文件名两种形态；
    图谱节点 id 统一为 "bids/X.md"（与结论 target 对齐，溯源联动）。
    """
    from bidchecker.pipeline import run_pipeline

    bare: Dict[str, str] = {}
    for key, text in list(sorted(bid_texts.items()))[:MAX_BIDS]:
        name = key.replace("\\", "/").rsplit("/", 1)[-1]
        if not name.lower().endswith(".md"):
            name += ".md"
        bare[name] = text
    graph_texts = {f"bids/{name}": text for name, text in bare.items()}
    with tempfile.TemporaryDirectory(prefix="bidchecker-web-") as td:
        proj = Path(td) / "proj"
        (proj / "bids").mkdir(parents=True)
        (proj / "tender.md").write_bytes(tender_text.encode("utf-8"))
        for name, text in bare.items():
            (proj / "bids" / name).write_bytes(text.encode("utf-8"))
        result = run_pipeline(proj, llm_fallback=False)
    bidder_stats: Dict[str, Dict[str, int]] = {}
    for b in result.bids:
        n_nc = sum(1 for f in b.findings if f.status == "不符合")
        n_man = sum(1 for f in b.findings if f.status == "待人工确认")
        if n_nc or n_man:
            bidder_stats[b.file] = {"不符合": n_nc, "待人工确认": n_man}
    graph = build_graph_data(graph_texts, exclude_text=tender_text,
                             bidder_stats=bidder_stats, title=title)
    return {
        "version": __version__,
        "summary": result.summary(),
        "findings": result.finding_dicts(),
        "failed": list(result.failed),
        "stages": [{"name": s.name, "ok": s.ok, "detail": s.detail}
                   for s in result.stages],
        "graph": graph,
    }


def create_app():
    """FastAPI 应用（Swagger/ReDoc 显式关闭——其页面引 CDN 外链；缺 extra 报可装提示）。"""
    if FastAPI is None:
        raise WebDependencyError(_DEPENDENCY_HINT)

    app = FastAPI(title="bidchecker Web 面板", version=__version__,
                  docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return INDEX_HTML

    @app.post("/api/check")
    async def check(tender: UploadFile = File(...),
                    bids: List[UploadFile] = File(...)) -> JSONResponse:
        try:
            tender_text = (await tender.read()).decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="招标文件不是 UTF-8 文本")
        if not tender_text.strip():
            raise HTTPException(status_code=400, detail="招标文件内容为空")
        bid_texts: Dict[str, str] = {}
        used: set = set()
        for f in bids:
            try:
                text = (await f.read()).decode("utf-8")
            except UnicodeDecodeError:
                raise HTTPException(status_code=400,
                                    detail=f"投标文件 {f.filename} 不是 UTF-8 文本")
            bid_texts[_sanitize_md_name(f.filename or "", used)] = text
        data = analyze_texts(tender_text, bid_texts,
                             title=_panel_title(tender_text))
        return JSONResponse(data)

    @app.get("/api/demo")
    async def demo(project: str = "demo-goods-1") -> JSONResponse:
        if not _DEMO_NAME_RE.match(project):
            raise HTTPException(status_code=400, detail="项目名不合法")
        root = Path("examples") / project
        tender_path = root / "tender.md"
        if not tender_path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"演示项目不存在：examples/{project}（可在项目根目录启动，"
                       "或用 bidchecker datagen 生成）")
        tender_text = tender_path.read_text(encoding="utf-8")
        bid_texts = {f"bids/{p.name}": p.read_text(encoding="utf-8")
                     for p in sorted((root / "bids").glob("*.md"))}
        data = analyze_texts(tender_text, bid_texts,
                             title=_panel_title(tender_text))
        return JSONResponse(data)

    return app


def _panel_title(tender_text: str) -> str:
    """面板图谱标题：取招标文件首行项目名（截断），兜底通用标题。"""
    for line in (tender_text or "").splitlines():
        if line.startswith("项目名称："):
            name = line.split("：", 1)[1].strip()
            return f"围标文本特征图谱 · {name[:24]}"
    return "围标文本特征图谱"


def run_server(host: str = "127.0.0.1", port: int = 8000) -> int:
    """启动 uvicorn（阻塞直至 Ctrl+C；干净退出返回 0）。"""
    try:
        import uvicorn
    except ImportError as exc:
        raise WebDependencyError(_DEPENDENCY_HINT) from exc
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


# ---------------------------------------------------------------- 内联单页（0 外链）
_PAGE_CSS = """
*{box-sizing:border-box}
body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;margin:0;background:#f2f4f7;color:#223}
.wrap{max-width:1080px;margin:0 auto;padding:18px}
h1{font-size:20px;margin:4px 0 4px}
.ver{font-size:12px;color:#778;font-weight:400;margin-left:8px}
.note{font-size:12px;color:#667;margin-bottom:14px}
.card{background:#fff;border:1px solid #dde;border-radius:8px;padding:14px;margin-bottom:14px}
label{display:inline-block;margin-right:18px;font-size:13px}
button{background:#3b5f8a;color:#fff;border:0;border-radius:5px;padding:6px 16px;font-size:13px;cursor:pointer}
button.alt{background:#71809a}
button:hover{opacity:.92}
#status{font-size:13px;color:#b42318;margin-left:10px}
.chips{margin:8px 0}
.chip{display:inline-block;border-radius:12px;padding:2px 12px;font-size:12px;margin-right:8px;background:#dde4ee}
.chip.bad{background:#fde8e6;color:#b42318;font-weight:600}
.chip.warn{background:#fff3d6;color:#8a6d1a}
table{border-collapse:collapse;width:100%;background:#fff;font-size:12px}
td,th{border:1px solid #e3e6ec;padding:4px 8px;text-align:left;vertical-align:top}
th{background:#eef2f8}
.st-nc{color:#b42318;font-weight:700}
.st-man{color:#8a6d1a;font-weight:600}
.muted{color:#778;font-size:12px}
"""

_PAGE_JS = """
(function () {
  "use strict";
  var STATUS_TEXT = {"不符合": "st-nc", "待人工确认": "st-man"};
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function setStatus(msg) { document.getElementById("status").textContent = msg || ""; }
  function chip(text, cls) {
    return "<span class='chip " + (cls || "") + "'>" + esc(text) + "</span>";
  }
  function render(data) {
    var s = data.summary || {};
    var counts = s.status_counts || {};
    var h = "<div class='card'><div class='chips'>"
      + chip("结论 " + (s.total || 0) + " 条")
      + chip("不符合 " + (counts["不符合"] || 0), counts["不符合"] ? "bad" : "")
      + chip("待人工确认 " + (counts["待人工确认"] || 0), counts["待人工确认"] ? "warn" : "")
      + chip("围标提示 " + ((data.graph && data.graph.problem_count) || 0) + " 对")
      + "<span class='muted'>bidchecker v" + esc(data.version) + "</span></div>";
    if (data.failed && data.failed.length) {
      h += "<div class='muted'>解析失败：" + esc(data.failed.join("、")) + "</div>";
    }
    h += "<table><tr><th>目标</th><th>check_id</th><th>类型</th><th>判定</th><th>风险</th>"
      + "<th>说明</th><th>依据</th></tr>";
    var fs = data.findings || [];
    for (var i = 0; i < fs.length; i++) {
      var f = fs[i];
      h += "<tr><td>" + esc(f.target) + "</td><td>" + esc(f.check_id) + "</td><td>"
        + esc(f.rule_type) + "</td><td class='" + (STATUS_TEXT[f.status] || "") + "'>"
        + esc(f.status) + "</td><td>" + esc(f.risk_level || "—") + "</td><td>"
        + esc(f.message) + "</td><td>" + esc((f.basis || []).join("；")) + "</td></tr>";
    }
    if (!fs.length) { h += "<tr><td colspan='7'>结论 0 条（干净对照或全部复核通过）</td></tr>"; }
    h += "</table>";
    var stages = data.stages || [];
    var sp = [];
    for (var j = 0; j < stages.length; j++) {
      sp.push(esc(stages[j].name) + (stages[j].ok ? "" : "✗"));
    }
    h += "<div class='muted'>节点：" + sp.join(" / ") + "</div></div>";
    h += "<div class='card' id='graph-root'></div>";
    document.getElementById("result").innerHTML = h;
    if (window.initGraph && data.graph) { window.initGraph(document.getElementById("graph-root"), data.graph); }
  }
  function post(fd) {
    setStatus("评审中…");
    fetch("/api/check", { method: "POST", body: fd })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) { setStatus((res.d && (res.d.detail || res.d.error)) || "请求失败"); return; }
        setStatus("");
        render(res.d);
      })
      .catch(function (err) { setStatus("请求失败：" + err); });
  }
  function loadDemo(name) {
    setStatus("加载演示项目…");
    fetch("/api/demo?project=" + encodeURIComponent(name))
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) { setStatus((res.d && (res.d.detail || res.d.error)) || "加载失败"); return; }
        setStatus("");
        render(res.d);
      })
      .catch(function (err) { setStatus("请求失败：" + err); });
  }
  document.getElementById("upload-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var tender = document.getElementById("tender").files[0];
    var bids = document.getElementById("bids").files;
    if (!tender) { setStatus("请选择招标文件 tender.md"); return; }
    if (!bids.length) { setStatus("请选择至少一份投标文件"); return; }
    var fd = new FormData();
    fd.append("tender", tender);
    for (var i = 0; i < bids.length; i++) { fd.append("bids", bids[i]); }
    post(fd);
  });
  var demoBtn = document.getElementById("demo-btn");
  if (demoBtn) { demoBtn.addEventListener("click", function () { loadDemo("demo-goods-1"); }); }
})();
"""

INDEX_HTML = (
    "<!DOCTYPE html>\n"
    '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    "<title>bidchecker Web 面板</title>\n"
    f"<style>{_PAGE_CSS}{GRAPH_CSS}</style>\n</head>\n<body>\n"
    '<div class="wrap">\n'
    "<h1>招投标文件智能评审<span class=\"ver\">bidchecker v"
    f"{__version__} · Web 面板</span></h1>\n"
    '<div class="note">辅助评审定位，非评标决策工具；全部解析与校核在本机离线完成'
    "（LLM 兜底固定禁用）；围标分析仅文本特征、不出定性结论。</div>\n"
    '<div class="card"><form id="upload-form">\n'
    '<label>招标文件 tender.md：<input type="file" id="tender" accept=".md,.txt"></label>\n'
    '<label>投标文件（可多选）：<input type="file" id="bids" accept=".md,.txt" multiple></label>\n'
    '<button type="submit">开始评审</button>\n'
    '<button type="button" class="alt" id="demo-btn">加载内置演示（demo-goods-1）</button>\n'
    '<span id="status"></span>\n'
    "</form></div>\n"
    '<div id="result"><div class="card muted">选择招标与投标文件后点击「开始评审」，'
    "或点击「加载内置演示」。</div></div>\n"
    "</div>\n"
    f"<script>{GRAPH_JS}{_PAGE_JS}</script>\n</body>\n</html>\n"
)

__all__ = ["WebDependencyError", "create_app", "run_server", "analyze_texts",
           "INDEX_HTML"]
