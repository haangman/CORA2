"""차원9: Dummy — 더미 차원.

새 차원을 추가하는 방법을 보여주는 템플릿. config 의 [dummy] tag 값을 그대로 부여한다.
실제 의미는 없으며, 차원 추가 절차(모듈 작성 → 레지스트리 등록)의 예시 역할을 한다.
"""

from __future__ import annotations

from cora2.context import FileContext
from cora2.dimensions.base import Dimension


class DummyDimension(Dimension):
    name = "dummy"

    def tag(self, ctx: FileContext) -> list[str]:
        return [ctx.config.dummy.tag]
