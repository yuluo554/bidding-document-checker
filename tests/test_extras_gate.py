"""extras 守门：静态解析 pyproject，锁住运行期/测试期依赖声明。

漏声明 python-multipart → uvicorn 启动即崩（UploadFile/File 隐式依赖）；
漏声明 httpx → TestClient 静默少跑不是报错——此类缺失必须靠声明断言拦截。
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _extras_block() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r"\[project\.optional-dependencies\]\n(.*?)(?:\n\[|\Z)", text, re.S)
    assert m, "pyproject.toml 缺少 [project.optional-dependencies]"
    return m.group(1)


def _extra_line(block: str, name: str) -> str:
    m = re.search(rf"^{name}\s*=\s*\[(.*?)\]", block, re.S | re.M)
    assert m, f"pyproject 缺少 extra: {name}"
    return m.group(1)


def test_core_has_zero_runtime_dependencies():
    text = PYPROJECT.read_text(encoding="utf-8")
    assert re.search(r"^dependencies\s*=\s*\[\s*\]", text, re.M), "core（解析/引擎/基准）必须零依赖"


def test_web_extra_declares_multipart():
    assert "python-multipart" in _extra_line(_extras_block(), "web")


def test_llm_extra_declares_http_client():
    assert "httpx" in _extra_line(_extras_block(), "llm")


def test_report_extra_declares_docx():
    assert "python-docx" in _extra_line(_extras_block(), "report")


def test_dev_extra_declares_pytest():
    assert "pytest" in _extra_line(_extras_block(), "dev")
