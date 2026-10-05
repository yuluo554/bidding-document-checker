"""bidchecker 命令行入口。

命令按里程碑分阶段交付（plan/05-数据计划与里程碑.md）：未交付命令打印指向计划
文档的提示并返回退出码 2（与参数错误一致），不崩溃。
"""
import argparse
import sys

from bidchecker import __version__

_PLAN_URL = "plan/05-数据计划与里程碑.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bidchecker",
        description="招投标文件智能评审与合规校核系统（辅助评审定位，非评标决策工具）",
    )
    parser.add_argument("--version", action="version", version=f"bidchecker {__version__}")
    sub = parser.add_subparsers(dest="command")
    p_run = sub.add_parser("run", help="端到端评审流水线：解析 → 校核 → findings")
    p_run.add_argument("project", help="项目输入目录（招标文件 + 投标文件包）")
    sub.add_parser("datagen", help="合成招投标文件生成器（带真值/缺陷注入）")
    sub.add_parser("bench", help="内置基准：解析 F1 / 端到端校核（零 API 依赖）")
    sub.add_parser("report", help="生成 docx 评审报告")
    sub.add_parser("serve", help="启动 Web 面板")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        print(f"尚未实现：解析层计划于 M2 交付（见 {_PLAN_URL}）", file=sys.stderr)
        return 2
    if args.command in ("datagen", "bench", "report", "serve"):
        print(f"尚未实现：该命令按里程碑交付（见 {_PLAN_URL}）", file=sys.stderr)
        return 2
    parser.print_help()
    return 0
