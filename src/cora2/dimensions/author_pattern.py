"""차원7: Author Pattern — 작성자 분포 패턴을 분류한다.

작성자별 커밋 수(전체 기간)를 근거로 Single-Author / Few-Author / Shared.
git 정보가 없으면 unknown.
"""

from __future__ import annotations

from cora2.context import FileContext
from cora2.dimensions.base import Dimension


class AuthorPatternDimension(Dimension):
    name = "author_pattern"

    def tag(self, ctx: FileContext) -> list[str]:
        if ctx.git is None or ctx.git.commit_count == 0:
            return ["unknown"]

        authors = ctx.git.authors
        counts = sorted(authors.values(), reverse=True)
        distinct = len(counts)
        total = sum(counts)
        cfg = ctx.config.author_pattern

        top1 = counts[0] / total
        top3 = sum(counts[:3]) / total

        if distinct == 1 or top1 >= cfg.single_ratio:
            return ["Single-Author"]
        if distinct <= cfg.few_max or top3 >= cfg.few_ratio:
            return ["Few-Author"]
        return ["Shared"]
