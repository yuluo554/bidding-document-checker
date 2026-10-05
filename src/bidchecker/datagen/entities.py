"""虚构主体池：招标人/代理/投标人/人名/证书编号/项目名（合规红线 D3：全合成、零真实主体）。

命名规则：城市用文学虚构名（江州/临江/云溪），公司名走"生僻组合+通用后缀"，
证书编号用 CERT-/PMP-/ENG-/PAY- 合成前缀——与任何真实主体重名即数据 bug（入台账排查）。
池序即选择序（tuple 有序），由 DetRng 消费，禁止任何运行期重排。
"""
from __future__ import annotations

from typing import List

from bidchecker.datagen.rng import DetRng

BUYERS_GOODS = (
    "江州市城建投资集团有限公司",
    "云溪区人民医院",
    "临江市职业技术学院",
)
BUYERS_SERVICES = (
    "临江市第一中学",
    "江州市政务服务中心",
    "云溪区数据局",
)
AGENCIES = (
    "华信达项目管理有限公司",
    "中鸿信工程咨询有限公司",
    "正阳招标代理有限公司",
)
BIDDERS = (
    "瑞泰机电设备有限公司",
    "蓝驰信息技术有限公司",
    "恒诺办公设备有限公司",
    "安捷计算机系统有限公司",
    "汇智软件服务有限公司",
    "启明智能化工程有限公司",
)
PERSON_NAMES = (
    "张伟", "李娜", "王强", "刘敏", "陈杰", "杨帆", "赵磊", "黄静", "周涛", "吴丽",
)
SUBJECTS_GOODS = ("办公设备", "计算机设备", "医疗设备", "实验室仪器设备")
SUBJECTS_SERVICES = ("智慧校园运维服务", "信息化运维服务", "档案数字化加工服务", "物业管理服务")
COUNTERPARTIES = (
    "云溪区中医医院",
    "临江市第二实验小学",
    "江州市文化馆",
    "靖江区市场监督管理局",
)

# D11 围标痕迹注入用：长模板句池（≥40 字，句间无公共子串，两份投标共句即证据）
TEMPLATE_SENTENCES = (
    "根据我公司多年同类项目实施经验并结合本项目实际特点，我方将严格按照招标文件要求的"
    "各项技术指标组织供货安装与调试，确保一次性验收合格并建立专属服务档案。",
    "我公司承诺为本项目配备专职项目经理与原厂技术支持团队，在项目实施全周期内提供"
    "备机替换与驻场巡检服务，确保用户业务连续性达到合同约定的服务水平。",
    "针对本项目个性化需求，我方制定了详细的分阶段实施方案与风险预案，所有关键节点"
    "均设置双重复核机制，并在验收前完成不少于三轮的全流程内部测试。",
)


def pick_project_identity(rng: DetRng, category: str) -> dict:
    """抽样项目身份：项目名/编号/招标人/代理/品目（货物 or 服务）。"""
    goods = category == "goods"
    buyer = rng.choice(BUYERS_GOODS if goods else BUYERS_SERVICES)
    subject = rng.choice(SUBJECTS_GOODS if goods else SUBJECTS_SERVICES)
    return {
        "name": f"{buyer}{subject}采购项目",
        "number": f"ZB-2026-{rng.randint(1000, 9999)}",
        "buyer": buyer,
        "agency": rng.choice(AGENCIES),
        "subject": subject,
    }


def pick_bidders(rng: DetRng, n: int) -> List[str]:
    """不重复抽 n 家投标人（顺序即投标文件编号顺序）。"""
    return rng.sample(BIDDERS, n)


def cert_no(rng: DetRng, prefix: str = "CERT") -> str:
    return f"{prefix}-2026-{rng.randint(1000, 9999)}"
