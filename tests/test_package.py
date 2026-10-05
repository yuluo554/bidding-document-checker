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
    """骨架期 stub 行为锁定：调用即 NotImplementedError（M2/M3/M4 替换为实现）。"""
    from bidchecker.parsers.bid import parse_bid
    from bidchecker.parsers.tender import parse_tender
    from bidchecker.pipeline import run_pipeline
    from bidchecker.rules.engine import run_checks
    from bidchecker.schema import BidCard, TenderCard

    with pytest.raises(NotImplementedError):
        parse_tender("招标文件全文")
    with pytest.raises(NotImplementedError):
        parse_bid("投标文件全文")
    with pytest.raises(NotImplementedError):
        run_checks(TenderCard(), BidCard())
    with pytest.raises(NotImplementedError):
        run_pipeline("examples/demo")


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
