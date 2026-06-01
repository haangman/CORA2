"""차원 레지스트리.

차원 이름(config의 enabled_dimensions 키)을 실제 Dimension 인스턴스로 매핑한다.
새 차원을 추가하려면 모듈을 만들고 `_REGISTRY`에 한 줄 등록하면 된다.

import는 `build_dimensions` 내부에서 지연 수행한다(순환 import 방지 및 선택적 로딩).
"""

from __future__ import annotations

from cora2.config import Config
from cora2.dimensions.base import Dimension


def _registry() -> dict[str, type[Dimension]]:
    from cora2.dimensions.author_pattern import AuthorPatternDimension
    from cora2.dimensions.dummy import DummyDimension
    from cora2.dimensions.file_type import FileTypeDimension
    from cora2.dimensions.license import LicenseDimension
    from cora2.dimensions.ownership import OwnershipDimension
    from cora2.dimensions.purpose import PurposeDimension
    from cora2.dimensions.recency import RecencyDimension
    from cora2.dimensions.size import SizeDimension
    from cora2.dimensions.volatility import VolatilityDimension

    return {
        "file_type": FileTypeDimension,
        "purpose": PurposeDimension,
        "ownership": OwnershipDimension,
        "license": LicenseDimension,
        "volatility": VolatilityDimension,
        "recency": RecencyDimension,
        "author_pattern": AuthorPatternDimension,
        "size": SizeDimension,
        "dummy": DummyDimension,
    }


def build_dimensions(config: Config) -> list[Dimension]:
    """config.enabled_dimensions 순서대로 활성 차원 인스턴스 목록을 만든다."""
    registry = _registry()
    dims: list[Dimension] = []
    for name in config.enabled_dimensions:
        cls = registry.get(name)
        if cls is not None:
            dims.append(cls())
    return dims


def available_dimensions() -> list[str]:
    """등록된 모든 차원 이름."""
    return list(_registry().keys())
