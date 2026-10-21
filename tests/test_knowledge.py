"""法规知识库三层落库（M3 DoD）：raw 台账 sha256、blocks.jsonl 字段完备、rules.json 形态。

M7 增补：条文块带机读复核元数据（reviewed_on / next_review_due）、规则条数钉住 21。
"""
import datetime
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
EXPECTED_RULE_COUNT = 21
EXPECTED_BLOCK_COUNT = 16
REVIEW_CYCLE_MONTHS = 12


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


def test_blocks_carry_review_metadata():
    """D3 门：每条条文块必须带机读复核日期，且下次复核晚于本次（M7）。

    这是"日期只写在 README 台账里"的反面：复核锚必须进机器可读的 blocks。
    """
    blocks = load_blocks(KB)
    assert len(blocks) == EXPECTED_BLOCK_COUNT, (
        f"条文块条数变了（{len(blocks)} != {EXPECTED_BLOCK_COUNT}）："
        "若确为新增条文，请同步本常量与 data/README.md 台账")
    for b in blocks:
        key = f"{b['law']}{b['article_no']}"
        assert "reviewed_on" in b and "next_review_due" in b, f"{key} 缺复核元数据"
        try:
            reviewed = datetime.datetime.strptime(b["reviewed_on"], "%Y-%m-%d").date()
            due = datetime.datetime.strptime(b["next_review_due"], "%Y-%m-%d").date()
        except ValueError as exc:
            raise AssertionError(f"{key} 复核日期不可解析：{exc}") from exc
        assert due > reviewed, f"{key} next_review_due({due}) 必须晚于 reviewed_on({reviewed})"
        # 复核周期与 blocks 台账的 cycle_months 一致（已核对条文 12 个月；
        # 待核对条文可短于 12 个月，用于催补核）
        if b["status"] == STATUS_VERIFIED:
            months = (due.year - reviewed.year) * 12 + (due.month - reviewed.month)
            assert months == REVIEW_CYCLE_MONTHS, (
                f"{key} 已核对条文复核周期应 {REVIEW_CYCLE_MONTHS} 个月，实测 {months} 个月")
        else:
            assert due > datetime.date.today(), f"{key} 待核对条文已过复核期限 {due}"


def test_rules_count_is_pinned():
    """D2 门：rules.json 条数钉住 21（原自述写 20，实际 21；集合相等门抓不到条数漂移）。"""
    rules = load_rules(KB)
    assert len(rules) == EXPECTED_RULE_COUNT, (
        f"rules.json 条数 {len(rules)} != {EXPECTED_RULE_COUNT}；"
        "若确为增删规则，请同步本常量、data/README.md 与 plan/06 D19")
    # 条数与引擎注册集合同为 21 的两种口径必须对齐（集合相等 + 条数相等 ⇒ 无重复）
    assert len(set(CHECK_IDS)) == EXPECTED_RULE_COUNT


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
    """raw/ 原文与 data/README.md 台账登记的 sha256 一致（台账即溯源凭据）。

    仅源码态有意义：wheel 只装 rules.json + blocks.jsonl（data-files 白名单见
    pyproject.toml），`raw/` 原文不进装态；装态由下面的反向锚把关。
    """
    readme = (ROOT / "data" / "README.md").read_text(encoding="utf-8")
    raw_files = [p for p in (KB / "raw").glob("*.txt")]
    assert raw_files, "raw/ 缺少法规原文"
    for path in raw_files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        m = re.search(rf"{re.escape(path.name)}.*?`([0-9a-f]{{64}})`", readme, re.S)
        assert m, f"台账缺 {path.name} 的 sha256 登记"
        assert m.group(1) == digest, f"{path.name} sha256 与台账不符"


def test_source_tree_anchor_prevents_permanent_skip():
    """反向锚：防止 raw/ 台账门被"永久 skip"成假门。

    `test_raw_files_ledger_sha256_matches` 依赖 `data/knowledge/raw/` 与 `data/README.md`；
    若有人为了在装态也变绿而加 skipif，必须保证源码态仍真的跑了——这里断言源码树
    的这两样东西确实在场，否则 skip 条件本身就是缺陷。
    """
    assert (KB / "raw").is_dir(), "源码态缺 data/knowledge/raw/"
    assert list((KB / "raw").glob("*.txt")), "源码态 raw/ 为空"
    assert (ROOT / "data" / "README.md").is_file(), "源码态缺 data/README.md 台账"
    # raw/ 不进 wheel：装态应当看不到它（这里只钉声明，不真装）
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.setuptools.data-files]" in text, "缺 data-files 声明"
    block = text.split("[tool.setuptools.data-files]", 1)[1].split("\n[", 1)[0]
    assert "data/knowledge/raw" not in block, "raw/ 原文不应进 wheel（体积 + 仅源码态需要）"


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
