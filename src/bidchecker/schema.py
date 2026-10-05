"""统一中间表示（IR）：采购需求参数卡、投标响应参数卡与评审结论。

本模块是既定口径（plan/04-模块详设.md §1）：字段语义与结构一经定稿，任何变更必须
同步生成器真值语义与基准对账逻辑，并重跑全部基准确认不回退。

序列化约定：
- to_dict() 输出纯 JSON 兼容 dict；from_dict() 忽略未知键、缺键用 dataclass 默认值（向后兼容）；
- Evidence.quote 必须是原文逐字摘录（基准硬校验其为目标文档子串）。
"""
from __future__ import annotations

import dataclasses
import typing
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "1"

DOC_TENDER = "tender"
DOC_BID = "bid"

# 结论三级判定（plan/04 §2.2）：数值与布尔类结论只由确定性规则产生
STATUS_CONFORM = "符合"
STATUS_NONCONFORM = "不符合"
STATUS_MANUAL = "待人工确认"
STATUS_ALL = (STATUS_CONFORM, STATUS_NONCONFORM, STATUS_MANUAL)

RISK_HIGH = "high"
RISK_MID = "mid"
RISK_LOW = "low"

CATEGORY_QUALIFICATION = "qualification"
CATEGORY_FINANCE = "finance"
CATEGORY_PERFORMANCE = "performance"
CATEGORY_PERSONNEL = "personnel"
CATEGORY_OTHER = "other"


class _JsonMixin:
    """from_dict/to_dict 统一实现：递归构建、忽略未知键、缺键走默认值。"""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "_JsonMixin":
        return _build(cls, data)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class Evidence(_JsonMixin):
    """证据：章节定位 + 原文逐字摘录（+ 可选行号）。"""

    section: Optional[str] = None
    quote: Optional[str] = None
    line: Optional[int] = None


@dataclass
class ProjectInfo(_JsonMixin):
    name: Optional[str] = None
    number: Optional[str] = None
    buyer: Optional[str] = None
    agency: Optional[str] = None


@dataclass
class Qualification(_JsonMixin):
    """资格资格条件：招标侧=要求；投标侧=持有响应。"""

    item_id: str = ""
    requirement: str = ""
    category: str = CATEGORY_OTHER
    level: Optional[str] = None       # 要求等级（招标侧）/ 持有等级（投标侧）
    valid_until: Optional[str] = None  # ISO 日期：要求的有效期 / 证书有效期
    evidence: Optional[Evidence] = None


@dataclass
class StarClause(_JsonMixin):
    """实质性/星号条款（招标侧）：★ 强制、▲ 重要。"""

    item_id: str = ""
    marker: str = "★"
    text: str = ""
    evidence: Optional[Evidence] = None


@dataclass
class StarResponse(_JsonMixin):
    """投标侧对星号条款的响应。star_id 对应 TenderCard.star_clauses[].item_id。"""

    star_id: str = ""
    responded: bool = False
    location: Optional[str] = None
    quote: Optional[str] = None
    deviation: Optional[str] = None


@dataclass
class RejectionClause(_JsonMixin):
    """否决（无效投标）条款。basis 为法规条号（如 "87号令第37条"）或 "招标文件自设"。"""

    item_id: str = ""
    text: str = ""
    basis: Optional[str] = None
    evidence: Optional[Evidence] = None


@dataclass
class Bond(_JsonMixin):
    """投标保证金（招标侧=要求；投标侧 bond_response=缴纳响应）。"""

    amount: Optional[float] = None
    currency: str = "CNY"
    forms: List[str] = field(default_factory=list)
    deadline: Optional[str] = None


@dataclass
class KeyDates(_JsonMixin):
    issue_start: Optional[str] = None
    submit_deadline: Optional[str] = None
    open_time: Optional[str] = None
    validity_days: Optional[int] = None


@dataclass
class ScoringItem(_JsonMixin):
    name: str = ""
    weight: Optional[float] = None


@dataclass
class Scoring(_JsonMixin):
    method: Optional[str] = None
    items: List[ScoringItem] = field(default_factory=list)
    price_weight: Optional[float] = None


@dataclass
class PriceItem(_JsonMixin):
    name: str = ""
    amount: Optional[float] = None


@dataclass
class Prices(_JsonMixin):
    """开标一览表与分项报价（算术复核对象：total_words ↔ total_number ↔ items_sum）。"""

    total_words: Optional[str] = None
    total_number: Optional[float] = None
    items: List[PriceItem] = field(default_factory=list)
    items_sum: Optional[float] = None


@dataclass
class PersonItem(_JsonMixin):
    name: Optional[str] = None
    cert_name: Optional[str] = None
    cert_no: Optional[str] = None
    valid_until: Optional[str] = None


@dataclass
class PerfItem(_JsonMixin):
    name: Optional[str] = None
    amount: Optional[float] = None
    date: Optional[str] = None
    counterparty: Optional[str] = None


@dataclass
class TenderCard(_JsonMixin):
    """采购需求参数卡（招标侧解析产物）。"""

    doc_type: str = DOC_TENDER
    schema_version: str = SCHEMA_VERSION
    project: ProjectInfo = field(default_factory=ProjectInfo)
    qualifications: List[Qualification] = field(default_factory=list)
    star_clauses: List[StarClause] = field(default_factory=list)
    scoring: Optional[Scoring] = None
    bond: Optional[Bond] = None
    key_dates: KeyDates = field(default_factory=KeyDates)
    rejection_clauses: List[RejectionClause] = field(default_factory=list)


@dataclass
class BidCard(_JsonMixin):
    """投标响应参数卡（投标侧解析产物）。"""

    doc_type: str = DOC_BID
    schema_version: str = SCHEMA_VERSION
    project: ProjectInfo = field(default_factory=ProjectInfo)
    bidder: Optional[str] = None
    qualifications: List[Qualification] = field(default_factory=list)
    star_responses: List[StarResponse] = field(default_factory=list)
    prices: Optional[Prices] = None
    bond_response: Optional[Bond] = None
    key_dates: KeyDates = field(default_factory=KeyDates)
    personnel: List[PersonItem] = field(default_factory=list)
    performance: List[PerfItem] = field(default_factory=list)


@dataclass
class Finding(_JsonMixin):
    """单条校核结论。status=STATUS_NONCONFORM 时 risk_level 必填、basis 必须非空。"""

    check_id: str = ""
    status: str = STATUS_CONFORM
    risk_level: Optional[str] = None
    message: str = ""
    basis: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)


def _build(tp: Any, value: Any) -> Any:
    """按类型注解递归构建：dataclass / List[X] / Optional[X] / 基础类型数值归一。"""
    if value is None:
        return None
    origin = typing.get_origin(tp)
    if origin is list:
        item_tp = typing.get_args(tp)[0]
        return [_build(item_tp, v) for v in value]
    if origin is typing.Union:
        args = [a for a in typing.get_args(tp) if a is not type(None)]
        for a in args:
            if isinstance(value, dict) and isinstance(a, type) and dataclasses.is_dataclass(a):
                return _build(a, value)
        return _build(args[0], value)
    if isinstance(tp, type) and dataclasses.is_dataclass(tp):
        if not isinstance(value, dict):
            raise TypeError(f"{tp.__name__} 期望 dict，得到 {type(value).__name__}")
        hints = typing.get_type_hints(tp)
        kwargs = {}
        for f in dataclasses.fields(tp):
            if f.name in value:
                kwargs[f.name] = _build(hints[f.name], value[f.name])
        return tp(**kwargs)
    if tp is float and isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if tp is int and isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    return value
