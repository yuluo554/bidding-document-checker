"""围标串标文本特征分析（P1 加分项，plan/04 §五）。M4 交付：按对检出 + pipeline 接入。

口径（HANDOFF-M4 + datagen 真值契约 D11）：
- 按对读两份投标文本，检出**文本特征异常一致**的两个信号，**双信号交叉验证**：
  1) 同分钟编制时间戳：`编制完成时间：` 行取值完全相同；
  2) 共享模板句：两份投标存在长度 ≥ SENTENCE_MIN_LEN 的相同行，且该行不出现在
     招标文本、也不出现在项目内其余投标文本中（"对照独有"——固定体例行全体投标
     共有，天然被排除）；
- **两信号同时命中才出结论**（HANDOFF-M4 围标签名 = 模板句相同 + 编制时间戳
  同分钟）：单信号污染路径实测存在——干净投标的响应行/承诺行在第三份投标被
  注入偏离后会变成"对照独有共享行"，且同分钟编制也可能巧合，单一信号不足以
  构成"异常一致"提示（宁缺勿错）。投标 < 3 份时无法建立独有性对照，整体不产出；
- 命中 → 出一条 collusion·待人工确认·mid，target = 围标对
  "bids/A.md|bids/B.md"（按文件名排序规范化，与真值 pair_target 同序）；
- **仅文本特征、仅辅助提示**：按实施条例第 39/40 条 + 87号令第 36/37 条所列情形提示
  （条文均官方逐字核验入库），**不出"围标"定性结论**（D3 合规红线），结论级别仅
  待人工确认；LLM 与人工都不通过本模块改变 status；
- 确定性：文件序 sorted、结果序 = 对的枚举序、无 set 迭代依赖、零时钟零随机。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Tuple

from bidchecker.knowledge import load_rules
from bidchecker.rules.gates import rule_applies
from bidchecker.schema import Evidence, Finding, STATUS_MANUAL

CHECK_ID = "CHK-CL-01"  # 围标文本特征提示（rules.json 注册，rule_type=collusion）

LAW_IMPL_REG = "招标投标法实施条例"
LAW_87 = "政府采购货物和服务招标投标管理办法"
CITE_IMPL_39 = "《%s》第三十九条" % LAW_IMPL_REG
CITE_IMPL_40 = "《%s》第四十条" % LAW_IMPL_REG
CITE_87_FAIR = "《%s》第三十六条" % LAW_87
CITE_87_COLLUDE = "《%s》第三十七条" % LAW_87

BASIS_COLLUSION = (CITE_IMPL_39, CITE_IMPL_40, CITE_87_FAIR, CITE_87_COLLUDE)

SENTENCE_MIN_LEN = 24  # 共享模板句判定：对照独有相同行的最小长度（字）
_TS_LINE_RE = re.compile(r"^编制完成时间：(.+)$", re.M)


@dataclass
class PairFinding:
    """围标特征按对检出：target=围标对（排序规范化的 "bids/A.md|bids/B.md"）。"""

    target: str
    finding: Finding


def _compile_ts(text: str) -> Optional[str]:
    """投标文本 → 编制完成时间取值（取首处；无该行 → None）。"""
    m = _TS_LINE_RE.search(text or "")
    return m.group(1).strip() if m else None


def _exclusive_shared_line(text_a: str, text_b: str, others: List[str],
                           exclude_text: str) -> Optional[str]:
    """两份投标间"对照独有"的相同行：长度达标、不在招标文本、不在其余投标文本。

    行级精确相同（生成体例中模板句为单行整行）；返回最长一条（并列取字典序，
    保证确定性），无则 None。
    """
    common = set(text_a.splitlines()) & set(text_b.splitlines())
    candidates = []
    for line in common:
        stripped = line.strip()
        if len(stripped) < SENTENCE_MIN_LEN:
            continue
        if any(stripped in other for other in others):
            continue
        if stripped in exclude_text:
            continue
        candidates.append(stripped)
    if not candidates:
        return None
    return sorted(candidates, key=lambda s: (-len(s), s))[0]


def detect_collusion(bid_texts: Mapping[str, str], *, exclude_text: str = "",
                     rules: Optional[List[Dict[str, Any]]] = None) -> List[PairFinding]:
    """投标文本表（{相对路径: 原文}）→ 围标特征按对检出结论（确定性顺序）。

    exclude_text = 招标文件原文（共享模板句的排除对照）。规则未注册时恒激活；
    带 only_if 的注册规则以全部投标文本拼接为门控文本（与引擎分派纪律一致）。
    """
    files = sorted(bid_texts)
    rule = None
    for r in (rules if rules is not None else load_rules()):
        if isinstance(r, dict) and r.get("id") == CHECK_ID:
            rule = r
            break
    if rule is not None and not rule_applies(rule, "\n".join(bid_texts[f] for f in files)):
        return []

    out: List[PairFinding] = []
    for i in range(len(files)):
        for j in range(i + 1, len(files)):
            fa, fb = files[i], files[j]
            ta, tb = bid_texts[fa], bid_texts[fb]
            others = [bid_texts[f] for f in files if f not in (fa, fb)]
            # 双信号交叉验证（HANDOFF-M4 签名 = 模板句相同 + 编制时间戳同分钟）：
            # 单信号污染路径实测存在——干净投标的响应行/承诺行在第三份投标被注入
            # 偏离后会变成"对照独有共享行"，同分钟编制也可能巧合；两信号同时命中
            # 才构成"异常一致"提示（宁缺勿错）。
            ts_a, ts_b = _compile_ts(ta), _compile_ts(tb)
            shared = _exclusive_shared_line(ta, tb, others, exclude_text) \
                if len(files) >= 3 else None  # < 3 份无法建立独有性对照 → 不产出
            if ts_a is None or ts_a != ts_b or shared is None:
                continue
            signals = [f"编制完成时间相同（{ts_a}）",
                       f"存在仅此两份共享的相同长句（{len(shared)}字）"]
            evidence = [Evidence(quote=f"编制完成时间：{ts_a}"),
                        Evidence(quote=shared)]
            name_a, name_b = fa.rsplit("/", 1)[-1][:-3], fb.rsplit("/", 1)[-1][:-3]
            message = (
                f"投标人{name_a}与投标人{name_b}的投标文件存在异常一致文本特征："
                + "；".join(signals)
                + "。属《招标投标法实施条例》第三十九条/第四十条、"
                "《政府采购货物和服务招标投标管理办法》第三十六条/第三十七条所列"
                "串通投标情形的文本特征提示，提请人工核查（辅助提示，非定性结论）"
            )
            out.append(PairFinding(
                target=f"{fa}|{fb}",
                finding=Finding(check_id=CHECK_ID, status=STATUS_MANUAL,
                                risk_level="mid", message=message,
                                basis=list(BASIS_COLLUSION), evidence=evidence),
            ))
    return out


__all__ = ["CHECK_ID", "BASIS_COLLUSION", "SENTENCE_MIN_LEN", "PairFinding",
           "detect_collusion"]
