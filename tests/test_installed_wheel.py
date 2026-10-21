"""装态可用性门（M7 / D1 回归锚）：pip 装完 rule_type 不许退化为空串。

本文件三类判据，成本从低到高：

1. 静态声明门：`pyproject.toml` 必须把 rules.json + blocks.jsonl 声明进
   `[tool.setuptools.data-files]`（漏声明 = D1 复发）；
2. 装态定位门：`find_knowledge_dir()` 必须能命中 `<prefix>/share/bidchecker/knowledge`
   （用 monkeypatch 伪造 prefix，无需真装）；
3. 真装门（`installed_wheel` 标记）：把源码副本构建成 wheel → 装进临时 venv →
   **从中立目录**跑 `bidchecker run` → 断言该次 run 的 findings 与**同一份 examples
   在源码态跑出的 findings 逐字段相同**（除 project_dir 这类与环境相关字段）。

门槛口径：真装门断言的是"装态 == 源码态"这一相等关系，期望值由源码态现算，
不写死 rule_type 字符串——新增规则不会让它变红，丢列/退化才会。
"""
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "data" / "knowledge"
PYPROJECT = ROOT / "pyproject.toml"
DEMO = "demo-goods-1"


# ------------------------------------------------------------------ 1. 静态声明门
def test_pyproject_declares_knowledge_data_files():
    """D1 根因（①pyproject 无 data-files）的静态守门：声明缺失即红。"""
    text = PYPROJECT.read_text(encoding="utf-8")
    assert "[tool.setuptools.data-files]" in text, "缺 [tool.setuptools.data-files]，知识库不会进 wheel"
    block = text.split("[tool.setuptools.data-files]", 1)[1].split("\n[", 1)[0]
    assert "share/bidchecker/knowledge" in block, "数据未装到 share/bidchecker/knowledge（装态定位依赖此路径）"
    for name in ("rules.json", "blocks.jsonl"):
        assert f"data/knowledge/{name}" in block, f"data-files 漏 {name}（D1 将复发）"


def test_share_subdir_matches_declaration():
    """代码里的 SHARE_SUBDIR 与 pyproject 声明路径必须同源。"""
    from bidchecker.knowledge import SHARE_SUBDIR

    assert "/".join(SHARE_SUBDIR) == "share/bidchecker/knowledge"


# ------------------------------------------------------------------ 2. 装态定位门
def test_installed_share_dir_is_discovered(tmp_path, monkeypatch):
    """伪造 <prefix>/share/bidchecker/knowledge，断言 find_knowledge_dir 能命中。

    CWD 与包位置都放到中立目录（无 data/），确保命中只可能来自装态分支。
    """
    from bidchecker import knowledge

    share = tmp_path / "prefix" / "share" / "bidchecker" / "knowledge"
    share.mkdir(parents=True)
    for name in ("rules.json", "blocks.jsonl"):
        shutil.copyfile(KB / name, share / name)
    neutral = tmp_path / "neutral"
    neutral.mkdir()

    monkeypatch.chdir(neutral)
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "prefix"))
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "prefix"))
    monkeypatch.setattr(knowledge, "__file__", str(neutral / "bidchecker" / "knowledge" / "__init__.py"))

    assert knowledge.find_knowledge_dir() == share
    assert knowledge.knowledge_status()["available"] is True


def test_both_files_required_for_installed_dir(tmp_path, monkeypatch):
    """保留原判定：只放 rules.json 不算找到知识库。"""
    from bidchecker import knowledge

    share = tmp_path / "prefix" / "share" / "bidchecker" / "knowledge"
    share.mkdir(parents=True)
    shutil.copyfile(KB / "rules.json", share / "rules.json")
    neutral = tmp_path / "neutral"
    neutral.mkdir()

    monkeypatch.chdir(neutral)
    monkeypatch.setattr(sys, "prefix", str(tmp_path / "prefix"))
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path / "prefix"))
    monkeypatch.setattr(knowledge, "__file__", str(neutral / "bidchecker" / "knowledge" / "__init__.py"))

    assert knowledge.find_knowledge_dir() is None
    status = knowledge.knowledge_status()
    assert status["available"] is False and "blocks.jsonl" in status["reason"]


def test_missing_knowledge_warns_on_stderr(tmp_path, monkeypatch, capsys):
    """DEC3=A：知识库不可用时仍可运行，但 stderr 必须有一行警告（不许静默）。"""
    import bidchecker.pipeline as pl

    monkeypatch.setattr(pl, "load_rules", lambda *a, **k: [])
    pl.reset_knowledge_warning()
    result = pl.run_pipeline(ROOT / "examples" / "demo-goods-1", out_dir=str(tmp_path / "out"))
    dicts = result.finding_dicts()
    err = capsys.readouterr().err

    assert dicts, "演示项目应产出结论"
    assert all(d["rule_type"] == "" for d in dicts), "无规则映射时 rule_type 退化为空串（预期）"
    assert "警告：知识库不可用" in err
    # 只告警一次，不随序列化次数刷屏
    result.finding_dicts()
    assert capsys.readouterr().err == ""
    pl.reset_knowledge_warning()


# ------------------------------------------------------------------ 3. 真装门
def _copy_build_source(dest: Path) -> None:
    """只拷贝构建所需的最小源码集（避免 .git/build/dist 进构建上下文）。"""
    shutil.copyfile(ROOT / "pyproject.toml", dest / "pyproject.toml")
    shutil.copyfile(ROOT / "README.md", dest / "README.md")
    shutil.copyfile(ROOT / "LICENSE", dest / "LICENSE")
    shutil.copytree(ROOT / "src", dest / "src")
    kb_dest = dest / "data" / "knowledge"
    kb_dest.mkdir(parents=True)
    for name in ("rules.json", "blocks.jsonl"):
        shutil.copyfile(KB / name, kb_dest / name)


def _run(cmd, *, cwd, env=None):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", env=env)


@pytest.mark.installed_wheel
def test_wheel_install_keeps_rule_types(tmp_path):
    """D1 回归锚：wheel 装完后 rule_type 集合必须等于源码态集合，且能找到 share 知识库。"""
    build_src = tmp_path / "src-copy"
    build_src.mkdir()
    _copy_build_source(build_src)

    wheels = tmp_path / "wheels"
    wheels.mkdir()
    built = _run([sys.executable, "-m", "pip", "wheel", str(build_src),
                  "--no-deps", "-w", str(wheels)], cwd=tmp_path)
    assert built.returncode == 0, f"构建 wheel 失败：\n{built.stdout}\n{built.stderr}"
    whl = sorted(wheels.glob("bidchecker-*.whl"))
    assert whl, f"未产出 wheel：{built.stdout}"
    whl = whl[-1]

    # 静态判据：wheel 里必须真有知识库两个文件（D1 的第一环）
    import zipfile

    names = zipfile.ZipFile(whl).namelist()
    data_entries = [n for n in names if n.endswith(("rules.json", "blocks.jsonl"))]
    assert sorted(Path(n).name for n in data_entries) == ["blocks.jsonl", "rules.json"], \
        f"wheel 里知识库条目不符：{data_entries}（共 {len(names)} 条）"

    # 干净 venv（不 -e，不继承 PYTHONPATH）
    env_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, symlinks=False).create(str(env_dir))
    vpy = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    inst = _run([str(vpy), "-m", "pip", "install", "--no-deps", "--no-index", str(whl)],
                cwd=tmp_path)
    assert inst.returncode == 0, f"装 wheel 失败：\n{inst.stdout}\n{inst.stderr}"

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONIOENCODING"] = "utf-8"

    # 装态定位：必须命中 <venv>/share/bidchecker/knowledge，而不是源码树
    probe = _run([str(vpy), "-c",
                  "import bidchecker.knowledge as k;print(k.find_knowledge_dir())"],
                 cwd=tmp_path, env=env)
    assert probe.returncode == 0, probe.stderr
    located = probe.stdout.strip()
    assert located and "share" in located.replace("\\", "/"), \
        f"装态未命中 share 知识库：{located!r}"

    # 中立目录跑端到端（examples 复制过去，确保不靠仓库 CWD）
    neutral = tmp_path / "neutral"
    neutral.mkdir()
    shutil.copytree(ROOT / "examples", neutral / "examples")
    bidchecker = vpy.parent / ("bidchecker.exe" if os.name == "nt" else "bidchecker")
    run = _run([str(bidchecker), "run", "examples/demo-goods-1", "--out", "out"],
               cwd=neutral, env=env)
    assert run.returncode == 0, f"装态 run 失败（rc={run.returncode}）：\n{run.stdout}\n{run.stderr}"
    assert "警告：知识库不可用" not in run.stderr, f"装态仍报缺知识库：{run.stderr}"

    payload = json.loads((neutral / "out" / "findings.json").read_text(encoding="utf-8"))
    installed_types = {f["rule_type"] for f in payload["findings"]}
    assert "" not in installed_types, f"rule_type 出现空串（D1 复发）：{payload['findings']}"

    # 与源码态同一份 examples 逐字段对比（期望值现算，不写死）
    from bidchecker.pipeline import run_pipeline

    src_out = tmp_path / "src-out"
    src_result = run_pipeline(ROOT / "examples" / DEMO, out_dir=str(src_out))
    src_payload = json.loads((src_out / "findings.json").read_text(encoding="utf-8"))
    assert payload["findings"] == src_payload["findings"], (
        "装态 findings 与源码态不逐字段相同：\n"
        f"装态={json.dumps(payload['findings'], ensure_ascii=False)[:800]}\n"
        f"源码={json.dumps(src_payload['findings'], ensure_ascii=False)[:800]}")
    assert src_result.failed == [], "源码态对照 run 不应有解析失败"
