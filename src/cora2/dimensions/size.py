"""차원8: Size — 파일 크기(LOC 기준)를 분류한다.

Tiny / Small / Medium / Large / Massive. 바이너리 등 LOC 산출 불가 시 unknown.
"""

from __future__ import annotations

from cora2.context import FileContext
from cora2.dimensions.base import Dimension


class SizeDimension(Dimension):
    name = "size"

    def tag(self, ctx: FileContext) -> list[str]:
        loc = ctx.line_count
        if loc is None:
            return ["unknown"]

        cfg = ctx.config.size
        if loc <= cfg.tiny_max:
            return ["Tiny"]
        if loc <= cfg.small_max:
            return ["Small"]
        if loc <= cfg.medium_max:
            return ["Medium"]
        if loc <= cfg.large_max:
            return ["Large"]
        return ["Massive"]
