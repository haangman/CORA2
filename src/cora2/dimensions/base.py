"""차원 태거의 공통 인터페이스.

각 차원은 `Dimension`을 상속해 `name`(레지스트리 키)과 `tag(ctx)`를 구현한다.
`tag`는 해당 파일에 부여할 태그 문자열 리스트를 반환한다(다중 태그 가능).
판정 불가/비해당이면 빈 리스트 또는 ["unknown"] 등 차원별 약속에 따른다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from cora2.context import FileContext


class Dimension(ABC):
    """모든 차원 태거의 베이스 클래스."""

    #: 레지스트리 키이자 결과 dict의 차원 이름
    name: str = ""

    @abstractmethod
    def tag(self, ctx: FileContext) -> list[str]:
        """파일에 부여할 태그 목록을 반환한다."""
        raise NotImplementedError
