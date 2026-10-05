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


def test_stub_paths_raise_not_implemented():
    """骨架期 stub 行为锁定：M3/M4 未交付路径调用即 NotImplementedError。"""
    from bidchecker.pipeline import run_pipeline
    from bidchecker.rules.engine import run_checks
    from bidchecker.schema import BidCard, TenderCard

    with pytest.raises(NotImplementedError):
        run_checks(TenderCard(), BidCard())
    with pytest.raises(NotImplementedError):
        run_pipeline("examples/demo")


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
