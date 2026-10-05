"""人民币大小写金额换算：定点用例 + 往返 + 非法输入大声失败。"""
import pytest

from bidchecker.amounts import amount_to_words, render_amount, words_to_amount

_CASES = [
    (0, "零元整"),
    (5, "伍元整"),
    (10, "壹拾元整"),
    (105, "壹佰零伍元整"),
    (110, "壹佰壹拾元整"),
    (200, "贰佰元整"),
    (1005, "壹仟零伍元整"),
    (10_000, "壹万元整"),
    (10_500, "壹万零伍佰元整"),
    (100_000, "壹拾万元整"),
    (1_000_000, "壹佰万元整"),
    (1_050_000, "壹佰零伍万元整"),
    (2_800_000, "贰佰捌拾万元整"),
    (1_203_450, "壹佰贰拾万叁仟肆佰伍拾元整"),
    (100_000_000, "壹亿元整"),
    (100_000_001, "壹亿零壹元整"),
    (2_000_000_000, "贰拾亿元整"),
    (0.5, "伍角整"),
    (1.5, "壹元伍角整"),
    (1.05, "壹元零伍分"),
    (1.23, "壹元贰角叁分"),
    (0.04, "零肆分"),
]


@pytest.mark.parametrize("amount,words", _CASES)
def test_amount_to_words(amount, words):
    assert amount_to_words(amount) == words


@pytest.mark.parametrize("amount,_", _CASES, ids=str)
def test_round_trip(amount, _):
    assert words_to_amount(amount_to_words(amount)) == pytest.approx(float(amount))


def test_render_amount():
    assert render_amount(2_800_000) == "￥2,800,000.00"
    assert render_amount(1234.5) == "￥1,234.50"
    assert render_amount(0) == "￥0.00"


def test_amount_to_words_rejects_out_of_range():
    with pytest.raises(ValueError):
        amount_to_words(-1)
    with pytest.raises(ValueError):
        amount_to_words(10**12)


def test_words_to_amount_rejects_non_canonical():
    with pytest.raises(ValueError):
        words_to_amount("人民币壹佰元")  # 前缀由行模板持有，不在换算域
    with pytest.raises(ValueError):
        words_to_amount("hello")
