"""LLM 兜底通路（M4）：chat 客户端、解析兜底硬校验、不可达降级。

纪律（plan/04 §三 + HANDOFF-M4）：LLM 只填"宁缺"槽位、quote ⊂ 原文硬校验、
数值过合法性校验才入卡、不覆盖确定性抽取；LLM 不产生/不修改 Finding.status；
不可达时整链退化为纯规则通路，基准照常达标（bench 固定 llm_fallback=False）。
"""
import io
import json
import urllib.error

import pytest

from bidchecker.llm import client
from bidchecker.llm.client import LLMError
from bidchecker.llm.fallback import fill_missing_slots
from bidchecker.schema import BidCard, Prices, TenderCard

ENV_KEYS = (client.ENV_BASE_URL, client.ENV_API_KEY, client.ENV_MODEL)


@pytest.fixture
def llm_env(monkeypatch):
    monkeypatch.setenv(client.ENV_BASE_URL, "https://llm.example.com/v1")
    monkeypatch.setenv(client.ENV_API_KEY, "sk-test")
    monkeypatch.setenv(client.ENV_MODEL, "qwen3-test")


class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _patch_urlopen(monkeypatch, payload=None, exc: Exception = None, calls=[0]):
    counter = {"n": 0}

    def fake_urlopen(request, timeout=None):
        counter["n"] += 1
        if exc is not None:
            raise exc
        body = json.dumps(payload).encode("utf-8")
        return _FakeResp(body)

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    return counter


# ---------------------------------------------------------------- chat 客户端
def test_chat_without_config_raises_runtime_error(monkeypatch):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    assert client.is_enabled() is False
    with pytest.raises(RuntimeError):
        client.chat([{"role": "user", "content": "x"}])


def test_chat_happy_path_and_request_shape(monkeypatch, llm_env):
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResp(json.dumps(
            {"choices": [{"message": {"content": "hello"}}]}).encode("utf-8"))

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    out = client.chat([{"role": "user", "content": "你好"}], max_retries=0)
    assert out == "hello"
    assert captured["url"].endswith("/chat/completions")
    assert captured["body"]["model"] == "qwen3-test"
    assert captured["body"]["enable_thinking"] is False
    assert captured["body"]["messages"][0]["content"] == "你好"


def test_chat_strips_think_and_fences(monkeypatch, llm_env):
    content = "<think>推理过程</think>```json\n[{\"a\": 1}]\n```"
    _patch_urlopen(monkeypatch, payload={"choices": [{"message": {"content": content}}]})
    out = client.chat([], max_retries=0)
    assert out == '[{"a": 1}]'


def test_chat_retries_then_llm_error(monkeypatch, llm_env):
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    counter = _patch_urlopen(monkeypatch,
                             exc=urllib.error.URLError("connection refused"))
    with pytest.raises(LLMError):
        client.chat([], timeout=0.1, max_retries=2)
    assert counter["n"] == 3  # 首发 + 2 次重试


def test_clean_content_repair_and_errors():
    assert client._clean_content('前缀 {"a": 1}') == '{"a": 1}'
    assert client._clean_content('{"a": 1}') == '{"a": 1}'
    assert client._clean_content("纯文本回复") == "纯文本回复"
    with pytest.raises(LLMError):
        client._clean_content("")
    with pytest.raises(LLMError):
        client._clean_content("<think>未闭合的思考块")


# ---------------------------------------------------------------- 解析兜底
def _fake_chat(items):
    def chat_fn(messages, **kwargs):
        return json.dumps(items, ensure_ascii=False)
    return chat_fn


BID_TEXT = (
    "投标总价（大写）：人民币壹佰万元整\n"
    "投标总价（小写）：￥1,000,000.00\n"
    "分项合计：￥1,000,000.00\n"
    "1. 投标有效期为自投标截止之日起90日历天。\n"
    "编制完成时间：2026-10-14 17:30\n"
)


def test_fill_disabled_no_request():
    card = BidCard()  # 全部"宁缺"
    report = fill_missing_slots(card, BID_TEXT, chat_fn=None)
    assert report.requested and not report.applied  # 未启用：零请求零改动


def test_fill_applies_valid_slot_and_creates_container():
    card = BidCard()
    card.prices = None
    items = [{"field": "prices.total_number", "value": 1000000,
              "quote": "投标总价（小写）：￥1,000,000.00"}]
    report = fill_missing_slots(card, BID_TEXT, chat_fn=_fake_chat(items))
    assert report.applied == ["prices.total_number"]
    assert isinstance(card.prices, Prices)
    assert card.prices.total_number == 1000000.0


def test_fill_drops_quote_not_in_text():
    card = BidCard()
    items = [{"field": "prices.total_number", "value": 1000000,
              "quote": "这句话原文里不存在"}]
    report = fill_missing_slots(card, BID_TEXT, chat_fn=_fake_chat(items))
    assert not report.applied
    assert any("quote非原文子串" in d for d in report.dropped)
    assert card.prices is None  # 未入卡


def test_fill_drops_illegal_values():
    card = BidCard()
    items = [
        {"field": "prices.total_number", "value": -5, "quote": "投标总价"},
        {"field": "key_dates.validity_days", "value": "三十天", "quote": "投标有效期"},
        {"field": "unknown.field", "value": 1, "quote": "投标总价"},
    ]
    report = fill_missing_slots(card, BID_TEXT, chat_fn=_fake_chat(items))
    assert not report.applied
    assert len(report.dropped) == 3
    assert card.prices is None and card.key_dates.validity_days is None


def test_fill_words_amount_legality():
    card = BidCard()
    ok = [{"field": "prices.total_words", "value": "壹佰万元整",
           "quote": "投标总价（大写）：人民币壹佰万元整"}]
    report = fill_missing_slots(card, BID_TEXT, chat_fn=_fake_chat(ok))
    assert report.applied == ["prices.total_words"]
    bad = [{"field": "prices.total_words", "value": "这是不是金额的文本",
            "quote": "投标总价（大写）"}]
    card2 = BidCard()
    report2 = fill_missing_slots(card2, BID_TEXT, chat_fn=_fake_chat(bad))
    assert not report2.applied and card2.prices is None


def test_fill_never_overwrites_deterministic_value():
    card = BidCard()
    card.key_dates.validity_days = 90
    items = [{"field": "key_dates.validity_days", "value": 1,
              "quote": "投标有效期为自投标截止之日起90日历天"}]
    report = fill_missing_slots(card, BID_TEXT, chat_fn=_fake_chat(items))
    assert not report.applied
    assert card.key_dates.validity_days == 90  # 不覆盖


def test_fill_invalid_json_raises_llm_error():
    card = BidCard()
    with pytest.raises(LLMError):
        fill_missing_slots(card, BID_TEXT,
                           chat_fn=lambda m, **k: "这不是 JSON")


# ---------------------------------------------------------------- 流水线降级
def test_pipeline_llm_unreachable_degrades_to_pure_rules(tmp_path, monkeypatch):
    """LLM 已配置但不可达 → 整链退化纯规则通路，findings 与禁用时完全一致。"""
    from pathlib import Path

    import bidchecker.pipeline as pl
    from bidchecker.parsers.bid import parse_bid as real_parse

    from bidchecker.pipeline import run_pipeline

    project = Path(__file__).resolve().parent.parent / "examples" / "demo-services-1"

    def broken_parse(text):
        card = real_parse(text)
        if "瑞泰" in text:
            card.prices = None  # 制造"宁缺"位：兜底才会真正发起 LLM 调用
        return card

    monkeypatch.setattr(pl, "parse_bid", broken_parse)
    baseline = run_pipeline(project, llm_fallback=False)
    monkeypatch.setattr(client, "is_enabled", lambda: True)
    monkeypatch.setattr(client.time, "sleep", lambda s: None)
    _patch_urlopen(monkeypatch, exc=urllib.error.URLError("refused"))
    degraded = run_pipeline(project)
    assert degraded.finding_dicts() == baseline.finding_dicts()
    assert not degraded.failed
    parse_detail = next(s.detail for s in degraded.stages if s.name == "parse_bids")
    assert "LLM兜底不可达" in parse_detail


def test_pipeline_llm_fills_slot_feeds_engine(tmp_path, monkeypatch):
    """LLM 填充的槽位进卡后由确定性引擎判定——status 仍只来自规则。"""
    from pathlib import Path

    import bidchecker.pipeline as pl
    from bidchecker.parsers.bid import parse_bid as real_parse

    project = Path(__file__).resolve().parent.parent / "examples" / "demo-services-1"
    first_bid_file = sorted((project / "bids").glob("*.md"))[0]
    bid_text = first_bid_file.read_text(encoding="utf-8")

    def broken_parse(text):
        card = real_parse(text)
        if "瑞泰" in text:
            card.prices = None  # 模拟规则抽取失败（宁缺位）
        return card

    def fake_chat(messages, **kwargs):
        return json.dumps([{"field": "prices.total_number", "value": 9_999_999,
                            "quote": "投标总价（小写）"}], ensure_ascii=False)

    monkeypatch.setattr(pl, "parse_bid", broken_parse)
    monkeypatch.setattr(client, "is_enabled", lambda: True)
    monkeypatch.setattr(client, "chat", fake_chat)
    result = pl.run_pipeline(project)
    parse_detail = next(s.detail for s in result.stages if s.name == "parse_bids")
    assert "LLM兜底 应用" in parse_detail
    # 填充后的总价超最高限价 → 确定性规则产出 rejection_scan（结论与 LLM 无关）
    rj = [d for d in result.finding_dicts()
          if d["check_id"] == "CHK-RJ-01" and "瑞泰" in d["target"]]
    assert rj and rj[0]["status"] == "不符合"
