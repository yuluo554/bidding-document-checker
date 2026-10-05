"""端到端流水线编排（状态机：节点/重试/耗时记录）。

节点顺序（plan/04 §六）：load → parse_tender → parse_bids → checks → collusion(可选)
→ aggregate → report(可选)。单节点失败落失败清单，不中断其余节点。
M2 起分阶段交付。
"""

STAGES = ("load", "parse_tender", "parse_bids", "checks", "collusion", "aggregate", "report")


def run_pipeline(project_dir):
    """项目目录 → findings + 报告产物。M2 交付解析与校核段，M5 交付编排完整态。"""
    raise NotImplementedError("端到端流水线计划于 M2 起分阶段交付（plan/05）")
