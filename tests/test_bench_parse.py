"""bench parse 基准测试：多 seed 全量对账 F1 = 1.0 + CLI 接线与门槛判定。"""
import pytest

from bidchecker.bench import DEFAULT_SEEDS, F1_THRESHOLD, format_report, run_parse_bench
from bidchecker.cli import main

# 每 seed：3 个项目 = 3 份招标 + (4+3+3) 份投标
DOCS_PER_SEED = 3 + 10


def test_bench_parse_default_seeds_perfect():
    report = run_parse_bench()
    assert len(report.docs) == len(DEFAULT_SEEDS) * DOCS_PER_SEED
    bad = [d for d in report.docs if d.mismatches or d.evidence_violations]
    detail = "\n".join(f"{d.doc_id}: 失配={d.mismatches} 证据违例={d.evidence_violations}"
                       for d in bad[:8])
    assert not bad, f"存在字段级失配/证据违例：\n{detail}"
    assert report.f1 == 1.0, "确定性合成体例上的解析基准应满分"
    assert report.precision == 1.0 and report.recall == 1.0
    assert report.passed
    assert report.categories, "应有按字段类别的分解"


def test_bench_parse_single_seed():
    report = run_parse_bench(seeds=(42,))
    assert len(report.docs) == DOCS_PER_SEED
    assert report.f1 == 1.0
    text = format_report(report)
    assert "PASS" in text and "F1=1.0000" in text


def test_bench_report_lists_mismatches_when_injected():
    """守门演示：阈值上调到不可达（>1）时 FAIL，报告仍完整（不放宽门槛的判定路径）。"""
    report = run_parse_bench(seeds=(42,), threshold=1.1)
    assert not report.passed
    text = format_report(report)
    assert "FAIL" in text


def test_cli_bench_parse_pass(capsys):
    assert main(["bench", "parse", "--seed", "42"]) == 0
    out = capsys.readouterr().out
    assert "F1=" in out and "PASS" in out
    assert "按字段类别" in out


def test_cli_bench_parse_threshold_fail_exit_1(capsys):
    assert main(["bench", "parse", "--seed", "42", "--threshold", "1.1"]) == 1
    assert "FAIL" in capsys.readouterr().out


# bench e2e 转正后的 CLI 锁定移至 tests/test_cli.py（裸 bench 用法提示 / e2e 退出码 0·1），
# e2e 基准本体见 tests/test_bench_e2e.py。
