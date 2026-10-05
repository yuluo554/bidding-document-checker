"""围标串标文本特征（M4）：双信号交叉验证、排除对照、确定性、依据关联。

口径（collusion/__init__ 模块注释）：同分钟编制时间戳 + 对照独有共享长句同时命中
才产出 collusion·待人工确认·mid；仅文本特征，不出定性结论。
"""
import json
from pathlib import Path

from bidchecker.collusion import CHECK_ID, SENTENCE_MIN_LEN, detect_collusion
from bidchecker.knowledge import basis_resolves, load_blocks
from bidchecker.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"

TEMPLATE_SENTENCE = ("根据我公司多年同类项目实施经验并结合本项目实际特点，我方将严格按照"
                     "招标文件要求组织实施并确保验收合格。")


def _bid_text(bidder: str, ts: str, sentence: str = "") -> str:
    lines = [
        "# 演示项目投标文件", "", "项目编号：ZB-2026-0001", f"投标人：{bidder}", "",
        "## 第四章 技术方案", "", "4.2.1 我方将成立专项项目组，按招标文件要求组织实施。",
    ]
    if sentence:
        lines += [sentence]
    lines += ["", "## 第六章 承诺函", f"编制完成时间：{ts}", ""]
    return "\n".join(lines)


def test_both_signals_required_and_detected():
    """同分钟时间戳 + 对照独有共享长句同时命中 → 一条 待人工确认·mid。"""
    texts = {
        "bids/乙公司.md": _bid_text("乙公司", "2026-10-15 10:37", TEMPLATE_SENTENCE),
        "bids/甲公司.md": _bid_text("甲公司", "2026-10-15 10:37", TEMPLATE_SENTENCE),
        "bids/丙公司.md": _bid_text("丙公司", "2026-10-15 11:20"),
    }
    out = detect_collusion(texts, exclude_text="招标文件不含该句")
    assert len(out) == 1
    pf = out[0]
    # target 按文件名排序规范化（输入序是 乙/甲/丙；码点序 乙 < 甲）
    assert pf.target == "|".join(sorted(["bids/甲公司.md", "bids/乙公司.md"]))
    assert pf.target == "bids/乙公司.md|bids/甲公司.md"
    f = pf.finding
    assert f.check_id == CHECK_ID and f.status == "待人工确认" and f.risk_level == "mid"
    assert "编制完成时间相同" in f.message and f"仅此两份共享" in f.message
    assert "非定性结论" in f.message
    quotes = [e.quote for e in f.evidence]
    assert f"编制完成时间：2026-10-15 10:37" in quotes
    assert TEMPLATE_SENTENCE in quotes
    for q in quotes:  # 证据 quote 必须是两份投标原文子串（硬校验口径）
        assert q in texts["bids/甲公司.md"] and q in texts["bids/乙公司.md"]


def test_basis_resolves_to_verified_blocks():
    texts = {
        "bids/甲.md": _bid_text("甲", "2026-10-15 10:37", TEMPLATE_SENTENCE),
        "bids/乙.md": _bid_text("乙", "2026-10-15 10:37", TEMPLATE_SENTENCE),
        "bids/丙.md": _bid_text("丙", "2026-10-15 11:20"),
    }
    blocks = load_blocks()
    for pf in detect_collusion(texts):
        for entry in pf.finding.basis:
            assert basis_resolves(entry, blocks, None), f"依据无法解析: {entry}"


def test_single_signal_ts_only_is_silent():
    texts = {
        "bids/甲.md": _bid_text("甲", "2026-10-15 10:37"),
        "bids/乙.md": _bid_text("乙", "2026-10-15 10:37"),
        "bids/丙.md": _bid_text("丙", "2026-10-15 11:20"),
    }
    assert detect_collusion(texts) == []


def test_single_signal_sentence_only_is_silent():
    texts = {
        "bids/甲.md": _bid_text("甲", "2026-10-15 10:37", TEMPLATE_SENTENCE),
        "bids/乙.md": _bid_text("乙", "2026-10-15 12:05", TEMPLATE_SENTENCE),
        "bids/丙.md": _bid_text("丙", "2026-10-15 11:20"),
    }
    assert detect_collusion(texts) == []


def test_shared_line_in_other_bid_or_tender_excluded():
    """共享行被第三份投标共有、或出现在招标文本 → 不算"对照独有"，无结论。"""
    shared = TEMPLATE_SENTENCE
    texts_all = {
        "bids/甲.md": _bid_text("甲", "2026-10-15 10:37", shared),
        "bids/乙.md": _bid_text("乙", "2026-10-15 10:37", shared),
        "bids/丙.md": _bid_text("丙", "2026-10-15 10:37", shared),
    }
    assert detect_collusion(texts_all) == []
    texts_tender = {
        "bids/甲.md": _bid_text("甲", "2026-10-15 10:37", shared),
        "bids/乙.md": _bid_text("乙", "2026-10-15 10:37", shared),
        "bids/丙.md": _bid_text("丙", "2026-10-15 11:20"),
    }
    assert detect_collusion(texts_tender, exclude_text=shared) == []


def test_fewer_than_three_bids_silent():
    """投标 < 3 份：无法建立独有性对照，整体不产出（宁缺勿错）。"""
    texts = {
        "bids/甲.md": _bid_text("甲", "2026-10-15 10:37", TEMPLATE_SENTENCE),
        "bids/乙.md": _bid_text("乙", "2026-10-15 10:37", TEMPLATE_SENTENCE),
    }
    assert detect_collusion(texts) == []


def test_short_shared_line_below_threshold_silent():
    short = "本项目已经具备招标条件并开始实施"  # 15 字 < SENTENCE_MIN_LEN
    assert len(short) < SENTENCE_MIN_LEN
    texts = {
        "bids/甲.md": _bid_text("甲", "2026-10-15 10:37", short),
        "bids/乙.md": _bid_text("乙", "2026-10-15 10:37", short),
        "bids/丙.md": _bid_text("丙", "2026-10-15 11:20"),
    }
    assert detect_collusion(texts) == []


def test_gate_only_if_blocks_when_keywords_absent():
    gated = [{"id": CHECK_ID, "rule_type": "collusion",
              "only_if": {"keywords": ["货物类目专属"]}}]
    texts = {
        "bids/甲.md": _bid_text("甲", "2026-10-15 10:37", TEMPLATE_SENTENCE),
        "bids/乙.md": _bid_text("乙", "2026-10-15 10:37", TEMPLATE_SENTENCE),
        "bids/丙.md": _bid_text("丙", "2026-10-15 11:20"),
    }
    assert detect_collusion(texts, rules=gated) == []
    assert detect_collusion(texts, rules=gated + []) is not None
    texts_goods = {k: "本项目为货物类目专属采购\n" + v for k, v in texts.items()}
    assert len(detect_collusion(texts_goods, rules=gated)) == 1


# ---------------------------------------------------------------- pipeline 集成
def test_examples_demo_goods_1_collusion_pair():
    """examples 集成：D11 对按真值 target 检出，证据 quote ⊂ 对应投标原文。"""
    result = run_pipeline(EXAMPLES / "demo-goods-1")
    gt = json.loads((EXAMPLES / "demo-goods-1" / "ground_truth.json").read_text(encoding="utf-8"))
    truth_pairs = {(row["target"]) for row in gt["expect_findings"]
                   if row["rule_type"] == "collusion"}
    got_pairs = {pf.target for pf in result.collusion}
    assert got_pairs == truth_pairs
    bid_texts = {b.file: (EXAMPLES / "demo-goods-1" / b.file).read_text(encoding="utf-8")
                 for b in result.bids}
    for pf in result.collusion:
        a, b = pf.target.split("|")
        for e in pf.finding.evidence:
            assert e.quote in bid_texts[a] and e.quote in bid_texts[b]
    # finding_dicts 携带 rule_type 与围标对 target（serialization 口径）
    dicts = [d for d in result.finding_dicts() if d["check_id"] == CHECK_ID]
    assert len(dicts) == 1 and dicts[0]["rule_type"] == "collusion"
    assert dicts[0]["target"] in got_pairs


def test_examples_clean_project_no_collusion():
    result = run_pipeline(EXAMPLES / "demo-goods-2")
    assert result.collusion == []
    assert result.summary()["total"] == 0
