"""bidchecker 命令行入口。

命令按里程碑分阶段交付（plan/05-数据计划与里程碑.md）：未交付命令打印指向计划
文档的提示并返回退出码 2（与参数错误一致），不崩溃。

退出码语义（M3 定稿，锁进 tests/test_cli.py）：
- datagen / bench parse / --version / 无参帮助：0 成功（bench parse 门槛不过 = 1）；
- run：0 = 全部文档解析并校核完成；1 = 完成但存在解析失败文档（降级）；
  2 = 输入不可用（目录/文件缺失）或未交付命令；
- bench e2e / report / serve：未交付 = 2（指向 plan/05）。
"""
import argparse
import sys
from pathlib import Path

from bidchecker import __version__

_PLAN_URL = "plan/05-数据计划与里程碑.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidchecker",
        description="招投标文件智能评审与合规校核系统（辅助评审定位，非评标决策工具）",
    )
    parser.add_argument("--version", action="version", version=f"bidchecker {__version__}")
    sub = parser.add_subparsers(dest="command")
    p_run = sub.add_parser("run", help="端到端评审流水线：解析 → 校核 → findings（M3）")
    p_run.add_argument("project", help="项目输入目录（招标文件 + 投标文件包）")
    p_run.add_argument("--out", default="output",
                       help="产物输出目录（默认 ./output：findings.json + cards/）")
    p_datagen = sub.add_parser("datagen", help="合成招投标文件生成器（带真值/缺陷注入，M1）")
    p_datagen.add_argument("--seed", type=int, default=42, help="确定性随机种子（默认 42）")
    p_datagen.add_argument("--out", default="examples", help="输出根目录（默认 examples）")
    p_bench = sub.add_parser("bench", help="内置基准：解析 F1（M2）/ 端到端校核（M4）")
    bench_sub = p_bench.add_subparsers(dest="bench_command")
    p_bp = bench_sub.add_parser("parse", help="解析层基准：字段级 P/R/F1（对账生成器真值）")
    p_bp.add_argument("--seed", type=int, action="append", dest="seeds",
                      help="回归种子，可重复传入（默认 1,7,42,123,2026）")
    p_bp.add_argument("--threshold", type=float, default=None,
                      help="总体 F1 门槛（默认 0.95，不放宽）")
    p_bp.add_argument("--verbose", action="store_true", help="列出全部字段级失配明细")
    bench_sub.add_parser("e2e", help="端到端基准：检出率/误报率/判定准确率（M4 交付）")
    sub.add_parser("report", help="生成 docx 评审报告")
    sub.add_parser("serve", help="启动 Web 面板")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "datagen":
        from bidchecker.datagen import run_datagen

        run_datagen(seed=args.seed, out_root=args.out)
        return 0
    if args.command == "run":
        from bidchecker import pipeline as pipeline_mod

        try:
            result = pipeline_mod.run_pipeline(args.project, out_dir=args.out)
        except FileNotFoundError as exc:
            print(f"输入错误：{exc}", file=sys.stderr)
            return 2
        print(result.format_summary())
        print(f"产物：{Path(args.out) / 'findings.json'}（卡片 {Path(args.out) / 'cards'}）")
        return 0 if not result.failed else 1
    if args.command == "bench":
        if args.bench_command == "parse":
            from bidchecker.bench import F1_THRESHOLD, run_bench_parse

            seeds = tuple(args.seeds) if args.seeds else None
            threshold = args.threshold if args.threshold is not None else F1_THRESHOLD
            _report, text = run_bench_parse(seeds=seeds, threshold=threshold,
                                            verbose=args.verbose)
            print(text)
            return 0 if _report.passed else 1
        if args.bench_command == "e2e":
            print(f"尚未实现：bench e2e 计划于 M4 交付（见 {_PLAN_URL}）", file=sys.stderr)
            return 2
        print(f"用法：bidchecker bench parse|e2e（e2e 尚未实现，见 {_PLAN_URL}）",
              file=sys.stderr)
        return 2
    if args.command in ("report", "serve"):
        print(f"尚未实现：该命令按里程碑交付（见 {_PLAN_URL}）", file=sys.stderr)
        return 2
    parser.print_help()
    return 0
