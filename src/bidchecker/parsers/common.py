"""解析公共预处理与行级定位（plan/03 §六.5 陷阱清单：CRLF 残留、伪空格等）。

M2 解析器共用设施：
- normalize_text：CRLF 归一 + 零宽字符清理 + 全角空格归一（值抽取在归一行上做）；
- LineDoc：原文行/归一行 1:1 对齐的行序列 + 章节树（"## 第X章" 锚点、"### x.y" 小节）；
  Evidence.quote 一律取原文行——归一只删零宽字符/换空格、不动 \\n，行数必然一致；
- 槽位值合法性校验（宁缺勿错，plan/04 §三.4）：金额 ￥x,xxx.dd、ISO 日期/日期时间；
  校验不过返回 None，调用方丢弃该抽取，留待 LLM 兜底（M4）或人工。
"""
from __future__ import annotations

import re
from datetime import date
from typing import List, Optional, Tuple

_ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\u2060", "\ufeff")

_HEADING_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$")
_CHAPTER_TITLE_RE = re.compile(r"^第[0-9一二三四五六七八九十百]+章")
_AMOUNT_RE = re.compile(r"^￥([0-9][0-9,]*)\.([0-9]{2})$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


def normalize_text(text: str) -> str:
    """CRLF 归一 + 零宽字符清理 + 全角空格归一为半角空格。

    归一保持字符间距语义（"第一章　总则" → "第一章 总则"），正则侧用 \\s* 吸收间距；
    只删零宽字符、替换全角空格、不改 \\n——与 :func:`_normalize_eol` 的行序列 1:1 对齐。
    """
    out = _normalize_eol(text)
    for ch in _ZERO_WIDTH:
        out = out.replace(ch, "")
    return out.replace("\u3000", " ")


def _normalize_eol(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


class LineDoc:
    """对齐的原文行/归一行序列 + 章节树索引（固定体例：## 第X章 / ### 小节标题）。"""

    def __init__(self, text: str):
        self.orig_lines: List[str] = _normalize_eol(text).split("\n")
        self.norm_lines: List[str] = normalize_text(text).split("\n")
        # 两种归一都不增删 \n；行数漂移只可能是实现 bug，大声失败
        assert len(self.orig_lines) == len(self.norm_lines), "行对齐失败：归一引入了换行差异"
        self._headings: List[Tuple[int, int, str]] = []  # (行下标, 标题级别, 标题文本)
        for i, ln in enumerate(self.norm_lines):
            m = _HEADING_RE.match(ln)
            if m:
                self._headings.append((i, len(m.group(1)), m.group(2)))

    def __len__(self) -> int:
        return len(self.norm_lines)

    def quote(self, idx: int) -> str:
        """Evidence.quote：原文行逐字摘录（去首尾空白后仍为原文子串）。"""
        return self.orig_lines[idx].strip()

    def section(self, idx: int) -> Optional[str]:
        """idx 行所属最近一级标题文本；文档头部行为标题行（# 层）文本。"""
        best = None
        for i, _lvl, title in self._headings:
            if i <= idx:
                best = title
            else:
                break
        return best

    def chapter(self, chapter: str) -> Optional[Tuple[int, int, str]]:
        """"第X章"章内容区间 [start, end)（不含章标题行）与章标题；未找到 → None。

        end = 下一章（## 级）标题行或文档尾——章内 ### 小节属于本章区间。
        """
        for k, (i, lvl, title) in enumerate(self._headings):
            if lvl == 2 and _CHAPTER_TITLE_RE.match(title) \
                    and title.split("（")[0].strip().startswith(chapter):
                end = len(self.norm_lines)
                for j in range(k + 1, len(self._headings)):
                    if self._headings[j][1] <= 2:
                        end = self._headings[j][0]
                        break
                return (i + 1, max(end, i + 1), title)
        return None

    def subsection(self, start: int, end: int, prefix: str) -> Optional[Tuple[int, int]]:
        """[start, end) 内标题以 prefix 开头的 ### 小节内容区间 [s, e)；未找到 → None。"""
        for k, (i, lvl, _title) in enumerate(self._headings):
            if not (start <= i < end) or lvl < 3:
                continue
            if _title.split("（")[0].strip().startswith(prefix):
                nxt = self._headings[k + 1][0] if k + 1 < len(self._headings) \
                    else len(self.norm_lines)
                return (i + 1, min(max(nxt, i + 1), end))
        return None


def parse_amount(token: str) -> Optional[float]:
    """规范小写金额 "￥1,234.00" → 元（float）；形态不符返回 None（宁缺勿错）。"""
    m = _AMOUNT_RE.match(token.strip())
    if not m:
        return None
    return float(f"{m.group(1).replace(',', '')}.{m.group(2)}")


def parse_date_str(token: str) -> Optional[str]:
    """ISO 纯日期 YYYY-MM-DD；格式与日历合法性通过返回原文，否则 None。"""
    s = token.strip()
    if not _DATE_RE.match(s):
        return None
    y, mo, d = (int(x) for x in s.split("-"))
    try:
        date(y, mo, d)
    except ValueError:
        return None
    return s


def parse_datetime_str(token: str) -> Optional[str]:
    """ISO 日期时间 YYYY-MM-DD HH:MM；合法返回原文，否则 None。"""
    s = token.strip()
    if not _DATETIME_RE.match(s):
        return None
    d, t = s.split(" ")
    if parse_date_str(d) is None:
        return None
    hh, mm = (int(x) for x in t.split(":"))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return None
    return s
