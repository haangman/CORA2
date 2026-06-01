"""설정 로딩.

TOML 설정파일을 읽어 차원별 기준값/임계치, repo 매핑, ownership/license 규칙 등을
`Config` 데이터클래스로 만든다. 설정파일이 없거나 일부 키가 빠져 있으면 코드에 정의된
기본값을 사용한다(부분 병합).

설정파일이 없어도 모든 기능이 기본값으로 동작하는 것을 보장한다.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

# 설정파일을 명시하지 않았을 때 스캔 루트에서 찾는 기본 파일명
DEFAULT_CONFIG_FILENAME = "cora2.toml"

# 전체 차원 이름(레지스트리 키와 일치해야 함)
ALL_DIMENSIONS = [
    "file_type",
    "purpose",
    "ownership",
    "license",
    "volatility",
    "recency",
    "author_pattern",
    "size",
    "dummy",
]


@dataclass
class RepoConfig:
    """설정파일의 [[repo]] 항목 하나."""

    path: str  # 스캔 루트 기준 상대경로 (POSIX). "." 은 루트 자신.
    name: str | None = None
    branch: str | None = None  # 생략 시 git에서 자동 감지
    remote: str | None = None


@dataclass
class OwnershipConfig:
    internal_authors: list[str] = field(default_factory=list)
    internal_entities: list[str] = field(default_factory=list)
    external_paths: list[str] = field(
        default_factory=lambda: ["third_party/", "external/", "vendor/"]
    )


@dataclass
class LicensePattern:
    regex: str
    tag: str


@dataclass
class LicenseConfig:
    internal_tag: str = "SAMSUNG"
    patterns: list[LicensePattern] = field(
        default_factory=lambda: [
            LicensePattern(r"SPDX-License-Identifier:\s*GPL", "GPL"),
            LicensePattern(r"SPDX-License-Identifier:\s*MIT", "MIT"),
            LicensePattern(r"SPDX-License-Identifier:\s*Apache", "Apache"),
            LicensePattern(r"GNU GENERAL PUBLIC LICENSE", "GPL"),
            LicensePattern(r"MIT License", "MIT"),
            LicensePattern(r"Apache License", "Apache"),
        ]
    )


@dataclass
class VolatilityConfig:
    window_days: int = 180
    high_churn_commits: int = 50
    medium_churn_commits: int = 10
    low_churn_commits: int = 1
    high_churn_lines: int = 2000
    medium_churn_lines: int = 500
    low_churn_lines: int = 50
    internal_dominant_ratio: float = 0.8


@dataclass
class RecencyConfig:
    hot_days: int = 30
    active_days: int = 90
    cooling_days: int = 180
    stable_days: int = 365


@dataclass
class AuthorPatternConfig:
    single_ratio: float = 0.9
    few_max: int = 3
    few_ratio: float = 0.9
    shared_min: int = 4


@dataclass
class SizeConfig:
    """LOC(줄 수) 기준 임계치. 각 값은 해당 버킷의 상한(이하)."""

    tiny_max: int = 50
    small_max: int = 200
    medium_max: int = 500
    large_max: int = 2000  # 초과 = Massive


@dataclass
class DummyConfig:
    tag: str = "dummy"


@dataclass
class Config:
    enabled_dimensions: list[str] = field(default_factory=lambda: list(ALL_DIMENSIONS))
    ignore_dirs: set[str] | None = None  # None이면 classifier 기본값 사용
    repos: list[RepoConfig] = field(default_factory=list)
    ownership: OwnershipConfig = field(default_factory=OwnershipConfig)
    license: LicenseConfig = field(default_factory=LicenseConfig)
    volatility: VolatilityConfig = field(default_factory=VolatilityConfig)
    recency: RecencyConfig = field(default_factory=RecencyConfig)
    author_pattern: AuthorPatternConfig = field(default_factory=AuthorPatternConfig)
    size: SizeConfig = field(default_factory=SizeConfig)
    dummy: DummyConfig = field(default_factory=DummyConfig)


def _merge_dataclass(obj, data: dict) -> None:
    """dict의 키 중 dataclass 필드와 일치하는 것만 obj에 덮어쓴다(부분 병합)."""
    valid = set(getattr(obj, "__dataclass_fields__", {}))
    for key, value in data.items():
        if key in valid:
            setattr(obj, key, value)


def load_config(path: str | Path | None) -> Config:
    """설정파일을 읽어 Config를 만든다. path가 None이거나 없으면 전부 기본값."""
    cfg = Config()
    if path is None:
        return cfg

    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"설정파일을 찾을 수 없습니다: {path}")

    with p.open("rb") as fh:
        data = tomllib.load(fh)

    return _apply(cfg, data)


def find_and_load(scan_root: str | Path, explicit: str | Path | None) -> Config:
    """설정파일 경로 결정 후 로드.

    explicit이 주어지면 그 파일을(없으면 에러), 아니면 scan_root/cora2.toml을 탐색해
    있으면 사용하고 없으면 기본값으로 동작한다.
    """
    if explicit is not None:
        return load_config(explicit)
    candidate = Path(scan_root) / DEFAULT_CONFIG_FILENAME
    if candidate.is_file():
        return load_config(candidate)
    return Config()


def _apply(cfg: Config, data: dict) -> Config:
    """파싱된 TOML dict을 Config에 병합한다."""
    scan = data.get("scan", {})
    if isinstance(scan.get("ignore_dirs"), list) and scan["ignore_dirs"]:
        cfg.ignore_dirs = set(scan["ignore_dirs"])

    dims = data.get("dimensions", {})
    if isinstance(dims.get("enabled"), list):
        cfg.enabled_dimensions = [d for d in dims["enabled"] if d in ALL_DIMENSIONS]

    for entry in data.get("repo", []):
        if "path" in entry:
            cfg.repos.append(
                RepoConfig(
                    path=entry["path"],
                    name=entry.get("name"),
                    branch=entry.get("branch"),
                    remote=entry.get("remote"),
                )
            )

    _merge_dataclass(cfg.ownership, data.get("ownership", {}))
    _merge_dataclass(cfg.volatility, data.get("volatility", {}))
    _merge_dataclass(cfg.recency, data.get("recency", {}))
    _merge_dataclass(cfg.author_pattern, data.get("author_pattern", {}))
    _merge_dataclass(cfg.size, data.get("size", {}))
    _merge_dataclass(cfg.dummy, data.get("dummy", {}))

    lic = data.get("license", {})
    if "internal_tag" in lic:
        cfg.license.internal_tag = lic["internal_tag"]
    if isinstance(lic.get("patterns"), list):
        cfg.license.patterns = [
            LicensePattern(regex=pat["regex"], tag=pat["tag"])
            for pat in lic["patterns"]
            if "regex" in pat and "tag" in pat
        ]

    return cfg
