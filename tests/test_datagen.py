"""datagen 守门测试：位级一致 / fixtures 字节冻结 / CR 门 / D1–D12 覆盖 / 互斥表 / 体例结构。"""
import json
import re
from pathlib import Path

import pytest

from bidchecker.datagen import (DEMO_PROJECTS, DEFECT_FINDINGS, build_project,
                                run_datagen)
from bidchecker.datagen.defects import validate_plan
from bidchecker.datagen.rng import DetRng, fnv1a64

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"

ALL_DEFECTS = {f"D{i}" for i in range(1, 13)}
VALID_RULE_TYPES = {"qualification_match", "star_response", "arithmetic_consistency",
                    "date_logic", "bond_check", "rejection_scan", "price_check", "collusion"}


def _tree(root: Path):
    """相对路径 → 字节 的全量快照（排序保证顺序确定）。"""
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out = tmp_path_factory.mktemp("datagen")
    run_datagen(seed=42, out_root=str(out))
    return out


# ---------------------------------------------------------------- 确定性与冻结
def test_same_seed_bit_identical(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    run_datagen(seed=42, out_root=str(a))
    run_datagen(seed=42, out_root=str(b))
    assert _tree(a) == _tree(b), "同 seed 两次生成必须位级一致"


def test_different_seed_changes_content(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    run_datagen(seed=42, out_root=str(a))
    run_datagen(seed=43, out_root=str(b))
    assert _tree(a) != _tree(b), "不同 seed 应产出不同数据"


def test_examples_fixture_frozen(generated):
    """字节冻结门：入仓 examples/ 必须与 seed=42 再生成逐字节一致（手改即挂）。"""
    assert EXAMPLES.is_dir(), "examples/ 未随仓提交（fixtures 字节冻结门失效）"
    committed, fresh = _tree(EXAMPLES), _tree(generated)
    assert set(committed) == set(fresh), (
        f"examples/ 文件集漂移：多 {set(committed) - set(fresh)} 少 {set(fresh) - set(committed)}")
    drifted = [k for k in committed if committed[k] != fresh[k]]
    assert not drifted, f"examples/ 与 seed=42 再生成不一致（fixtures 被改动）：{drifted}"


def test_no_cr_no_bom_in_outputs(generated):
    """EOL/编码门：生成物出现 CR 或 BOM 即大声失败（plan/06 D12 防 autocrlf 基准全挂）。"""
    for rel, data in _tree(generated).items():
        assert b"\r" not in data, f"{rel} 出现 CR（检查换行来源）"
        assert not data.startswith(b"\xef\xbb\xbf"), f"{rel} 出现 UTF-8 BOM"


def test_no_cr_in_committed_examples():
    assert EXAMPLES.is_dir()
    for p in sorted(EXAMPLES.rglob("*")):
        if p.is_file():
            assert b"\r" not in p.read_bytes(), f"{p} 出现 CR（autocrlf 或手工编辑污染）"


# ---------------------------------------------------------------- 演示集与真值契约
def _truths(root: Path):
    out = {}
    for spec in DEMO_PROJECTS:
        out[spec.key] = json.loads(
            (root / spec.key / "ground_truth.json").read_text(encoding="utf-8"))
    return out


def test_demo_composition(generated):
    truths = _truths(generated)
    categories = {t["category"] for t in truths.values()}
    assert categories == {"goods", "services"}
    assert sum(t["category"] == "goods" for t in truths.values()) == 2
    cleans = [t for t in truths.values() if t["clean"]]
    assert len(cleans) == 1 and cleans[0]["expect_findings"] == [] and cleans[0]["also_expect"] == []


def test_truth_schema_and_defect_coverage(generated):
    seen_defects = set()
    for key, truth in _truths(generated).items():
        for key_list in ("expect_findings", "also_expect"):
            for entry in truth[key_list]:
                assert set(entry) == {"defect_id", "rule_type", "status",
                                      "risk_level", "target", "note"}
                assert entry["rule_type"] in VALID_RULE_TYPES
                assert entry["status"] in ("符合", "不符合", "待人工确认")
                assert entry["risk_level"] in ("high", "mid", "low")
                seen_defects.add(entry["defect_id"])
    assert seen_defects == ALL_DEFECTS, f"D1–D12 未全覆盖：缺 {ALL_DEFECTS - seen_defects}"


def test_truth_tuple_unique_per_target(generated):
    """真值契约自检：同目标 (rule_type,status,risk) 唯一（e2e 对账可分辨的前提）。"""
    for truth in _truths(generated).values():
        seen = set()
        for entry in truth["expect_findings"] + truth["also_expect"]:
            key = (entry["rule_type"], entry["status"], entry["risk_level"], entry["target"])
            assert key not in seen, f"四元组冲突：{key}"
            seen.add(key)


def test_targets_exist(generated):
    for spec in DEMO_PROJECTS:
        truth = json.loads((generated / spec.key / "ground_truth.json").read_text(encoding="utf-8"))
        assert (generated / spec.key / truth["tender_file"]).is_file()
        assert len(truth["bid_files"]) == spec.n_bids
        for rel in truth["bid_files"]:
            assert (generated / spec.key / rel).is_file()


# ---------------------------------------------------------------- 互斥表与计划校验
def test_mutual_exclusive_plan_rejected():
    with pytest.raises(ValueError):
        validate_plan([("bid:0", "D6"), ("bid:0", "D7")], n_bids=3)
    with pytest.raises(ValueError):
        validate_plan([("bid:0", "D12"), ("bid:0", "D6")], n_bids=3)


def test_wrong_location_plan_rejected():
    with pytest.raises(ValueError):
        validate_plan([("bid:0", "D10")], n_bids=3)  # D10 只打招标文件
    with pytest.raises(ValueError):
        validate_plan([("tender", "D11")], n_bids=3)  # D11 只打围标对


@pytest.mark.parametrize("seed", [1, 7, 42, 123, 2026])
def test_demo_plans_valid_across_seeds(seed):
    """注册表计划在多 seed 下通过构建期校验，且产出真值与计划一一对应。"""
    for spec in DEMO_PROJECTS:
        bundle = build_project(seed, spec.key, spec.category, spec.clean, spec.plan, spec.n_bids)
        plan_defects = {d for _, d in spec.plan}
        assert {f.defect_id for f in bundle.findings} == plan_defects


# ---------------------------------------------------------------- 体例结构（解析锚点）
def _md(root: Path, key: str):
    tender = (root / key / "tender.md").read_text(encoding="utf-8")
    truth = json.loads((root / key / "ground_truth.json").read_text(encoding="utf-8"))
    bid = (root / key / truth["bid_files"][0]).read_text(encoding="utf-8")
    return tender, bid


def test_chapter_structure(generated):
    for spec in DEMO_PROJECTS:
        tender, bid = _md(generated, spec.key)
        for i, title in enumerate(["招标公告", "投标人须知", "评标办法", "合同条款",
                                   "技术要求", "投标文件格式"], 1):
            assert f"## 第{'一二三四五六'[i - 1]}章 {title}" in tender, f"{spec.key} 招标第{i}章缺失"
        for i, title in enumerate(["投函声明", "资格证明文件", "商务偏差表", "技术方案",
                                   "开标一览表与分项报价", "承诺函",
                                   "拟投入人员与类似业绩清单"], 1):
            assert f"## 第{'一二三四五六七'[i - 1]}章 {title}" in bid, f"{spec.key} 投标第{i}章缺失"


def test_star_clause_markers_present(generated):
    tender, _ = _md(generated, "demo-goods-1")
    assert len(re.findall(r"^★ S\d：", tender, re.M)) == 2
    assert len(re.findall(r"^▲ S\d：", tender, re.M)) == 1


def test_fictional_disclaimer_present(generated):
    _, bid = _md(generated, "demo-goods-1")
    assert "均为虚构" in bid


def test_category_keyword_line(generated):
    """类目门控关键词落点：'采购类别：货物/服务' 行存在。"""
    for spec in DEMO_PROJECTS:
        tender, _ = _md(generated, spec.key)
        label = "货物" if spec.category == "goods" else "服务"
        assert f"采购类别：{label}" in tender


# ---------------------------------------------------------------- 随机源单元
def test_fnv1a64_stable():
    assert fnv1a64(b"demo-goods-1") == fnv1a64(b"demo-goods-1")
    assert fnv1a64(b"demo-goods-1") != fnv1a64(b"demo-goods-2")


def test_det_rng_sequence_stable():
    a, b = DetRng(42), DetRng(42)
    seq_a = [a.next_u64() for _ in range(8)]
    seq_b = [b.next_u64() for _ in range(8)]
    assert seq_a == seq_b
    rng = DetRng(1)
    for _ in range(200):
        assert 0 <= rng.below(7) < 7
    with pytest.raises(ValueError):
        DetRng(1).below(0)
