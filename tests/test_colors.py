"""colors 모듈 테스트."""

from __future__ import annotations

import re

from cora2.colors import _hsl_to_hex, _ordered_tags, build_colors

_HEX = re.compile(r"^#[0-9a-f]{6}$")


def test_hsl_to_hex_format():
    assert _HEX.match(_hsl_to_hex(0, 60, 50))
    assert _hsl_to_hex(0, 0, 0) == "#000000"
    assert _hsl_to_hex(0, 0, 100) == "#ffffff"


def test_ordered_tags_canonical_first():
    order = _ordered_tags("size", ["Massive", "Tiny", "Medium"])
    # canonical 순서(Tiny<Medium<...<Massive) 유지
    assert order == ["Tiny", "Medium", "Massive"]


def test_ordered_tags_unknown_appended_sorted():
    order = _ordered_tags("file_type", ["Python", "C/C++", "asm"])
    # canonical 정의 없음 → 정렬
    assert order == sorted(["Python", "C/C++", "asm"])


def test_build_colors_structure():
    observed = {
        "file_type": ["Python", "C/C++"],
        "size": ["Tiny", "Large"],
        "ownership": ["Internal", "External"],
    }
    colors = build_colors(observed)
    # 관측 차원 + 기본 hue 정의 차원 모두 포함
    assert "file_type" in colors and "size" in colors
    for dim, info in colors.items():
        assert _HEX.match(info["base"])
        for tag, hexv in info["tags"].items():
            assert _HEX.match(hexv)
    # 각 차원 내 태그 색은 서로 달라야(명도 변형)
    ft = colors["file_type"]["tags"]
    assert ft["Python"] != ft["C/C++"]


def test_build_colors_includes_all_known_dimensions():
    colors = build_colors({})
    # 관측이 없어도 DIMENSION_HUES 의 차원들은 base 색을 가진다
    for dim in ["file_type", "purpose", "ownership", "license", "volatility",
                "recency", "author_pattern", "size", "dummy"]:
        assert dim in colors
