"""知识库检索（plan/04 §四）：纯 Python TF 余弦 top_k，不引向量库。M4 交付。

- 分词：拉丁词（小写化）+ 中文二字组（bigram）——无需分词器、零依赖；
- 相似度：TF 向量余弦（0~1）；查询与条文块同构处理；
- 排序确定性：按 (-score, law, article_no)，杜绝 set 迭代序/哈希序（DetRng 纪律同源）；
- 用途：报告层引用原文锚点（M5）、LLM 兜底提供条文上下文（可选通路）。

检索范围 = blocks.jsonl 条文块（load_blocks）；传入 blocks 参数可复用已加载列表。
"""
from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from bidchecker.knowledge import load_blocks

_TOKEN_LATIN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_TOKEN_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def tokenize(text: str) -> List[str]:
    """条文/查询文本 → 词元序列：拉丁词（小写）+ 中文相邻二字组。"""
    tokens = [t.lower() for t in _TOKEN_LATIN_RE.findall(text or "")]
    cjk = _TOKEN_CJK_RE.findall(text or "")
    tokens += [a + b for a, b in zip(cjk, cjk[1:])]
    return tokens


def _tf(tokens: Sequence[str]) -> Dict[str, float]:
    tf: Dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0.0) + 1.0
    return tf


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def search(query: str, *, blocks: Optional[List[Dict[str, Any]]] = None,
           kb_dir: Union[str, None] = None, top_k: int = 5) -> List[Tuple[float, Dict[str, Any]]]:
    """查询 → [(score, 条文块)]（score 降序、并列按 law/article_no 升序）。

    blocks 缺省时从 data/knowledge/blocks.jsonl 加载；kb_dir 显式指定知识库目录。
    """
    if blocks is None:
        blocks = load_blocks(kb_dir)
    qv = _tf(tokenize(query))
    scored = [(_cosine(qv, _tf(tokenize(str(b.get("text", ""))))), b) for b in blocks]
    scored.sort(key=lambda t: (-t[0], str(t[1].get("law", "")),
                               str(t[1].get("article_no", ""))))
    return [(round(score, 6), b) for score, b in scored[:max(0, top_k)]]


__all__ = ["tokenize", "search"]
