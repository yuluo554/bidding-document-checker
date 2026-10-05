"""LLM 兜底通路（可选、默认关闭）：解析兜底/别名归一/复核/报告行文。

M4 交付：client.chat（OpenAI 兼容，标准库 urllib 传输）+ fallback.fill_missing_slots
（宁缺槽位兜底，quote ⊂ 原文硬校验 + 数值合法性校验）。

数值结论永远来自确定性规则（plan/04 §2.2 防幻觉纪律）；LLM 不产生/不修改任何
Finding（status 只由确定性规则产生）；不可达即整链降级纯规则通路。
"""
