"""法规知识库三层落库（M3 DoD）：raw 台账 sha256、blocks.jsonl 字段完备、rules.json 形态。"""
import hashlib
import json
import re
from pathlib import Path

from bidchecker.knowledge import (STATUS_PENDING, STATUS_VERIFIED,
                                  basis_kind, basis_resolves, find_knowledge_dir,
                                  load_blocks, load_rules)
from bidchecker.rules.engine import CHECK_IDS, RULE_TYPES

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "data" / "knowledge"


def test_knowledge_dir_discovered():
    assert find_knowledge_dir() == KB
    assert find_knowledge_dir(str(ROOT)) == KB


def test_blocks_jsonl_well_formed():
    blocks = load_blocks(KB)
    assert len(blocks) >= 14
    for b in blocks:
        assert {"law", "article_no", "text", "source_url", "status"} <= set(b)
        assert b["status"] in (STATUS_VERIFIED, STATUS_PENDING)
        assert b["text"] and b["source_url"].startswith("http")
        kind = basis_kind(f"《{b['law']}》{b['article_no']}")
        assert kind[0] == "law"
    # 引擎引用的条文全部已核对
    cited = {(b["law"], b["article_no"]) for b in blocks if b["status"] == STATUS_VERIFIED}
    for cid_law, article in (("政府采购货物和服务招标投标管理办法", "第二十三条"),
                             ("政府采购货物和服务招标投标管理办法", "第三十九条"),
                             ("政府采购货物和服务招标投标管理办法", "第五十九条"),
                             ("政府采购货物和服务招标投标管理办法", "第六十条"),
                             ("政府采购货物和服务招标投标管理办法", "第六十三条"),
                             ("招标投标法实施条例", "第五十一条")):
        assert (cid_law, article) in cited
    # 查不到官方原文的条目必须显式待核对（入库纪律）
    pending = {(b["law"], b["article_no"]) for b in blocks if b["status"] == STATUS_PENDING}
    assert ("中华人民共和国招标投标法", "第三十三条") in pending
    assert ("中华人民共和国招标投标法", "第三十四条") in pending


def test_rules_json_well_formed():
    rules = load_rules(KB)
    ids = [r["id"] for r in rules]
    assert len(ids) == len(set(ids)), "check_id 重复"
    assert set(ids) == set(CHECK_IDS)
    for r in rules:
        # collusion（CHK-CL-01）由 M4 collusion 模块产出，不在引擎 RULE_TYPES 分派表内
        assert r["rule_type"] in RULE_TYPES or r["rule_type"] == "collusion"
        assert r["severity"] in ("high", "mid", "low")
        assert isinstance(r.get("only_if", {}), dict)
        assert r["name"] and r["advice"] and r["basis"]
    price = next(r for r in rules if r["id"] == "CHK-PC-01")
    assert price["params"]["ratio"] == 0.8
    # M4 围标提示规则：依据全部为官方逐字核验条文（实施条例 39/40 + 87号令 36/37）
    cl = next(r for r in rules if r["id"] == "CHK-CL-01")
    blocks = load_blocks(KB)
    for entry in cl["basis"]:
        assert basis_resolves(entry, blocks, None), f"CHK-CL-01 依据无法解析: {entry}"


def test_raw_files_ledger_sha256_matches():
    """raw/ 原文与 data/README.md 台账登记的 sha256 一致（台账即溯源凭据）。"""
    readme = (ROOT / "data" / "README.md").read_text(encoding="utf-8")
    raw_files = [p for p in (KB / "raw").glob("*.txt")]
    assert raw_files, "raw/ 缺少法规原文"
    for path in raw_files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        m = re.search(rf"{re.escape(path.name)}.*?`([0-9a-f]{{64}})`", readme, re.S)
        assert m, f"台账缺 {path.name} 的 sha256 登记"
        assert m.group(1) == digest, f"{path.name} sha256 与台账不符"


def test_basis_resolution_helpers():
    blocks = load_blocks(KB)
    assert basis_kind("《招标投标法实施条例》第五十一条") == (
        "law", "招标投标法实施条例", "第五十一条")
    assert basis_kind("R1") == ("clause", "R1")
    assert basis_kind("自定义说明") == ("other", "自定义说明")
    assert basis_resolves("《招标投标法实施条例》第五十一条", blocks, None) is True
    assert basis_resolves("《招标投标法实施条例》第九十九条", blocks, None) is False
    assert basis_resolves("R1", blocks, type("T", (), {"qualifications": [],
                                                       "star_clauses": [],
                                                       "rejection_clauses": []})()) is False
