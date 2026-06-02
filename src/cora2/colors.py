"""차원·태그 색상 매핑.

각 차원에 고정 hue 를 배정하고, 차원 내 태그들은 명도(lightness) 변형으로 구분한다.
Python 에서 산출한 hex 맵을 HTML 리포트에 임베드해 범례·dot·상세 칩이 모두 일치하도록 한다.
"""

from __future__ import annotations

# 차원 → 기준 색상환 hue(도). 9개를 시각적으로 구분되게 분산.
DIMENSION_HUES: dict[str, int] = {
    "file_type": 210,       # 파랑
    "purpose": 140,         # 초록
    "ownership": 25,        # 주황
    "license": 280,         # 보라
    "volatility": 0,        # 빨강
    "recency": 45,          # 황금
    "author_pattern": 320,  # 분홍
    "size": 185,            # 청록
    "dummy": 95,            # 연두
}

# 차원 내에서 의미 순서가 있는 태그(이 순서대로 명도 배정). 없으면 관측 태그를 정렬.
CANONICAL_TAGS: dict[str, list[str]] = {
    "ownership": ["Internal", "External", "Unknown"],
    "volatility": [
        "High-Churn", "Medium-Churn", "Low-Churn", "No-Churn",
        "Only Internal", "Internal-Dominant", "Mixed",
        "External-Dominant", "Only External",
    ],
    "recency": ["Hot", "Active", "Cooling", "Stable", "Dormant", "unknown"],
    "author_pattern": ["Single-Author", "Few-Author", "Shared", "unknown"],
    "size": ["Tiny", "Small", "Medium", "Large", "Massive", "unknown"],
    "purpose": [
        "Develop", "Build", "Test", "Infra", "Tool",
        "Core", "Library", "Config", "Variant",
    ],
}

_DEFAULT_HUE = 220
_SATURATION = 62  # %


def _hsl_to_hex(h: float, s: float, l: float) -> str:
    """HSL(h:0-360, s/l:0-100) → #RRGGBB."""
    s /= 100.0
    l /= 100.0
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0.0
    elif h < 120:
        r, g, b = x, c, 0.0
    elif h < 180:
        r, g, b = 0.0, c, x
    elif h < 240:
        r, g, b = 0.0, x, c
    elif h < 300:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    return "#{:02x}{:02x}{:02x}".format(
        round((r + m) * 255), round((g + m) * 255), round((b + m) * 255)
    )


def _ordered_tags(dimension: str, observed: list[str]) -> list[str]:
    """차원의 태그 표시 순서: canonical 우선, 나머지는 정렬해 뒤에."""
    canon = CANONICAL_TAGS.get(dimension, [])
    obs = set(observed)
    head = [t for t in canon if t in obs]
    tail = sorted(obs - set(head))
    return head + tail


def _shade_lightness(index: int, total: int) -> float:
    """태그 index 에 대한 명도(%): 38%~72% 사이 균등 분포."""
    if total <= 1:
        return 52.0
    return 38.0 + (72.0 - 38.0) * (index / (total - 1))


def build_colors(observed_by_dim: dict[str, list[str]]) -> dict[str, dict]:
    """차원별 {base, tags:{tag:hex}} 색상 맵을 만든다.

    observed_by_dim: 차원 → 리포트에서 실제 관측된 태그 목록.
    """
    result: dict[str, dict] = {}
    for dim, hue in _all_dimensions(observed_by_dim):
        tags = _ordered_tags(dim, observed_by_dim.get(dim, []))
        tag_colors = {
            tag: _hsl_to_hex(hue, _SATURATION, _shade_lightness(i, len(tags)))
            for i, tag in enumerate(tags)
        }
        result[dim] = {
            "base": _hsl_to_hex(hue, _SATURATION, 52.0),
            "tags": tag_colors,
        }
    return result


def _all_dimensions(observed_by_dim: dict[str, list[str]]):
    """관측된 차원 + 기본 hue 정의가 있는 차원 모두에 대해 (이름, hue) 산출."""
    names = set(observed_by_dim) | set(DIMENSION_HUES)
    for name in names:
        yield name, DIMENSION_HUES.get(name, _DEFAULT_HUE)
