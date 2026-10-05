"""CLI：--version / 无参帮助 / 未交付命令退出码 2 / datagen 交付（M1）。"""
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


def test_run_not_implemented_exit_2(capsys):
    assert main(["run", "examples/demo-project"]) == 2
    assert "M2" in capsys.readouterr().err


@pytest.mark.parametrize("cmd", [["bench"], ["report"], ["serve"]])
def test_future_commands_exit_2(cmd, capsys):
    assert main(cmd) == 2
    assert "尚未实现" in capsys.readouterr().err


def test_datagen_creates_projects(tmp_path, capsys):
    assert main(["datagen", "--seed", "7", "--out", str(tmp_path)]) == 0
    assert "已生成" in capsys.readouterr().out
    for key in ("demo-goods-1", "demo-goods-2", "demo-services-1"):
        gt = tmp_path / key / "ground_truth.json"
        assert gt.is_file(), f"缺 {key}/ground_truth.json"
        truth = json.loads(gt.read_text(encoding="utf-8"))
        assert truth["seed"] == 7
        assert (tmp_path / key / truth["tender_file"]).is_file()
