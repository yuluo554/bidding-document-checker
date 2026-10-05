"""Web 面板（M5）：0 外链单页、/api/demo 与 /api/check 全链对账 pipeline、离线纪律。"""
import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")  # fastapi TestClient 依赖（llm extra 提供）

from fastapi.testclient import TestClient

from bidchecker import __version__
from bidchecker.pipeline import run_pipeline
from bidchecker.webapp import _sanitize_md_name, analyze_texts, create_app

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


# ---------------------------------------------------------------- 单页 0 外链
_FORBIDDEN = ("http://", "https://", "<script src", "<iframe", "<link", "@import",
              "src=", "href=", "url(")


def test_index_page_zero_external_links(client):
    r = client.get("/")
    assert r.status_code == 200
    for token in _FORBIDDEN:
        assert token not in r.text, f"页面含外链痕迹：{token}"
    assert "bidchecker" in r.text and "开始评审" in r.text
    assert __version__ in r.text


def test_index_page_demos_all_projects_offline(client):
    """三个演示项目断网可演示（LLM 兜底固定禁用、无任何外部请求）。"""
    for key in ("demo-goods-1", "demo-goods-2", "demo-services-1"):
        r = client.get(f"/api/demo?project={key}")
        assert r.status_code == 200, key


# ---------------------------------------------------------------- /api/demo 对账 pipeline
def test_demo_endpoint_matches_pipeline(client):
    r = client.get("/api/demo?project=demo-goods-1")
    assert r.status_code == 200
    data = r.json()
    result = run_pipeline(EXAMPLES / "demo-goods-1", llm_fallback=False)
    baseline = result.summary()
    assert data["summary"]["status_counts"] == baseline["status_counts"]
    assert data["summary"]["total"] == baseline["total"]
    assert data["summary"]["failed"] == baseline["failed"]
    assert data["findings"] == result.finding_dicts()
    assert data["graph"]["problem_count"] == 1
    assert len(data["graph"]["nodes"]) == 4
    assert [s["name"] for s in data["stages"]] == [
        "load", "parse_tender", "parse_bids", "checks", "collusion",
        "aggregate", "report"]


def test_demo_clean_project_zero_findings(client):
    r = client.get("/api/demo?project=demo-goods-2")
    assert r.status_code == 200
    assert r.json()["summary"]["total"] == 0


def test_demo_errors(client):
    assert client.get("/api/demo?project=../oops").status_code == 400
    assert client.get("/api/demo?project=no-such-project").status_code == 404


# ---------------------------------------------------------------- /api/check 上传路径
def _files_for(project: str):
    root = EXAMPLES / project
    files = [("tender", ("tender.md", (root / "tender.md").read_bytes()))]
    for name in sorted(os.listdir(root / "bids")):
        files.append(("bids", (name, (root / "bids" / name).read_bytes())))
    return files


def test_upload_endpoint_full_chain(client):
    r = client.post("/api/check", files=_files_for("demo-goods-1"))
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["total"] == 8
    # 上传名保持（中文投标人文件名原样进入图谱节点 id，与结论 target 对齐）
    assert data["graph"]["nodes"][0]["id"].startswith("bids/")
    assert len(data["graph"]["nodes"]) == 4
    assert data["graph"]["problem_count"] == 1


def test_upload_clean_project_zero(client):
    r = client.post("/api/check", files=_files_for("demo-goods-2"))
    assert r.status_code == 200
    assert r.json()["summary"]["total"] == 0


def test_upload_duplicate_names_deduped(client):
    tender = (EXAMPLES / "demo-goods-1" / "tender.md").read_bytes()
    same = "投标人：甲公司（重名测试）".encode("utf-8")
    files = [("tender", ("tender.md", tender)),
             ("bids", ("标书.md", same)), ("bids", ("标书.md", same))]
    r = client.post("/api/check", files=files)
    assert r.status_code == 200
    names = sorted(n["id"] for n in r.json()["graph"]["nodes"])
    assert names == ["bids/标书-2.md", "bids/标书.md"]


def test_upload_rejects_empty_tender(client):
    r = client.post("/api/check", files=[("tender", ("t.md", b"")),
                                         ("bids", ("b.md", b"x"))])
    assert r.status_code == 400


def test_upload_two_bids_no_collusion_output(client):
    """投标 <3 份 → 围标特征不产出（D23），面板图谱 problem_count=0。"""
    root = EXAMPLES / "demo-goods-1"
    files = [("tender", ("tender.md", (root / "tender.md").read_bytes()))]
    for name in sorted(os.listdir(root / "bids"))[:2]:
        files.append(("bids", (name, (root / "bids" / name).read_bytes())))
    r = client.post("/api/check", files=files)
    assert r.status_code == 200
    data = r.json()
    assert len(data["graph"]["nodes"]) == 2
    assert data["graph"]["problem_count"] == 0


def test_analyze_texts_llm_fallback_forced_off(monkeypatch):
    """env 配置齐备时面板仍固定纯规则通路（llm_fallback=False，断网可演示纪律）。"""
    monkeypatch.setenv("BIDCHECKER_LLM_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("BIDCHECKER_LLM_API_KEY", "k")
    monkeypatch.setenv("BIDCHECKER_LLM_MODEL", "m")
    root = EXAMPLES / "demo-goods-1"
    tender = (root / "tender.md").read_text(encoding="utf-8")
    bids = {f"bids/{p.name}": p.read_text(encoding="utf-8")
            for p in sorted((root / "bids").glob("*.md"))}
    data = analyze_texts(tender, bids)
    baseline = run_pipeline(root, llm_fallback=False)
    assert data["summary"]["status_counts"] == baseline.summary()["status_counts"]
    assert data["findings"] == baseline.finding_dicts()


def test_sanitize_md_name():
    assert _sanitize_md_name("../x/../../evil.md", set()) == "evil.md"
    assert _sanitize_md_name("报告.txt", set()) == "报告.md"
    assert _sanitize_md_name("a.md", {"a"}) == "a-2.md"
    assert _sanitize_md_name("", set()) == "投标文件.md"
    assert _sanitize_md_name("dir/name.md", set()) == "name.md"
