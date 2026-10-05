"""解析公共预处理：CRLF 归一 / 零宽字符 / 全角空格（plan/03 §六.5 陷阱清单）。"""
from bidchecker.parsers.common import normalize_text


def test_crlf_normalized():
    assert normalize_text("a\r\nb\rc\nd") == "a\nb\nc\nd"


def test_zero_width_removed():
    assert normalize_text("投\u200b标\ufeff文件\u2060响应") == "投标文件响应"


def test_ideographic_space_normalized():
    assert normalize_text("第一章　总则") == "第一章 总则"


def test_normal_text_unchanged():
    text = "第一章 总则\n投标人须知前附表：递交截止时间 2026-11-01 09:30。"
    assert normalize_text(text) == text
