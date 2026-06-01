"""각 차원 태거 단위 테스트.

실제 임시 파일 + 주입한 GitFileStats + 고정 now 로 결정론적으로 검증한다.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from cora2.config import Config, OwnershipConfig
from cora2.context import FileContext
from cora2.gitinfo import CommitRec, GitFileStats
from cora2.repos import RepoInfo
from cora2.dimensions.author_pattern import AuthorPatternDimension
from cora2.dimensions.dummy import DummyDimension
from cora2.dimensions.file_type import FileTypeDimension
from cora2.dimensions.license import LicenseDimension
from cora2.dimensions.ownership import OwnershipDimension
from cora2.dimensions.purpose import PurposeDimension
from cora2.dimensions.recency import RecencyDimension
from cora2.dimensions.size import SizeDimension
from cora2.dimensions.volatility import VolatilityDimension

NOW = datetime(2024, 6, 15, tzinfo=timezone.utc)


def make_git(records) -> GitFileStats:
    """records: list of (email, 'YYYY-MM-DD', added, deleted)."""
    recs = []
    for email, date_s, added, deleted in records:
        d = datetime.fromisoformat(date_s).replace(tzinfo=timezone.utc)
        recs.append(CommitRec(sha="x", email=email, date=d, added=added, deleted=deleted))
    return GitFileStats(path="f", records=recs)


def make_ctx(tmp_path, rel, content="", git=None, config=None, repo=None):
    abs_path = tmp_path / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        abs_path.write_bytes(content)
    else:
        abs_path.write_text(content, encoding="utf-8")
    return FileContext(
        abs_path=abs_path,
        scan_rel=rel,
        config=config or Config(),
        now=NOW,
        repo=repo,
        repo_rel=rel,
        git=git,
    )


# ---------- 차원1: File Type ----------

@pytest.mark.parametrize(
    "rel,content,expected",
    [
        ("main.c", "", "C/C++"),
        ("app.cpp", "", "C/C++"),
        ("a.py", "", "Python"),
        ("run.sh", "", "Shell"),
        ("Mod.java", "", "Java"),
        ("lib.rs", "", "Rust"),
        ("CMakeLists.txt", "", "CMake"),
        ("build.cmake", "", "CMake"),
        ("Dockerfile", "", "Docker"),
        ("data.json", "{}", "Config"),
        ("conf.yaml", "", "Config"),
        ("README.md", "# x", "Docs"),
        ("weird.xyz", "", "Other"),
    ],
)
def test_file_type(tmp_path, rel, content, expected):
    ctx = make_ctx(tmp_path, rel, content)
    assert FileTypeDimension().tag(ctx) == [expected]


def test_file_type_uppercase_asm(tmp_path):
    ctx = make_ctx(tmp_path, "boot.S", "")
    assert FileTypeDimension().tag(ctx) == ["asm"]


def test_file_type_shebang(tmp_path):
    ctx = make_ctx(tmp_path, "tool", "#!/usr/bin/env python3\nprint(1)\n")
    assert FileTypeDimension().tag(ctx) == ["Python"]


# ---------- 차원2: Purpose (다중) ----------

def test_purpose_test_file(tmp_path):
    ctx = make_ctx(tmp_path, "tests/test_main.py")
    assert PurposeDimension().tag(ctx) == ["Test"]


def test_purpose_core_source_multi(tmp_path):
    tags = PurposeDimension().tag(make_ctx(tmp_path, "src/core/engine.py"))
    assert "Core" in tags and "Develop" in tags


def test_purpose_cmake_build_and_config(tmp_path):
    tags = PurposeDimension().tag(make_ctx(tmp_path, "CMakeLists.txt"))
    assert set(tags) == {"Build", "Config"}


def test_purpose_tool(tmp_path):
    tags = PurposeDimension().tag(make_ctx(tmp_path, "tools/gen.py"))
    assert "Tool" in tags


def test_purpose_doc_empty(tmp_path):
    assert PurposeDimension().tag(make_ctx(tmp_path, "README.md")) == []


# ---------- 차원3: Ownership ----------

@pytest.fixture
def own_cfg():
    return Config(
        ownership=OwnershipConfig(
            internal_authors=["@in.com"],
            internal_entities=["Samsung"],
            external_paths=["third_party/", "external/"],
        )
    )


def test_ownership_external_path(tmp_path, own_cfg):
    ctx = make_ctx(tmp_path, "third_party/zlib/z.c", "code", config=own_cfg)
    assert OwnershipDimension().tag(ctx) == ["External"]


def test_ownership_internal_header(tmp_path, own_cfg):
    ctx = make_ctx(tmp_path, "src/a.c", "/* Copyright (c) 2020 Samsung */\n", config=own_cfg)
    assert OwnershipDimension().tag(ctx) == ["Internal"]


def test_ownership_external_header(tmp_path, own_cfg):
    ctx = make_ctx(tmp_path, "src/a.c", "/* Copyright (c) 2020 ACME Inc */\n", config=own_cfg)
    assert OwnershipDimension().tag(ctx) == ["External"]


def test_ownership_git_majority_internal(tmp_path, own_cfg):
    git = make_git([("a@in.com", "2024-01-01", 1, 0), ("b@in.com", "2024-02-01", 1, 0),
                    ("c@ext.com", "2024-03-01", 1, 0)])
    ctx = make_ctx(tmp_path, "src/a.c", "code", git=git, config=own_cfg)
    assert OwnershipDimension().tag(ctx) == ["Internal"]


def test_ownership_unknown(tmp_path, own_cfg):
    ctx = make_ctx(tmp_path, "src/a.c", "code", config=own_cfg)
    assert OwnershipDimension().tag(ctx) == ["Unknown"]


# ---------- 차원4: License ----------

@pytest.fixture
def lic_cfg():
    return Config(ownership=OwnershipConfig(internal_entities=["Samsung"],
                                            external_paths=["third_party/"]))


def test_license_spdx_mit(tmp_path, lic_cfg):
    ctx = make_ctx(tmp_path, "a.c", "// SPDX-License-Identifier: MIT\n", config=lic_cfg)
    assert LicenseDimension().tag(ctx) == ["MIT"]


def test_license_gpl_phrase(tmp_path, lic_cfg):
    ctx = make_ctx(tmp_path, "a.c", "GNU GENERAL PUBLIC LICENSE Version 2\n", config=lic_cfg)
    assert LicenseDimension().tag(ctx) == ["GPL"]


def test_license_internal_entity(tmp_path, lic_cfg):
    ctx = make_ctx(tmp_path, "a.c", "/* Copyright Samsung Electronics */\n", config=lic_cfg)
    assert LicenseDimension().tag(ctx) == ["SAMSUNG"]


def test_license_third_party(tmp_path, lic_cfg):
    ctx = make_ctx(tmp_path, "third_party/x.c", "code\n", config=lic_cfg)
    assert LicenseDimension().tag(ctx) == ["3rd party"]


def test_license_unknown(tmp_path, lic_cfg):
    ctx = make_ctx(tmp_path, "src/a.c", "code\n", config=lic_cfg)
    assert LicenseDimension().tag(ctx) == ["unknown"]


def test_license_from_repo_license_file(tmp_path, lic_cfg):
    (tmp_path / "LICENSE").write_text("The MIT License\n", encoding="utf-8")
    repo = RepoInfo(name="r", root=tmp_path, rel_root="")
    ctx = make_ctx(tmp_path, "src/a.c", "code\n", config=lic_cfg, repo=repo)
    assert LicenseDimension().tag(ctx) == ["MIT"]


# ---------- 차원5: Volatility ----------

def test_volatility_no_git(tmp_path):
    assert VolatilityDimension().tag(make_ctx(tmp_path, "a.c", "x")) == ["No-Churn"]


def test_volatility_no_commits_in_window(tmp_path):
    # 윈도우(180일) 밖의 오래된 커밋만 존재
    git = make_git([("a@in.com", "2020-01-01", 5, 5)])
    assert VolatilityDimension().tag(make_ctx(tmp_path, "a.c", "x", git=git)) == ["No-Churn"]


def test_volatility_low_churn_only_internal(tmp_path):
    cfg = Config(ownership=OwnershipConfig(internal_authors=["@in.com"]))
    git = make_git([("a@in.com", "2024-06-01", 3, 0)])
    tags = VolatilityDimension().tag(make_ctx(tmp_path, "a.c", "x", git=git, config=cfg))
    assert tags == ["Low-Churn", "Only Internal"]


def test_volatility_high_churn_by_commits(tmp_path):
    cfg = Config(ownership=OwnershipConfig(internal_authors=["@in.com"]))
    recs = [("a@in.com", "2024-05-01", 1, 0)] * 60
    tags = VolatilityDimension().tag(make_ctx(tmp_path, "a.c", "x", git=make_git(recs), config=cfg))
    assert tags[0] == "High-Churn"


def test_volatility_high_churn_by_lines(tmp_path):
    git = make_git([("a@ext.com", "2024-05-01", 3000, 0)])
    tags = VolatilityDimension().tag(make_ctx(tmp_path, "a.c", "x", git=git))
    assert tags[0] == "High-Churn"


def test_volatility_mix_internal_dominant(tmp_path):
    cfg = Config(ownership=OwnershipConfig(internal_authors=["@in.com"]))
    recs = [("a@in.com", "2024-05-01", 1, 0)] * 4 + [("b@ext.com", "2024-05-02", 1, 0)]
    tags = VolatilityDimension().tag(make_ctx(tmp_path, "a.c", "x", git=make_git(recs), config=cfg))
    assert tags[1] == "Internal-Dominant"  # 0.8


def test_volatility_mix_mixed(tmp_path):
    cfg = Config(ownership=OwnershipConfig(internal_authors=["@in.com"]))
    recs = [("a@in.com", "2024-05-01", 1, 0)] * 2 + [("b@ext.com", "2024-05-02", 1, 0)] * 3
    tags = VolatilityDimension().tag(make_ctx(tmp_path, "a.c", "x", git=make_git(recs), config=cfg))
    assert tags[1] == "Mixed"  # 0.4


def test_volatility_only_external(tmp_path):
    cfg = Config(ownership=OwnershipConfig(internal_authors=["@in.com"]))
    recs = [("b@ext.com", "2024-05-02", 1, 0)] * 3
    tags = VolatilityDimension().tag(make_ctx(tmp_path, "a.c", "x", git=make_git(recs), config=cfg))
    assert tags[1] == "Only External"


# ---------- 차원6: Recency ----------

@pytest.mark.parametrize(
    "date_s,expected",
    [
        ("2024-06-01", "Hot"),      # 14일
        ("2024-04-01", "Active"),   # ~75일
        ("2024-01-10", "Cooling"),  # ~157일
        ("2023-09-01", "Stable"),   # ~288일
        ("2022-01-01", "Dormant"),  # >1년
    ],
)
def test_recency_from_git(tmp_path, date_s, expected):
    git = make_git([("a@x.com", date_s, 1, 0)])
    assert RecencyDimension().tag(make_ctx(tmp_path, "a.c", "x", git=git)) == [expected]


def test_recency_mtime_fallback(tmp_path):
    ctx = make_ctx(tmp_path, "a.c", "x")
    # mtime 을 2024-06-10 으로 설정 → Hot
    ts = datetime(2024, 6, 10, tzinfo=timezone.utc).timestamp()
    os.utime(ctx.abs_path, (ts, ts))
    assert RecencyDimension().tag(ctx) == ["Hot"]


# ---------- 차원7: Author Pattern ----------

def test_author_single(tmp_path):
    git = make_git([("a@x.com", "2024-01-01", 1, 0)] * 3)
    assert AuthorPatternDimension().tag(make_ctx(tmp_path, "a.c", "x", git=git)) == ["Single-Author"]


def test_author_single_by_ratio(tmp_path):
    recs = [("a@x.com", "2024-01-01", 1, 0)] * 9 + [("b@x.com", "2024-01-02", 1, 0)]
    assert AuthorPatternDimension().tag(make_ctx(tmp_path, "a.c", "x", git=make_git(recs))) == ["Single-Author"]


def test_author_few(tmp_path):
    recs = [("a@x.com", "2024-01-01", 1, 0), ("b@x.com", "2024-01-02", 1, 0),
            ("c@x.com", "2024-01-03", 1, 0)]
    assert AuthorPatternDimension().tag(make_ctx(tmp_path, "a.c", "x", git=make_git(recs))) == ["Few-Author"]


def test_author_shared(tmp_path):
    recs = [(f"u{i}@x.com", "2024-01-01", 1, 0) for i in range(5)] * 4
    assert AuthorPatternDimension().tag(make_ctx(tmp_path, "a.c", "x", git=make_git(recs))) == ["Shared"]


def test_author_unknown_without_git(tmp_path):
    assert AuthorPatternDimension().tag(make_ctx(tmp_path, "a.c", "x")) == ["unknown"]


# ---------- 차원8: Size ----------

@pytest.mark.parametrize(
    "lines,expected",
    [(10, "Tiny"), (50, "Tiny"), (51, "Small"), (200, "Small"),
     (201, "Medium"), (700, "Large"), (2001, "Massive")],
)
def test_size_loc(tmp_path, lines, expected):
    content = "x\n" * lines
    assert SizeDimension().tag(make_ctx(tmp_path, "a.py", content)) == [expected]


def test_size_binary_unknown(tmp_path):
    ctx = make_ctx(tmp_path, "a.bin", b"\x00\x01\x02binary")
    assert SizeDimension().tag(ctx) == ["unknown"]


# ---------- 차원9: Dummy ----------

def test_dummy_default(tmp_path):
    assert DummyDimension().tag(make_ctx(tmp_path, "a.py", "x")) == ["dummy"]
