"""config 모듈 테스트."""

from __future__ import annotations

import pytest

from cora2.config import (
    ALL_DIMENSIONS,
    Config,
    find_and_load,
    load_config,
)


def test_load_config_none_returns_defaults():
    cfg = load_config(None)
    assert isinstance(cfg, Config)
    assert cfg.enabled_dimensions == ALL_DIMENSIONS
    assert cfg.volatility.window_days == 180
    assert cfg.recency.hot_days == 30
    assert cfg.size.tiny_max == 50
    assert cfg.dummy.tag == "dummy"
    # 기본 external_paths
    assert "third_party/" in cfg.ownership.external_paths


def test_load_config_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nope.toml")


def test_partial_merge_keeps_defaults(tmp_path):
    toml = tmp_path / "cora2.toml"
    toml.write_text(
        """
[recency]
hot_days = 7

[size]
tiny_max = 10
""",
        encoding="utf-8",
    )
    cfg = load_config(toml)
    # 덮어쓴 값
    assert cfg.recency.hot_days == 7
    assert cfg.size.tiny_max == 10
    # 같은 섹션의 미지정 키는 기본값 유지
    assert cfg.recency.active_days == 90
    assert cfg.size.large_max == 2000
    # 다른 섹션도 기본값 유지
    assert cfg.volatility.window_days == 180


def test_repo_and_dimension_parsing(tmp_path):
    toml = tmp_path / "cora2.toml"
    toml.write_text(
        """
[dimensions]
enabled = ["file_type", "size", "not_a_real_dim"]

[[repo]]
path = "."
name = "root"

[[repo]]
path = "third_party/zlib"
name = "zlib"
branch = "release"
""",
        encoding="utf-8",
    )
    cfg = load_config(toml)
    # 알 수 없는 차원은 걸러짐
    assert cfg.enabled_dimensions == ["file_type", "size"]
    assert len(cfg.repos) == 2
    assert cfg.repos[1].name == "zlib"
    assert cfg.repos[1].branch == "release"
    assert cfg.repos[0].branch is None


def test_license_patterns_override(tmp_path):
    toml = tmp_path / "cora2.toml"
    toml.write_text(
        """
[license]
internal_tag = "ACME"
patterns = [
  { regex = "BSD", tag = "BSD" },
]
""",
        encoding="utf-8",
    )
    cfg = load_config(toml)
    assert cfg.license.internal_tag == "ACME"
    assert len(cfg.license.patterns) == 1
    assert cfg.license.patterns[0].tag == "BSD"


def test_find_and_load_prefers_explicit(tmp_path):
    explicit = tmp_path / "custom.toml"
    explicit.write_text("[recency]\nhot_days = 3\n", encoding="utf-8")
    cfg = find_and_load(tmp_path, explicit)
    assert cfg.recency.hot_days == 3


def test_find_and_load_discovers_default(tmp_path):
    (tmp_path / "cora2.toml").write_text("[size]\ntiny_max = 1\n", encoding="utf-8")
    cfg = find_and_load(tmp_path, None)
    assert cfg.size.tiny_max == 1


def test_find_and_load_no_file_uses_defaults(tmp_path):
    cfg = find_and_load(tmp_path, None)
    assert cfg.size.tiny_max == 50
