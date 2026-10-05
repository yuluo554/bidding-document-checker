"""确定性随机源：splitmix64，跨 Python 版本/平台位级一致（M1 守门测试地基）。

stdlib random.Random 只承诺"兼容 seeder 下同序列"，且官方文档明确其算法可能随版本
调整；本项目 CI 是 py3.8 × py3.12 双矩阵，fixtures 又要求字节冻结——因此生成路径
禁用 random 模块，统一用本实现（splitmix64，只依赖整数运算，任何版本结果一致）。

纪律：生成路径禁止迭代 set/dict-keys-of-unordered（PYTHONHASHSEED 跨进程不一致），
实体池一律用 tuple，洗牌/抽样用本类方法。
"""
from __future__ import annotations

from typing import List, Sequence, TypeVar

T = TypeVar("T")

_MASK64 = (1 << 64) - 1
_GOLDEN = 0x9E3779B97F4A7C15


def fnv1a64(data: bytes) -> int:
    """FNV-1a 64bit：把字符串 key（如项目 id）折算成稳定 seed。"""
    h = 0xCBF29CE484222325
    for b in data:
        h = ((h ^ b) * 0x100000001B3) & _MASK64
    return h


class DetRng:
    """splitmix64 计数器型 PRNG：next_u64 序列仅由初始 state 决定。"""

    def __init__(self, seed: int):
        self._state = seed & _MASK64

    def next_u64(self) -> int:
        self._state = (self._state + _GOLDEN) & _MASK64
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
        return z ^ (z >> 31)

    def below(self, n: int) -> int:
        """[0, n) 无偏整数（拒绝采样，避免模偏差）。"""
        if n <= 0:
            raise ValueError(f"below 需要正整数，得到 {n}")
        limit = ((1 << 64) // n) * n
        while True:
            x = self.next_u64()
            if x < limit:
                return x % n

    def randint(self, lo: int, hi: int) -> int:
        """闭区间 [lo, hi] 整数。"""
        return lo + self.below(hi - lo + 1)

    def choice(self, seq: Sequence[T]) -> T:
        return seq[self.below(len(seq))]

    def shuffle(self, seq: List[T]) -> List[T]:
        """就地 Fisher-Yates 洗牌（传入 list）。"""
        for i in range(len(seq) - 1, 0, -1):
            j = self.below(i + 1)
            seq[i], seq[j] = seq[j], seq[i]
        return seq

    def sample(self, seq: Sequence[T], k: int) -> List[T]:
        """不重复抽取 k 个（部分 Fisher-Yates，保序返回）。"""
        if not 0 <= k <= len(seq):
            raise ValueError(f"sample 大小非法: {k} > {len(seq)}")
        pool = list(seq)
        for i in range(k):
            j = i + self.below(len(pool) - i)
            pool[i], pool[j] = pool[j], pool[i]
        return pool[:k]


def project_rng(seed: int, project_key: str) -> DetRng:
    """按 (seed, 项目 key) 派生子随机源：各项目互不串扰、整体可复现。"""
    return DetRng((seed & _MASK64) ^ fnv1a64(project_key.encode("utf-8")))
