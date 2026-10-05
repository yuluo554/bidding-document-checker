"""端到端流水线（M3/M4）：examples 三项目与 ground_truth 全集合对账、降级路径、落盘确定性。

对账口径（M4 升级）：expect_findings + also_expect **全集合（含 D11 围标对）**
vs findings 非符合四元组 (rule_type, status, risk_level, target)；
干净对照 demo-goods-2 零结论（含围标对零误报）。
"""
import json
from pathlib import Path

import pytest

from bidchecker.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


def _truth_tuples(project_dir: Path):
    gt = json.loads((project_dir / "ground_truth.json").read_text(encoding="utf-8"))
    out = set()
    for row in gt["expect_findings"] + gt["also_expect"]:
        out.add((row["rule_type"], row["status"], row["risk_level"], row["target"]))
    return out


def _actual_tuples(project_dir: Path):
    result = run_pipeline(project_dir)
    assert not result.failed
    out = set()
    for d in result.finding_dicts():
        out.add((d["rule_type"], d["status"], d["risk_level"], d["target"]))
    return out, result


@pytest.mark.parametrize("key", ["demo-goods-1", "demo-services-1"])
def test_findings_match_ground_truth_full_set(key):
    actual, _ = _actual_tuples(EXAMPLES / key)
    expected = _truth_tuples(EXAMPLES / key)
    assert actual == expected, f"{key}\n漏报: {expected - actual}\n误报: {actual - expected}"


def test_clean_project_zero_findings():
    actual, result = _actual_tuples(EXAMPLES / "demo-goods-2")
    assert actual == set()
    assert result.summary()["total"] == 0


def test_pipeline_deterministic_and_outputs_stable(tmp_path):
    """两次执行 findings 完全一致；落盘 findings.json 逐字节一致（无时间戳）。"""
    r1 = run_pipeline(EXAMPLES / "demo-goods-1", out_dir=str(tmp_path / "a"))
    r2 = run_pipeline(EXAMPLES / "demo-goods-1", out_dir=str(tmp_path / "b"))
    assert r1.finding_dicts() == r2.finding_dicts()
    fa = (tmp_path / "a" / "findings.json").read_bytes()
    fb = (tmp_path / "b" / "findings.json").read_bytes()
    assert fa == fb
    payload = json.loads(fa.decode("utf-8"))
    assert payload["findings"]
    for d in payload["findings"]:
        assert {"check_id", "rule_type", "status", "risk_level", "message",
                "basis", "evidence", "target"} <= set(d)
    cards = list((tmp_path / "a" / "cards").glob("*.card.json"))
    assert len(cards) == 1 + 4  # tender + 4 份投标


def test_missing_project_and_tender_raise():
    with pytest.raises(FileNotFoundError):
        run_pipeline(ROOT / "no-such-project")
    empty = ROOT / "examples" / "demo-goods-1"  # 有 tender.md；构造无 tender 的临时项目
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        (proj / "bids").mkdir(parents=True)
        shutil.copy(next((empty / "bids").glob("*.md")), proj / "bids" / "x.md")
        with pytest.raises(FileNotFoundError):
            run_pipeline(proj)


def test_degraded_when_bid_parse_fails(tmp_path, monkeypatch):
    """单份投标解析失败 → 落失败清单、其余继续（可解释降级，CLI 退出码 1 的来源）。"""
    import bidchecker.pipeline as pl

    real_parse = pl.parse_bid

    def flaky(text):
        if "启明" in text:
            raise ValueError("模拟解析失败")
        return real_parse(text)

    monkeypatch.setattr(pl, "parse_bid", flaky)
    result = run_pipeline(EXAMPLES / "demo-goods-1")
    assert any("启明" in f for f in result.failed)
    assert result.failed == [b.file for b in result.bids if b.card is None]
    still = result.finding_dicts()
    assert still, "其余投标的结论不应丢失"
    assert not any("启明" in d["target"] for d in still)


def test_summary_contains_targets_and_stages():
    result = run_pipeline(EXAMPLES / "demo-goods-1")
    text = result.format_summary()
    assert "结论" in text and "tender.md" in text and "CHK-DT-02" in text
    stage_names = [s.name for s in result.stages]
    assert stage_names == ["load", "parse_tender", "parse_bids", "checks",
                           "collusion", "aggregate", "report"]
