"""人民币大小写金额换算（生成器与解析器共用，plan/04 §三 槽位函数）。

- amount_to_words：数字 → 大写（datagen 渲染开标一览表）；
- words_to_amount：大写 → 数字（M2 解析器换算大写总价）。

两方向互为逆运算（amount_to_words 的全部合法输出可被 words_to_amount 还原，
见 tests/test_amounts.py 往返用例）。金额一律按"元"为单位的整数/两位于数处理，
渲染格式统一为 "￥1,234.00"（千分位 + 两位小数，由 render_amount 提供）。
"""
from __future__ import annotations

from typing import Union

_DIGITS = "零壹贰叁肆伍陆柒捌玖"
_DIGIT_MAP = {ch: i for i, ch in enumerate(_DIGITS)}
_UNIT_MAP = {"拾": 10, "佰": 100, "仟": 1000}
_GROUP_MAP = {"万": 10_000, "亿": 100_000_000}

_MAX_AMOUNT = 999_999_999_999  # 12 位：仟亿级，超出的合成金额没有业务意义


def _four_digits(n: int) -> str:
    """0..9999 → 大写（不含万/亿后缀）；0 返回空串。"""
    parts = []
    zero_pending = False
    for i in (3, 2, 1, 0):
        d = (n // 10 ** i) % 10
        if d == 0:
            if parts:
                zero_pending = True
        else:
            if zero_pending:
                parts.append("零")
                zero_pending = False
            parts.append(_DIGITS[d] + ("", "拾", "佰", "仟")[i])
    return "".join(parts)


def amount_to_words(amount: Union[int, float]) -> str:
    """整数元金额 → 人民币大写（不带"人民币"前缀）。0.5 元 → 零伍角。

    输入按分取整（round），仅支持 |amount| ≤ _MAX_AMOUNT 的非负金额；
    越界/负数抛 ValueError（合成数据金额都在业务范围内，越界即数据 bug）。
    """
    cents = int(round(float(amount) * 100))
    if cents < 0 or float(amount) > _MAX_AMOUNT:
        raise ValueError(f"金额超出可换算范围: {amount!r}")
    yuan, jiao, fen = cents // 100, cents // 10 % 10, cents % 10
    if yuan == 0 and jiao == 0 and fen == 0:
        return "零元整"

    words = ""
    if yuan > 0:
        groups = []
        n = yuan
        while n > 0:
            groups.append(n % 10000)
            n //= 10000
        gap = False  # 上一个非零段与本段之间存在零段/段内高位缺位
        for idx in range(len(groups) - 1, -1, -1):
            g = groups[idx]
            if g == 0:
                gap = True
                continue
            seg = _four_digits(g)
            if words and (gap or g < 1000):
                seg = "零" + seg
            words += seg + ("", "万", "亿")[idx]
            gap = False
        words += "元"

    if jiao == 0 and fen == 0:
        return words + "整"
    if jiao > 0:
        words += _DIGITS[jiao] + "角"
        if fen == 0:
            return words + "整"
    else:
        words += "零"
    return words + _DIGITS[fen] + "分"


def words_to_amount(text: str) -> float:
    """大写金额 → 元（float；整数元无角分时返回整数值浮点）。

    解析 amount_to_words 的规范输出（零/壹..玖 + 拾佰仟 + 万/亿 + 元角分整）；
    遇到规范外的字符抛 ValueError（宁缺勿错，留待 LLM 兜底，plan/04 §三.4）。
    """
    group = 0        # 当前万段内累计值
    completed = 0    # 已完成的高位段（万/亿乘毕）
    yuan = None      # "元"锚定后为整数元部分；未出现"元"时在末尾兜底累计
    jiao = 0.0
    fen = 0.0
    digit = None
    for ch in text:
        if ch in _DIGIT_MAP:
            digit = _DIGIT_MAP[ch]
        elif ch in _UNIT_MAP:
            group += (digit if digit is not None else 1) * _UNIT_MAP[ch]
            digit = None
        elif ch in _GROUP_MAP:
            group = (group + (digit or 0)) * _GROUP_MAP[ch]
            completed += group
            group = 0
            digit = None
        elif ch == "元":
            yuan = completed + group + (digit or 0)
            group = 0
            digit = None
        elif ch == "角":
            jiao = (digit or 0) / 10
            digit = None
        elif ch == "分":
            fen = (digit or 0) / 100
            digit = None
        elif ch in ("零", "整"):
            digit = None if ch == "零" else digit
        else:
            raise ValueError(f"大写金额含规范外字符: {ch!r} in {text!r}")
    if yuan is None:
        yuan = completed + group + (digit or 0)
    elif digit is not None or group:
        raise ValueError(f"元后残留未挂接数字: {text!r}")
    return yuan + jiao + fen


def render_amount(yuan: Union[int, float]) -> str:
    """规范小写金额渲染：2,800,000 → "￥2,800,000.00"（千分位，固定两位小数）。"""
    cents = int(round(float(yuan) * 100))
    if cents < 0:
        raise ValueError(f"金额不能为负: {yuan!r}")
    whole, frac = divmod(cents, 100)
    return f"￥{whole:,}.{frac:02d}"
