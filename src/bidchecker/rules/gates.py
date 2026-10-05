"""类目隔离门控：only_if 关键词命中才激活规则，对全部 rule_type 生效（plan/04 §2.2）。

跨类目误查参数是同类系统实测踩过的坑（conditional/checklist 分支最容易漏接门控）——
引擎在分派任何 check_type 之前必须先过本门控。
"""

from typing import Any, Union


def rule_applies(rule: Any, text: str) -> bool:
    """规则（dict，来自 rules.json；或带同名属性的对象）+ 输入文本全文 → 是否激活。

    only_if 缺失/keywords 为空 → 恒激活；否则 only_if.keywords 全部出现在 text 才激活。
    """
    if isinstance(rule, dict):
        only_if = rule.get("only_if")
    else:
        only_if = getattr(rule, "only_if", None)
    if not only_if:
        return True
    keywords: Union[list, tuple] = []
    if isinstance(only_if, dict):
        keywords = only_if.get("keywords") or []
    else:
        keywords = list(only_if)
    if not keywords:
        return True
    return all(kw in text for kw in keywords)
