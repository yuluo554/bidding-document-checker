"""bench e2e 基准（M4）：多 seed 全链对账、门槛判定、零 API 依赖可重复。

对账口径（plan/04 §七 + datagen 真值契约）：expect_findings + also_expect
**含 D11 全集合**四元组 vs pipeline findings 非符合四元组；指标 = 检出率
（分缺陷类型）/ 误报数 / 判定准确率；门槛：检出率 ≥ 0.95、误报 0。
"""
import pytest

from bidchecker.bench import (DEFAULT_SEEDS, E2E_DETECTION_THRESHOLD,
                              format_e2e_report, run_e2e_bench)


def test_bench_e2e_full_set_multi_seed():
    """多 seed × 3 演示项目：全集合（含 D11）一致、检出率 1.0、误报 0。"""
    report = run_e2e_bench(seeds=(7, 123))
    assert report.passed
    assert report.detection_rate == 1.0
    assert report.false_positives == 0
    assert report.accuracy == 1.0
    assert all(p.full_set_equal for p in report.projects)
    assert len(report.projects) == 2 * 3
    # 干净对照：期望空集合、实际零结论
    clean = [p for p in report.projects if p.clean]
    assert clean and all(p.expected == set() and p.actual == set() for p in clean)


def test_bench_e2e_covers_all_defect_types_including_d11():
    report = run_e2e_bench(seeds=(42,))
    assert set(report.detection_by_defect) == {f"D{i}" for i in range(1, 13)}
    for hit, total in report.detection_by_defect.values():
        assert hit == total == 1


def test_bench_e2e_report_text():
    report = run_e2e_bench(seeds=(42,))
    text = format_e2e_report(report)
    assert "检出率=1.0000" in text
    assert "误报=0" in text
    assert "判定准确率=1.0000" in text
    assert "结论：PASS" in text
    assert "D11" in text  # 分缺陷类型报告包含围标对检出


def test_bench_e2e_default_seeds_gate():
    """默认 seeds（1/7/42/123/2026）门槛判定与模块阈值一致。"""
    report = run_e2e_bench()
    assert report.seeds == DEFAULT_SEEDS
    assert report.threshold == E2E_DETECTION_THRESHOLD
    assert report.passed


def test_bench_e2e_is_deterministic():
    r1 = run_e2e_bench(seeds=(42,))
    r2 = run_e2e_bench(seeds=(42,))
    assert [(p.seed, p.project_key, sorted(p.actual)) for p in r1.projects] == \
           [(p.seed, p.project_key, sorted(p.actual)) for p in r2.projects]
    assert format_e2e_report(r1) == format_e2e_report(r2)


@pytest.mark.parametrize("seeds", [(1,), (2026,)])
def test_bench_e2e_more_seeds_no_regression(seeds):
    """多 seed 回归不挑 seed：任意单 seed 全集合一致（D11 围标对/抽取序无关）。"""
    report = run_e2e_bench(seeds=seeds)
    assert report.passed
    assert all(p.full_set_equal for p in report.projects)
