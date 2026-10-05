"""CLI：--version / 无参帮助 / 未交付命令退出码 2（不崩溃）。"""
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


@pytest.mark.parametrize("cmd", [["datagen"], ["bench"], ["report"], ["serve"]])
def test_future_commands_exit_2(cmd, capsys):
    assert main(cmd) == 2
    assert "尚未实现" in capsys.readouterr().err
