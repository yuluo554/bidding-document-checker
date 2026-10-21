"""法规知识库（三层：原文 → 条文块 → 机器可读规则表，plan/04 §四）。M3 交付。

入库纪律：每条挂出处（规范号+条号+渠道+status）；无出处的值不得以确定语气落库；
查不到显式标"待核对"。检索用纯 Python 余弦，不引向量库（M3 先交付加载与依据解析，
检索 M4/M5 随 LLM 兜底与报告层交付）。

目录布局（plan/04 §四）::

    data/knowledge/
    ├── raw/            # 法规原文 txt（来源台账：URL+获取日期+sha256，见 data/README.md）
    ├── blocks.jsonl    # 条文块：{law, article_no, text, source_url, status: 已核对|待核对}
    └── rules.json      # CheckRule[]：id/name/rule_type/severity/basis/advice/only_if/params

两种定位口径（M7 起）：
- 源码态：从 start（默认 CWD）与包位置逐级上溯，找 `<任意祖先>/data/knowledge`；
- 装态（pip 安装的 wheel）：`[tool.setuptools.data-files]` 把同一份数据装到
  `<prefix>/share/bidchecker/knowledge`，由 `_installed_candidates()` 兜底命中。
两种口径共用同一判定：**目录下同时存在 rules.json 与 blocks.jsonl 才算找到**。

依据关联（Finding.basis 100% 可解析的实现基础）：
- 法规引用形如 "《法规名》第X条" → (law, article_no) 在 blocks.jsonl 中逐字对应；
- TenderCard 条款 id 形如 "Q3"/"S1"/"R2" → 在参数卡 qualifications/star_clauses/
  rejection_clauses 的 item_id 中出现。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

BLOCKS_FILE = "blocks.jsonl"
RULES_FILE = "rules.json"
STATUS_VERIFIED = "已核对"
STATUS_PENDING = "待核对"

# 装态（wheel）数据目录：pyproject 的 [tool.setuptools.data-files] 把 data/knowledge/*
# 装到 <prefix>/share/bidchecker/knowledge（rules.json + blocks.jsonl，不含 raw/ 原文）。
SHARE_SUBDIR = ("share", "bidchecker", "knowledge")

_BASIS_LAW_RE = re.compile(r"^《([^《》]+)》(第[0-9一二三四五六七八九十百]+条)$")
_BASIS_CLAUSE_RE = re.compile(r"^[QSR][0-9]+$")
_CHINESE_NUM = "一二三四五六七八九十百"


def _is_knowledge_dir(path: Path) -> bool:
    """判定标准：目录下同时存在 rules.json 与 blocks.jsonl（源码态/装态共用）。"""
    return (path / RULES_FILE).is_file() and (path / BLOCKS_FILE).is_file()


def _installed_candidates() -> List[Path]:
    """装态候选：<prefix>/share/bidchecker/knowledge（sys.prefix / sys.base_prefix / 包上溯）。

    pip 把 wheel 装进 venv 时 sys.prefix 指向 venv；`--target`/`--prefix` 或用户级安装
    则要沿包位置逐级上溯才能找到真正的 prefix——因此三路全部枚举，顺序确定。
    """
    roots: List[Path] = []
    for raw in (getattr(sys, "prefix", None), getattr(sys, "base_prefix", None)):
        if raw:
            roots.append(Path(raw))
    roots.extend(Path(__file__).resolve().parents)
    out: List[Path] = []
    for root in roots:
        cand = root.joinpath(*SHARE_SUBDIR)
        if cand not in out:
            out.append(cand)
    return out


def find_knowledge_dir(start: Union[str, Path, None] = None) -> Optional[Path]:
    """定位 data/knowledge 目录：start（默认 CWD）与包安装位置逐级上溯，再查装态 share。

    判定标准 = 目录下同时存在 rules.json 与 blocks.jsonl；找不到返回 None
    （引擎在无知识库时仍可运行，缺依据会由 pipeline 打 stderr 警告，见 DEC3）。
    """
    bases: List[Path] = []
    if start is not None:
        bases.append(Path(start))
    bases.append(Path.cwd())
    bases.append(Path(__file__).resolve())
    for base in bases:
        for cand in (base, *base.parents):
            kb = cand / "data" / "knowledge"
            if _is_knowledge_dir(kb):
                return kb
    for kb in _installed_candidates():
        if _is_knowledge_dir(kb):
            return kb
    return None


def load_blocks(kb_dir: Union[str, Path, None] = None) -> List[Dict[str, Any]]:
    """blocks.jsonl → 条文块 dict 列表（逐行 JSON，空行跳过）。"""
    path = _resolve(kb_dir, BLOCKS_FILE)
    if path is None:
        return []
    blocks: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            blocks.append(json.loads(line))
    return blocks


def load_rules(kb_dir: Union[str, Path, None] = None) -> List[Dict[str, Any]]:
    """rules.json → CheckRule dict 列表。

    找不到知识库时返回 `[]`（plan/06 D20：引擎在无知识库时仍可运行）。**静默不再允许**：
    调用方需用 `knowledge_status()` 判断并给出提示（DEC3=A：可运行 + 告警）。
    """
    path = _resolve(kb_dir, RULES_FILE)
    if path is None:
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def knowledge_status(kb_dir: Union[str, Path, None] = None) -> Dict[str, Any]:
    """知识库可用性探针：{"available": bool, "path": str|None, "reason": str}。

    供 pipeline / CLI 在缺依据时给出可见提示（不改变退出码语义）。
    path 指向**知识库目录**（不是某个文件）。
    """
    kb = Path(kb_dir) if kb_dir is not None else find_knowledge_dir()
    if kb is None:
        return {"available": False, "path": None,
                "reason": f"未找到知识库目录（需同时含 {RULES_FILE} 与 {BLOCKS_FILE}）："
                          f"已查找 CWD 上溯、包位置上溯与 "
                          f"{'/'.join(SHARE_SUBDIR)}"}
    missing = [name for name in (RULES_FILE, BLOCKS_FILE) if not (kb / name).is_file()]
    if missing:
        return {"available": False, "path": str(kb),
                "reason": f"知识库目录 {kb} 缺少 {'、'.join(missing)}"}
    try:
        rules = json.loads((kb / RULES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"available": False, "path": str(kb),
                "reason": f"知识库目录 {kb} 的 {RULES_FILE} 无法解析：{exc}"}
    if not isinstance(rules, list) or not rules:
        return {"available": False, "path": str(kb),
                "reason": f"知识库目录 {kb} 的 {RULES_FILE} 为空，规则映射将全空"}
    return {"available": True, "path": str(kb), "reason": ""}


def _resolve(kb_dir: Union[str, Path, None], filename: str) -> Optional[Path]:
    if kb_dir is not None:
        return Path(kb_dir) / filename
    kb = find_knowledge_dir()
    return (kb / filename) if kb is not None else None


# ---------------------------------------------------------------- 依据解析
def basis_kind(entry: str) -> Tuple[str, ...]:
    """basis 条目分类：("law", 法规名, 条号) / ("clause", 条款id) / ("other", 原文)。"""
    if not isinstance(entry, str):
        return ("other", str(entry))
    m = _BASIS_LAW_RE.match(entry.strip())
    if m:
        return ("law", m.group(1), m.group(2))
    if _BASIS_CLAUSE_RE.match(entry.strip()):
        return ("clause", entry.strip())
    return ("other", entry)


def law_block_key(law: str, article_no: str) -> str:
    """法规引用的规范书写（Finding.basis 中法规条目的唯一合法形态）。"""
    return f"《{law}》{article_no}"


def basis_resolves(entry: str, blocks: List[Dict[str, Any]],
                   tender: Any) -> bool:
    """单条 basis 是否可解析：法规引用命中条文块，或条款 id 存在于 TenderCard。"""
    kind = basis_kind(entry)
    if kind[0] == "law":
        _law, name, article = kind
        return any(b.get("law") == name and b.get("article_no") == article
                   for b in blocks)
    if kind[0] == "clause":
        item_id = kind[1]
        quals = getattr(tender, "qualifications", ()) or ()
        stars = getattr(tender, "star_clauses", ()) or ()
        rejects = getattr(tender, "rejection_clauses", ()) or ()
        return any(q.item_id == item_id for q in quals) \
            or any(c.item_id == item_id for c in stars) \
            or any(r.item_id == item_id for r in rejects)
    return False


__all__ = [
    "BLOCKS_FILE", "RULES_FILE", "STATUS_VERIFIED", "STATUS_PENDING", "SHARE_SUBDIR",
    "find_knowledge_dir", "knowledge_status", "load_blocks", "load_rules",
    "basis_kind", "law_block_key", "basis_resolves",
]
