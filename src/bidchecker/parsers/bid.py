"""投标文件解析器：固定体例 → BidCard（plan/04 §三）。M2 交付。"""

from bidchecker.schema import BidCard


def parse_bid(text: str) -> BidCard:
    """投标文件全文 → 投标响应参数卡（同 tender 五步流水线）。"""
    raise NotImplementedError("bid 解析器计划于 M2 交付（plan/05 M2）")
