"""datagen 内部模型：项目包（招标卡+投标卡束）、星号条款登记表、真值记录。

真值即卡片：build 产物是"缺陷注入后"的 schema.TenderCard/BidCard——文档由卡片渲染，
卡片就是解析真值（M2 bench parse 直接比对，不经 JSON，见 datagen/__init__ 契约注释）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from bidchecker.schema import BidCard, TenderCard

# ---------------------------------------------------------------- 星号条款登记表
# kind 仅作方向说明（floor=不少于，更小值更差 / ceil=不超过，更大值更差）；
# dev_pool 是 D5 注入的"更差目标值"（绝对值，非偏差量——避免小基数条款算出负数）；
# text/response 是渲染与真值 quote 的唯一来源（先登记后渲染，杜绝文本后改写）。
STAR_DEFS: Dict[str, Tuple[Dict[str, Any], ...]] = {
    "goods": (
        {"item_id": "S1", "marker": "★", "kind": "floor",
         "text": "所投设备整体质保期不少于{v}个月",
         "response": "响应。所投设备整体质保期为{v}个月，满足招标文件要求。",
         "value": 36, "dev_pool": (24, 30)},
        {"item_id": "S2", "marker": "▲", "kind": "floor",
         "text": "交货期：合同签订后{v}日内完成供货并安装调试",
         "response": "响应。交货期：合同签订后{v}日内完成供货并安装调试，满足招标文件要求。",
         "value": 60, "dev_pool": (45, 50, 55)},
        {"item_id": "S3", "marker": "★", "kind": "ceil",
         "text": "质保期内故障响应时间不超过{v}小时",
         "response": "响应。质保期内故障响应时间不超过{v}小时，满足招标文件要求。",
         "value": 2, "dev_pool": (4, 8)},
    ),
    "services": (
        {"item_id": "S1", "marker": "★", "kind": "ceil",
         "text": "服务期内驻场响应时间不超过{v}分钟",
         "response": "响应。服务期内驻场响应时间不超过{v}分钟，满足招标文件要求。",
         "value": 30, "dev_pool": (60, 120)},
        {"item_id": "S2", "marker": "▲", "kind": "floor",
         "text": "服务团队进驻：合同签订后{v}日内完成进场",
         "response": "响应。服务团队进驻：合同签订后{v}日内完成进场，满足招标文件要求。",
         "value": 5, "dev_pool": (10, 15)},
        {"item_id": "S3", "marker": "★", "kind": "ceil",
         "text": "重大故障修复时间不超过{v}小时",
         "response": "响应。重大故障修复时间不超过{v}小时，满足招标文件要求。",
         "value": 8, "dev_pool": (24, 48)},
    ),
}

# ---------------------------------------------------------------- 资格条件登记表
# (item_id, category, requirement, required_level)；Q4 的 AAA 是 D3（等级不足）的注入靶。
# "str | None" 仅为注解可读性（模块带 from __future__ import annotations，py3.8 安全）。
QUAL_DEFS: Tuple[Tuple[str, str, str, Any], ...] = (
    ("Q1", "qualification", "具有独立承担民事责任能力的法人，提供有效营业执照", None),
    ("Q2", "finance", "财务状况良好，提供上一年度经审计的财务报告", None),
    ("Q3", "qualification", "具有有效的ISO9001质量管理体系认证证书", None),
    ("Q4", "qualification", "具有有效的企业信用等级证书", "AAA"),
    ("Q5", "performance", "提供2023年以来至少1个类似项目业绩合同", None),
    ("Q6", "personnel", "拟投入项目负责人具有PMP项目管理证书", None),
)


def rejection_texts(validity_days: int, budget_cap: int) -> Tuple[Tuple[str, str], ...]:
    """否决条款 R1–R4（依据均为"招标文件自设"，法规条号由 M3 知识库挂接）。

    R1 内嵌最高限价金额：schema 冻结无预算字段，M3 引擎从 R1 文本抽取限价做 D12 核验
    （这是"卡外参数走条款文本"的既定口径，见 ProjectBundle.meta 注释）。
    """
    return (
        ("R1", f"投标报价超过最高限价（人民币{budget_cap:,}.00元）的，其投标无效。"),
        ("R2", "未按要求提交投标保证金的，其投标无效。"),
        ("R3", f"投标有效期不足{validity_days}日历天的，其投标无效。"),
        ("R4", "★号条款不满足或者未响应的，其投标无效。"),
    )


# ---------------------------------------------------------------- 分项报价构成
# (名称, 整数百分比)；百分比用整数（生成路径不引入浮点），末项按残差找平到分项合计。
PRICE_ITEMS: Dict[str, Tuple[Tuple[str, int], ...]] = {
    "goods": (("主机设备", 70), ("辅助设备", 15), ("安装调试费", 10), ("运输保险费", 5)),
    "services": (("人工服务费", 60), ("软件与工具费", 20), ("差旅与现场费", 12), ("管理费", 8)),
}


# ---------------------------------------------------------------- 项目包模型
@dataclass
class TruthFinding:
    """真值记录：主期望（kind=main）与同注入隐含结论（kind=also）共用此结构。

    e2e 对账口径（plan/05 §1.4）：按"目标文档全部非 pass 集合"匹配——
    (rule_type, status, risk_level, target) 四元组唯一确定一条期望。
    """

    defect_id: str
    kind: str  # "main" | "also"
    rule_type: str
    status: str
    risk_level: str
    target: str = ""  # 相对路径："tender.md" / "bids/<投标人>.md" / 围标对 "bids/A.md|bids/B.md"
    note: str = ""

    def to_truth_dict(self) -> Dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "rule_type": self.rule_type,
            "status": self.status,
            "risk_level": self.risk_level,
            "target": self.target,
            "note": self.note,
        }


@dataclass
class BidBundle:
    """单份投标：响应参数卡（真值）+ 仅渲染用附件位（围标痕迹、凭证号等卡外信息）。"""

    bidder: str
    card: BidCard
    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectBundle:
    """演示项目包：招标卡 + N 份投标卡 + 真值记录（注入后状态）。

    meta 承载体例级"卡外真值"（冻结 schema 无对应字段的参数，如最高限价）：
    渲染进文档、注入器消费、M3 引擎从文档条款（如 R1 内嵌金额）解析取用。
    """

    key: str
    category: str  # "goods" | "services"
    clean: bool
    seed: int
    tender: TenderCard
    bids: List[BidBundle]
    findings: List[TruthFinding] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    def bid_target(self, index: int) -> str:
        return f"bids/{self.bids[index].bidder}.md"

    def pair_target(self, i: int, j: int) -> str:
        return f"bids/{self.bids[i].bidder}.md|bids/{self.bids[j].bidder}.md"
