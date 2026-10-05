"""围标图谱 HTML（M5）：5-gram shingle + Jaccard 两两矩阵、确定性力导向布局、
0 外链硬断言、证据溯源展开、问题边与 detect_collusion 同口径。"""
import json
from pathlib import Path

import pytest

from bidchecker.collusion import detect_collusion
from bidchecker.collusion.graph import (SHINGLE_K, build_graph_data, build_graph_html,
                                        shingle_set, write_graph_html)

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def _load(project: str):
    root = EXAMPLES / project
    tender = (root / "tender.md").read_text(encoding="utf-8")
    bids = {f"bids/{p.name}": p.read_text(encoding="utf-8")
            for p in sorted((root / "bids").glob("*.md"))}
    return tender, bids


def test_shingle_set_basics():
    assert shingle_set("") == set()
    assert shingle_set("abcd") == set()          # 短于 k
    assert shingle_set("abcde") == {"abcde"}
    assert shingle_set("abcdefg") == {"abcde", "bcdef", "cdefg"}
    # 空白字符不参与 shingle（正文换行/空格不影响相似度）
    assert shingle_set("abcde fghij") == shingle_set("abcdefghij")


def test_jaccard_identical_and_disjoint():
    tender, _ = _load("demo-goods-1")
    a = "完全不同的内容甲" * 60
    b = "另一种截然不同的文本乙" * 60
    data = build_graph_data({"bids/a.md": a, "bids/b.md": b}, exclude_text=tender)
    assert data["edges"][0]["jaccard"] == 0.0
    data2 = build_graph_data({"bids/a.md": a, "bids/b.md": a}, exclude_text=tender)
    assert data2["edges"][0]["jaccard"] == 1.0
    assert data2["nodes"][0]["id"] != data2["nodes"][1]["id"]


def test_matrix_structure_and_problem_edges_match_detect_collusion():
    tender, bids = _load("demo-goods-1")
    data = build_graph_data(bids, exclude_text=tender)
    assert data["schema_version"] == "1"
    assert len(data["nodes"]) == 4
    assert len(data["edges"]) == 4 * 3 // 2
    problems = {e["a"] + "|" + e["b"] for e in data["edges"] if e["problem"]}
    expected = {pf.target for pf in detect_collusion(bids, exclude_text=tender)}
    assert problems == expected == {"bids/启明智能化工程有限公司.md|bids/安捷计算机系统有限公司.md"}
    # 问题边证据：双信号齐备（同分钟时间戳 + 对照独有共享长句，带行号锚点）
    ev = data["evidence"]["bids/启明智能化工程有限公司.md|bids/安捷计算机系统有限公司.md"]
    assert ev["problem"] is True and ev["timestamp_equal"] is True
    assert ev["shared_lines"], "问题边必须带共享长句证据"
    for line in ev["shared_lines"]:
        assert line["a_line"] >= 1 and line["b_line"] >= 1
        assert line["len"] >= data["min_sentence"]
        assert line["text"] in bids[ev["a"]] and line["text"] in bids[ev["b"]]


def test_two_bids_no_problem_output():
    """投标 <3 份无法建立独有性对照 → 问题边不产出（D23 口径，图谱同样遵守）。"""
    tender, bids = _load("demo-goods-1")
    pair_keys = sorted(k for k in bids
                       if k in ("bids/启明智能化工程有限公司.md",
                                "bids/安捷计算机系统有限公司.md"))
    data = build_graph_data({k: bids[k] for k in pair_keys}, exclude_text=tender)
    assert len(data["edges"]) == 1
    assert data["edges"][0]["problem"] is False
    assert data["problem_count"] == 0
    # 原始特征仍可视化（timestamp/共享行照常给出，供人工参考）
    assert data["edges"][0]["evidence_count"] >= 1


def test_clean_project_zero_problem_edges():
    tender, bids = _load("demo-goods-2")
    data = build_graph_data(bids, exclude_text=tender)
    assert data["problem_count"] == 0
    assert all(not e["problem"] for e in data["edges"])


def test_graph_data_deterministic():
    tender, bids = _load("demo-goods-1")
    a = build_graph_data(bids, exclude_text=tender)
    b = build_graph_data(bids, exclude_text=tender)
    assert json.dumps(a, ensure_ascii=False) == json.dumps(b, ensure_ascii=False)


def test_layout_deterministic_and_in_canvas():
    tender, bids = _load("demo-goods-1")
    a = build_graph_data(bids, exclude_text=tender)
    b = build_graph_data(bids, exclude_text=tender)
    w, h = a["canvas"]["w"], a["canvas"]["h"]
    for n1, n2 in zip(a["nodes"], b["nodes"]):
        assert (n1["x"], n1["y"]) == (n2["x"], n2["y"])
        assert 0 < n1["x"] < w and 0 < n1["y"] < h
    # 节点位置互不重叠（布局有效性）
    coords = {(n["x"], n["y"]) for n in a["nodes"]}
    assert len(coords) == len(a["nodes"])


def test_node_stats_passthrough():
    tender, bids = _load("demo-goods-1")
    stats = {"bids/启明智能化工程有限公司.md": {"不符合": 2, "待人工确认": 1}}
    data = build_graph_data(bids, exclude_text=tender, bidder_stats=stats)
    node = next(n for n in data["nodes"] if n["id"] == "bids/启明智能化工程有限公司.md")
    assert node["stats"] == {"不符合": 2, "待人工确认": 1}


# ---------------------------------------------------------------- 0 外链硬断言
_FORBIDDEN = ("http://", "https://", "<script src", "<iframe", "<link", "@import",
              "src=", "href=", "url(")


def test_html_zero_external_links():
    tender, bids = _load("demo-goods-1")
    html = build_graph_html(bids, exclude_text=tender)
    for token in _FORBIDDEN:
        assert token not in html, f"图谱 HTML 含外链痕迹：{token}"
    assert "<svg" in html and "graph-data" in html


def test_html_deterministic():
    tender, bids = _load("demo-goods-1")
    assert build_graph_html(bids, exclude_text=tender) == \
        build_graph_html(bids, exclude_text=tender)


def test_html_data_embedded_without_script_breakout():
    text = "编制完成时间：2026-01-01 00:00\n</script>alert(1)"
    html = build_graph_html({"bids/x.md": text, "bids/y.md": text},
                            exclude_text="招标文本")
    payload = html.split('id="graph-data">')[1].split("</script>")[0]
    data = json.loads(payload.replace("<\\/", "</"))
    assert data["nodes"][0]["chars"] == len(text)


def test_write_graph_html(tmp_path):
    tender, bids = _load("demo-goods-1")
    out = tmp_path / "nested" / "collusion_graph.html"
    path = write_graph_html(bids, out, exclude_text=tender)
    assert path == out and out.is_file()
    assert out.read_text(encoding="utf-8") == build_graph_html(bids, exclude_text=tender)
    # 落盘内容确定性（无时间戳）：再写一次逐字节一致
    write_graph_html(bids, out, exclude_text=tender)
    assert out.read_bytes() == out.read_bytes()


def test_single_bid_renders_empty_graph():
    tender, bids = _load("demo-goods-1")
    one = next(iter(bids.items()))
    data = build_graph_data(dict([one]), exclude_text=tender)
    assert data["nodes"] and not data["edges"] and data["problem_count"] == 0
    html = build_graph_html(dict([one]), exclude_text=tender)
    for token in _FORBIDDEN:
        assert token not in html
