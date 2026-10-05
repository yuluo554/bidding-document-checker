"""解析兜底（M4，可选通路）：对规则抽取失败的槽位做 LLM 抽取（plan/04 §三）。

纪律（防幻觉口径，HANDOFF-M4）：
- 只对规则抽取后仍为 None 的"宁缺"槽位发问，**绝不覆盖确定性抽取结果**；
- 输入 = 按字段关键词筛出的候选行（带行号的压缩行集合），不是全文倾倒；
- 返回要求 {field, value, quote}：quote 非原文逐字子串 → 该项整体丢弃；
  数值过合法性校验（金额可解析、天数/百分比范围、日期形态）才入卡；
- LLM 不可达/未启用/响应不合法 → 报告为空或抛 LLMError，调用方降级纯规则通路；
- 本模块只填参数卡槽位，**不产生、不修改任何 Finding**（结论 status 只由
  确定性规则产生，plan/04 §2.2）。

字段范围（FIELDS）：投标侧 9 个 / 招标侧 11 个"文档可携带"槽位；容器缺失
（prices/bond_response/bond/scoring 为 None）时按 schema 就地构建后再填。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from bidchecker.amounts import words_to_amount
from bidchecker.schema import (BidCard, Bond, Prices, Scoring, TenderCard)

# 每字段：(候选行关键词, 合法性校验)；关键词命中行进入候选集（截断 MAX_LINES 行）
MAX_LINES_PER_FIELD = 12

_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")


def _v_text(value: Any) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("空文本")
    return text


def _v_amount(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("布尔不是金额")
    if isinstance(value, (int, float)):
        num = float(value)
    else:
        cleaned = str(value).strip().replace("￥", "").replace("元", "") \
            .replace(",", "").replace("，", "").replace(" ", "")
        num = float(cleaned)
    if not math.isfinite(num) or num < 0:
        raise ValueError(f"金额非法: {value!r}")
    return num


def _v_days(value: Any) -> int:
    num = int(_v_amount(value))
    if num <= 0:
        raise ValueError(f"天数非法: {value!r}")
    return num


def _v_percent(value: Any) -> float:
    num = _v_amount(value)
    if num > 100:
        raise ValueError(f"权重非法: {value!r}")
    return num


def _v_datetime(value: Any) -> str:
    text = _v_text(value)
    if not _DATETIME_RE.match(text):
        raise ValueError(f"日期形态非法: {value!r}")
    return text


def _v_words(value: Any) -> str:
    text = _v_text(value)
    words_to_amount(text)  # 非法中文金额在此抛 ValueError
    return text


BID_FIELDS: Dict[str, Tuple[Tuple[str, ...], Callable[[Any], Any]]] = {
    "bidder": (("投标人",), _v_text),
    "project.name": (("项目名称",), _v_text),
    "project.number": (("项目编号",), _v_text),
    "project.buyer": (("招标人", "采购人"), _v_text),
    "prices.total_words": (("大写", "投标总价"), _v_words),
    "prices.total_number": (("小写", "投标总价"), _v_amount),
    "prices.items_sum": (("分项合计", "合计"), _v_amount),
    "bond_response.amount": (("保证金",), _v_amount),
    "key_dates.validity_days": (("有效期",), _v_days),
}

TENDER_FIELDS: Dict[str, Tuple[Tuple[str, ...], Callable[[Any], Any]]] = {
    "project.name": (("项目名称",), _v_text),
    "project.number": (("项目编号",), _v_text),
    "project.buyer": (("招标人", "采购人"), _v_text),
    "project.agency": (("代理",), _v_text),
    "bond.amount": (("保证金",), _v_amount),
    "bond.deadline": (("保证金",), _v_datetime),
    "key_dates.issue_start": (("获取", "发售"), _v_datetime),
    "key_dates.submit_deadline": (("截止",), _v_datetime),
    "key_dates.open_time": (("开标",), _v_datetime),
    "key_dates.validity_days": (("有效期",), _v_days),
    "scoring.method": (("评标方法", "评分办法"), _v_text),
    "scoring.price_weight": (("价格分",), _v_percent),
}

# 容器构建：路径首段容器为 None 时先建空容器（schema 默认形态）
_BID_CONTAINERS = {"prices": Prices, "bond_response": Bond}
_TENDER_CONTAINERS = {"bond": Bond, "scoring": Scoring}


@dataclass
class SlotFillReport:
    """单文档兜底结果：询问/写入/丢弃清单（只进阶段明细，不进落盘产物）。"""

    requested: List[str] = field(default_factory=list)
    applied: List[str] = field(default_factory=list)
    dropped: List[str] = field(default_factory=list)  # "字段:原因"


def fill_missing_slots(card, text: str, *,
                       chat_fn: Optional[Callable] = None) -> SlotFillReport:
    """参数卡 + 原文 → 兜底填充报告（未启用/无缺槽/不可达时零改动返回或抛错）。"""
    is_bid = isinstance(card, BidCard)
    specs = BID_FIELDS if is_bid else TENDER_FIELDS
    report = SlotFillReport()
    missing = {name for name in specs if _current_value(card, name) is None}
    report.requested = sorted(missing)
    if not missing:
        return report
    if chat_fn is None:
        from bidchecker.llm import client
        if not client.is_enabled():
            return report  # 未启用：零请求零改动（纯规则通路）
        chat_fn = client.chat

    content = chat_fn(_build_messages(card, text, missing, specs))
    items = _parse_items(content)
    for item in items:
        if not isinstance(item, dict):
            continue
        fname = item.get("field")
        quote, value = item.get("quote"), item.get("value")
        if fname not in missing:
            report.dropped.append(f"{fname}:非请求字段")
            continue
        if not isinstance(quote, str) or not quote or quote not in text:
            report.dropped.append(f"{fname}:quote非原文子串")
            continue
        try:
            validated = specs[fname][1](value)
        except (ValueError, TypeError):
            report.dropped.append(f"{fname}:值非法")
            continue
        if _current_value(card, fname) is not None:
            report.dropped.append(f"{fname}:已有值不覆盖")
            continue
        _apply(card, fname, validated, is_bid)
        report.applied.append(fname)
    return report


# ---------------------------------------------------------------- 内部
def _current_value(card, path: str) -> Any:
    obj: Any = card
    for part in path.split("."):
        if obj is None:
            return None
        obj = getattr(obj, part, None)
    return obj


def _apply(card, path: str, value: Any, is_bid: bool) -> None:
    parts = path.split(".")
    containers = _BID_CONTAINERS if is_bid else _TENDER_CONTAINERS
    if parts[0] in containers and getattr(card, parts[0]) is None:
        setattr(card, parts[0], containers[parts[0]]())
    obj: Any = card
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def _candidate_lines(text: str, keywords: Tuple[str, ...]) -> List[str]:
    """按关键词筛候选行（压缩行集合）：命中行带行号，截断 MAX_LINES_PER_FIELD。"""
    out = []
    for no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped and any(kw in stripped for kw in keywords):
            out.append(f"{no}|{stripped}")
            if len(out) >= MAX_LINES_PER_FIELD:
                break
    return out


def _build_messages(card, text: str, missing: set, specs: Dict) -> List[dict]:
    """system 纪律 + 压缩候选行 + 缺失字段清单 → messages（含行号便于溯源）。"""
    lines: List[str] = []
    seen: set = set()
    for fname in sorted(missing):
        for row in _candidate_lines(text, specs[fname][0]):
            if row not in seen:
                seen.add(row)
                lines.append(row)
    system = (
        "你是招投标文件字段抽取助手。只依据给定文档行抽取，禁止编造。"
        "仅输出 JSON 数组，每项形如 {\"field\": 字段名, \"value\": 抽取值, "
        "\"quote\": 原文逐字摘录}；quote 必须是文档行的原文子串；"
        "无法确定的字段不要输出；不要输出任何解释。"
    )
    user = (
        "缺失字段（value 形态：文本=字符串，金额=数字，天数=整数，日期=YYYY-MM-DD[ HH:MM]）：\n"
        + "\n".join(f"- {name}" for name in sorted(missing))
        + "\n\n文档行（行号|内容）：\n" + "\n".join(lines)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_items(content: str) -> List[Any]:
    """LLM 回复 → JSON 数组项；不合法 → LLMError（调用方按不可达降级）。"""
    from bidchecker.llm.client import LLMError
    import json
    try:
        data = json.loads(content)
    except ValueError as exc:
        raise LLMError(f"LLM 兜底响应不是合法 JSON：{exc}") from exc
    if not isinstance(data, list):
        raise LLMError("LLM 兜底响应不是 JSON 数组")
    return data


__all__ = ["SlotFillReport", "fill_missing_slots", "BID_FIELDS", "TENDER_FIELDS"]
