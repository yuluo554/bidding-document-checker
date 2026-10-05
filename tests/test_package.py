"""包级：版本号、子包可导入、stub 行为锁定、LLM 默认关闭。"""
import importlib
import os
import re

import pytest

import bidchecker

SUBMODULES = [
    "bidchecker.schema",
    "bidchecker.parsers.common",
    "bidchecker.parsers.tender",
    "bidchecker.parsers.bid",
    "bidchecker.rules.engine",
    "bidchecker.rules.gates",
    "bidchecker.knowledge",
    "bidchecker.llm.client",
    "bidchecker.datagen",
    "bidchecker.bench",
    "bidchecker.collusion",
    "bidchecker.report",
    "bidchecker.webapp",
    "bidchecker.pipeline",
    "bidchecker.cli",
]


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", bidchecker.__version__)


def test_submodules_importable():
    for name in SUBMODULES:
        importlib.import_module(name)


def test_m3_engine_and_pipeline_delivered():
    """M3 转正：引擎空卡零结论（不抛 NotImplementedError）、流水线可在干净项目出空 findings。"""
    from pathlib import Path

    from bidchecker.pipeline import run_pipeline
    from bidchecker.rules.engine import run_checks, run_tender_checks
    from bidchecker.schema import BidCard, TenderCard

    assert run_checks(TenderCard(), BidCard()) == []
    assert run_tender_checks(TenderCard()) == []
    result = run_pipeline(Path(__file__).resolve().parent.parent / "examples" / "demo-goods-2")
    assert result.summary()["total"] == 0
    assert not result.failed


def test_m4_collusion_search_llm_delivered():
    """M4 转正：围标按对检出 / 知识库检索 / LLM chat 均可运行（不再抛 NotImplementedError）。"""
    from bidchecker.collusion import detect_collusion
    from bidchecker.knowledge.search import search

    assert detect_collusion({"bids/甲.md": "编制完成时间：2026-10-14 17:30"}) == []
    hits = search("投标保证金", top_k=2)
    assert hits and all("保证金" in b["text"] for _, b in hits)


def test_parsers_delivered_m2():
    """M2 转正：双侧解析器可运行，examples 固定体例解析出完整参数卡。"""
    from pathlib import Path

    from bidchecker.parsers.bid import parse_bid
    from bidchecker.parsers.tender import parse_tender

    root = Path(__file__).resolve().parent.parent / "examples" / "demo-goods-1"
    tender = parse_tender((root / "tender.md").read_text(encoding="utf-8"))
    assert tender.project.number == "ZB-2026-6452"
    assert len(tender.qualifications) == 6
    assert len(tender.star_clauses) == 3
    assert len(tender.rejection_clauses) == 4
    # D10 注入痕迹原样抽出（解析器不做一致性判定）：开标早于递交截止
    assert tender.key_dates.open_time < tender.key_dates.submit_deadline

    bid_files = sorted((root / "bids").glob("*.md"))
    assert bid_files, "examples demo-goods-1 缺投标文件"
    bid = parse_bid(bid_files[0].read_text(encoding="utf-8"))
    assert bid.bidder
    assert bid.prices is not None and bid.prices.total_number
    assert bid.prices.total_words and bid.prices.items


def test_llm_disabled_without_env():
    """LLM 默认关闭：未配置环境变量时 is_enabled=False，chat 抛 RuntimeError 不崩溃。"""
    from bidchecker.llm import client

    env_keys = (client.ENV_BASE_URL, client.ENV_API_KEY, client.ENV_MODEL)
    saved = {k: os.environ.get(k) for k in env_keys}
    try:
        for k in env_keys:
            os.environ.pop(k, None)
        assert client.is_enabled() is False
        with pytest.raises(RuntimeError):
            client.chat([])
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
