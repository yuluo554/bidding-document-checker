"""项目包落盘与演示集注册表：渲染 → ground_truth.json → 目录写入。

落盘纪律（位级一致守门的前提）：
- 一律 write_bytes（UTF-8 无 BOM，内容仅 \n 换行）——杜绝平台换行翻译与 BOM 漂移；
- 文件序/键序固定：bids 按构建序（=投标人抽取序），JSON 键按构造序写入；
- 内容零时钟：文档与真值不含"生成时刻"，seed 是唯一变化源。

e2e 对账（M4 bench）读取的 expect_findings/also_expect 结构见 datagen/__init__ 契约注释；
解析侧真值（M2 bench parse）不经 JSON，用 build_project 返回的参数卡逐字段比对。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from bidchecker.datagen.build import build_project
from bidchecker.datagen.spec import ProjectBundle
from bidchecker.datagen.templates import render_bid, render_tender


@dataclass(frozen=True)
class DemoSpec:
    """演示项目配置：key/类目/是否干净对照/投标份数/缺陷注入计划（位置串, 缺陷id）。"""

    key: str
    category: str
    clean: bool
    n_bids: int
    plan: Tuple[Tuple[str, str], ...]


# 三个演示项目：货物×2（缺陷注入 + 干净对照）+ 服务×1（缺陷注入），
# D1–D12 全覆盖（M1 DoD）；计划全部通过 defects.validate_plan 静态校验（互斥+四元组唯一）。
DEMO_PROJECTS: Tuple[DemoSpec, ...] = (
    DemoSpec(
        key="demo-goods-1", category="goods", clean=False, n_bids=4,
        plan=(
            ("tender", "D10"),
            ("bid:0", "D4"), ("bid:1", "D2"), ("bid:2", "D1"), ("bid:2", "D6"),
            ("bid:3", "D3"), ("pair:0-1", "D11"),
        ),
    ),
    DemoSpec(key="demo-goods-2", category="goods", clean=True, n_bids=3, plan=()),
    DemoSpec(
        key="demo-services-1", category="services", clean=False, n_bids=3,
        plan=(
            ("bid:0", "D7"), ("bid:0", "D8"),
            ("bid:1", "D5"), ("bid:1", "D9"),
            ("bid:2", "D12"),
        ),
    ),
)


def build_ground_truth(bundle: ProjectBundle) -> Dict[str, Any]:
    """真值 JSON：主期望（main）入 expect_findings，隐含结论（also）入 also_expect。"""
    main = [f.to_truth_dict() for f in bundle.findings if f.kind == "main"]
    also = [f.to_truth_dict() for f in bundle.findings if f.kind == "also"]
    return {
        "schema_version": "1",
        "project_id": bundle.key,
        "category": bundle.category,
        "clean": bundle.clean,
        "seed": bundle.seed,
        "tender_file": "tender.md",
        "bid_files": [f"bids/{bb.bidder}.md" for bb in bundle.bids],
        "expect_findings": main,
        "also_expect": also,
    }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))  # LF 保证：内容由 "\n" 连接，无 \r、无 BOM


def generate_project_package(out_root: Path, seed: int, spec: DemoSpec) -> Path:
    """生成单个项目包目录（tender.md + bids/*.md + ground_truth.json），返回目录路径。"""
    bundle = build_project(seed, spec.key, spec.category, spec.clean, spec.plan, spec.n_bids)
    proj_dir = Path(out_root) / spec.key
    _write_text(proj_dir / "tender.md", render_tender(bundle))
    for bb in bundle.bids:
        _write_text(proj_dir / "bids" / f"{bb.bidder}.md", render_bid(bundle, bb))
    truth = json.dumps(build_ground_truth(bundle), ensure_ascii=False, indent=2) + "\n"
    _write_text(proj_dir / "ground_truth.json", truth)
    return proj_dir


def run_datagen(seed: int = 42, out_root: str = "examples") -> List[str]:
    """生成全部演示项目；返回落盘目录列表（供 CLI 汇报与测试断言）。"""
    out = Path(out_root)
    written: List[str] = []
    for spec in DEMO_PROJECTS:
        proj_dir = generate_project_package(out, seed, spec)
        written.append(str(proj_dir))
        print(f"已生成 {proj_dir}")
    return written
