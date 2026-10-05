"""CLI：--version / 无参帮助 / 未交付命令退出码 2 / datagen（M1）/ run 退出码 0·1·2（M3）
/ bench e2e 转正退出码 0·1（M4）。"""
import json

import pytest

from bidchecker import __version__
from bidchecker.cli import main


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert f"bidchecker {__version__}" in capsys.readouterr().out


def test_no_args_prints_help(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "bidchecker" in out
    assert "run" in out


def test_run_missing_project_exit_2(capsys):
    assert main(["run", "no-such-project-dir"]) == 2
    assert "输入错误" in capsys.readouterr().err


def test_run_clean_project_exit_0(tmp_path, capsys):
    from pathlib import Path

    project = Path(__file__).resolve().parent.parent / "examples" / "demo-goods-2"
    out = tmp_path / "out"
    assert main(["run", str(project), "--out", str(out)]) == 0
    assert "结论 0 条" in capsys.readouterr().out
    payload = json.loads((out / "findings.json").read_text(encoding="utf-8"))
    assert payload["findings"] == []
    assert (out / "cards" / "tender.card.json").is_file()


def test_run_degraded_exit_1(tmp_path, monkeypatch, capsys):
    """存在解析失败文档：流水线完成但降级，退出码 1。"""
    from pathlib import Path

    import bidchecker.pipeline as pl

    project = Path(__file__).resolve().parent.parent / "examples" / "demo-goods-1"
    real_parse = pl.parse_bid

    def flaky(text):
        if "启明" in text:
            raise ValueError("模拟解析失败")
        return real_parse(text)

    monkeypatch.setattr(pl, "parse_bid", flaky)
    assert main(["run", str(project), "--out", str(tmp_path)]) == 1
    assert "解析失败 1 份" in capsys.readouterr().out


@pytest.mark.parametrize("cmd", [["report"], ["serve"]])
def test_future_commands_exit_2(cmd, capsys):
    assert main(cmd) == 2
    assert "尚未实现" in capsys.readouterr().err


def test_bare_bench_shows_usage_exit_2(capsys):
    """bench 子命令已转正（parse/e2e），裸 bench 打印用法提示退出码 2。"""
    assert main(["bench"]) == 2
    assert "用法" in capsys.readouterr().err


def test_bench_e2e_pass_exit_0(capsys):
    """bench e2e 转正（M4）：默认 seeds 全链基准，检出率/误报/判定准确率达标退出码 0。"""
    assert main(["bench", "e2e"]) == 0
    out = capsys.readouterr().out
    assert "检出率" in out and "误报=0" in out and "结论：PASS" in out


def test_bench_e2e_custom_seeds(capsys):
    assert main(["bench", "e2e", "--seed", "7", "--seed", "123"]) == 0
    out = capsys.readouterr().out
    assert "seeds=7,123" in out
    assert "D11" in out  # 围标对检出纳入分缺陷类型报告


def test_datagen_creates_projects(tmp_path, capsys):
    assert main(["datagen", "--seed", "7", "--out", str(tmp_path)]) == 0
    assert "已生成" in capsys.readouterr().out
    for key in ("demo-goods-1", "demo-goods-2", "demo-services-1"):
        gt = tmp_path / key / "ground_truth.json"
        assert gt.is_file(), f"缺 {key}/ground_truth.json"
        truth = json.loads(gt.read_text(encoding="utf-8"))
        assert truth["seed"] == 7
        assert (tmp_path / key / truth["tender_file"]).is_file()
