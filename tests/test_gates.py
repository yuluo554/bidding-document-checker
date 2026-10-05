"""类目隔离门控：only_if 对全部 check_type 生效（plan/04 §2.2）。"""
from bidchecker.rules.engine import RULE_TYPES
from bidchecker.rules.gates import rule_applies


def test_rule_types_declared():
    assert set(RULE_TYPES) == {
        "qualification_match",
        "star_response",
        "arithmetic_consistency",
        "date_logic",
        "bond_check",
        "rejection_scan",
        "price_check",
    }


def test_no_gate_always_applies():
    assert rule_applies({"id": "CHK-1"}, "任意文本") is True
    assert rule_applies({"id": "CHK-1", "only_if": {}}, "任意文本") is True
    assert rule_applies({"id": "CHK-1", "only_if": {"keywords": []}}, "任意文本") is True


def test_all_keywords_must_match():
    rule = {"id": "CHK-GRD-01", "only_if": {"keywords": ["货物", "设备"]}}
    assert rule_applies(rule, "本项目为货物类设备采购") is True
    assert rule_applies(rule, "本项目为服务类采购") is False


def test_gate_on_object_rule():
    class Rule:
        only_if = {"keywords": ["服务"]}

    assert rule_applies(Rule(), "服务类项目") is True
    assert rule_applies(Rule(), "货物类项目") is False


def test_gate_applies_to_any_rule_type():
    """门控挂在分派层：同一 only_if 形态适用于任何 rule_type（conditional 分支不漏接）。"""
    for rule_type in RULE_TYPES:
        rule = {"id": f"CHK-SVC-{rule_type}", "rule_type": rule_type, "only_if": {"keywords": ["服务"]}}
        assert rule_applies(rule, "服务类项目") is True, rule_type
        assert rule_applies(rule, "货物类项目") is False, rule_type
