"""解析公共预处理（plan/03 §六.5 陷阱清单：伪空格、CRLF 残留等）。"""

_ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff")


def normalize_text(text: str) -> str:
    """CRLF 归一 + 零宽字符清理 + 全角空格归一为半角空格。

    归一保持字符间距语义（"第一章　总则" → "第一章 总则"），正则侧用 \\s* 吸收间距。
    """
    out = text.replace("\r\n", "\n").replace("\r", "\n")
    for ch in _ZERO_WIDTH:
        out = out.replace(ch, "")
    return out.replace("\u3000", " ")
