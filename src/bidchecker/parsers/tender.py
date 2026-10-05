"""招标文件解析器：固定体例 → TenderCard（plan/04 §三 五步流水线）。M2 交付。"""

from bidchecker.schema import TenderCard


def parse_tender(text: str) -> TenderCard:
    """招标文件全文 → 采购需求参数卡。

    五步：预处理 → 章节切分 → 槽位抽取 → 合法性校验（超范围即丢弃）→ 证据绑定。
    """
    raise NotImplementedError("tender 解析器计划于 M2 交付（plan/05 M2）")
