"""符合性校核引擎：按 rule_type 分派 handler（plan/04 §二）。M3 交付。

纪律：
- 数值与布尔类结论只由确定性规则产生，LLM 不能改变 Finding.status；
- 每条 Finding.basis 必须能解析回知识库条文块或 TenderCard 条款 id；
- 分派任何 check_type 之前必须先过 gates.rule_applies 类目门控。
"""

from bidchecker.schema import BidCard, Finding, TenderCard

RULE_TYPES = (
    "qualification_match",
    "star_response",
    "arithmetic_consistency",
    "date_logic",
    "bond_check",
    "rejection_scan",
    "price_check",
)


def run_checks(tender: TenderCard, bid: BidCard):
    """TenderCard + BidCard → List[Finding]（三级判定：符合/不符合/待人工确认）。"""
    raise NotImplementedError("符合性校核引擎计划于 M3 交付（plan/05 M3）")
