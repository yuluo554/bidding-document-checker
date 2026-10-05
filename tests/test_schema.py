"""参数卡 IR：序列化往返、缺键默认值、未知键忽略（plan/04 §1 既定口径）。"""
import json

from bidchecker.schema import (
    DOC_BID,
    DOC_TENDER,
    SCHEMA_VERSION,
    STATUS_CONFORM,
    STATUS_MANUAL,
    STATUS_NONCONFORM,
    BidCard,
    Bond,
    Evidence,
    Finding,
    KeyDates,
    PerfItem,
    PersonItem,
    PriceItem,
    Prices,
    ProjectInfo,
    Qualification,
    RejectionClause,
    Scoring,
    ScoringItem,
    StarClause,
    StarResponse,
    TenderCard,
)


def _full_tender_card():
    return TenderCard(
        project=ProjectInfo(
            name="某单位办公设备采购项目",
            number="TC-2026-001",
            buyer="某采购单位",
            agency="某招标代理有限公司",
        ),
        qualifications=[
            Qualification(
                item_id="Q1",
                requirement="具备有效的 ISO9001 质量管理体系认证证书",
                category="qualification",
                evidence=Evidence(
                    section="第二章 投标人须知",
                    quote="投标人须具备有效的 ISO9001 质量管理体系认证证书",
                    line=42,
                ),
            ),
            Qualification(item_id="Q2", requirement="近三年类似业绩不少于 2 项", category="performance", level="2 项"),
        ],
        star_clauses=[
            StarClause(
                item_id="S1",
                marker="★",
                text="交货期：合同签订后 30 日内",
                evidence=Evidence(section="第五章 技术要求", quote="★交货期：合同签订后 30 日内。", line=88),
            )
        ],
        scoring=Scoring(
            method="综合评分法",
            items=[ScoringItem(name="技术", weight=60.0), ScoringItem(name="商务", weight=40.0)],
            price_weight=30.0,
        ),
        bond=Bond(amount=20000.0, currency="CNY", forms=["银行转账", "保函"], deadline="2026-11-01"),
        key_dates=KeyDates(
            issue_start="2026-10-10",
            submit_deadline="2026-11-01 09:30",
            open_time="2026-11-01 09:30",
            validity_days=90,
        ),
        rejection_clauses=[
            RejectionClause(item_id="R1", text="未按规定缴纳投标保证金的", basis="87号令第37条")
        ],
    )


def test_tender_card_roundtrip():
    card = _full_tender_card()
    data = card.to_dict()
    assert json.loads(json.dumps(data, ensure_ascii=False)) == data  # 纯 JSON 兼容
    assert TenderCard.from_dict(data) == card


def test_bid_card_roundtrip():
    card = BidCard(
        bidder="某科技有限公司",
        prices=Prices(
            total_words="贰拾万元整",
            total_number=200000.0,
            items=[PriceItem(name="设备A", amount=120000.0), PriceItem(name="设备B", amount=80000.0)],
            items_sum=200000.0,
        ),
        star_responses=[
            StarResponse(
                star_id="S1",
                responded=True,
                location="第四章 技术方案",
                quote="交货期：合同签订后 25 日内",
                deviation="优于招标要求",
            )
        ],
        personnel=[PersonItem(name="张工", cert_name="注册建造师", cert_no="CERT-2026-0001", valid_until="2027-01-01")],
        performance=[PerfItem(name="某类似项目", amount=500000.0, date="2025-06-01", counterparty="某单位")],
    )
    assert BidCard.from_dict(card.to_dict()) == card


def test_from_dict_partial_and_unknown_keys():
    card = BidCard.from_dict(
        {
            "doc_type": "bid",
            "unknown_field": 1,
            "bidder": "某公司",
            "prices": {"total_number": 100, "junk": True},
        }
    )
    assert card.bidder == "某公司"
    assert card.schema_version == SCHEMA_VERSION
    assert card.prices.total_number == 100.0  # int → float 归一
    assert card.prices.items == []
    assert card.qualifications == []
    assert card.key_dates.validity_days is None


def test_doc_type_defaults():
    assert TenderCard().doc_type == DOC_TENDER
    assert BidCard().doc_type == DOC_BID


def test_finding_roundtrip_and_status_vocabulary():
    assert (STATUS_CONFORM, STATUS_NONCONFORM, STATUS_MANUAL) == ("符合", "不符合", "待人工确认")
    finding = Finding(
        check_id="CHK-Q-01",
        status=STATUS_NONCONFORM,
        risk_level="high",
        message="资格条件 Q1 缺失响应",
        basis=["87号令第37条", "TenderCard.qualifications[Q1]"],
        evidence=[Evidence(section="第二章 资格证明文件", quote="（未提供 ISO9001 证书）")],
    )
    assert Finding.from_dict(finding.to_dict()) == finding
