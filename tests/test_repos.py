"""repos 모듈 테스트."""

from __future__ import annotations

from cora2.config import Config, RepoConfig
from cora2.repos import (
    RepoInfo,
    build_repos,
    repo_relative,
    resolve_repo,
)


def _repo(name, rel_root):
    return RepoInfo(name=name, root=None, rel_root=rel_root)


def test_resolve_longest_prefix():
    repos = [
        _repo("root", ""),
        _repo("zlib", "third_party/zlib"),
    ]
    # 하위 repo가 더 구체적이면 그쪽으로
    r = resolve_repo("third_party/zlib/src/a.c", repos)
    assert r.name == "zlib"
    # 루트만 매칭되는 경우
    r2 = resolve_repo("src/main.py", repos)
    assert r2.name == "root"


def test_resolve_no_match_returns_none():
    repos = [_repo("zlib", "third_party/zlib")]
    assert resolve_repo("src/main.py", repos) is None


def test_resolve_exact_path():
    repos = [_repo("zlib", "third_party/zlib")]
    r = resolve_repo("third_party/zlib", repos)
    assert r is not None and r.name == "zlib"


def test_resolve_prefix_not_partial_token():
    # third_party/zlib-extra 는 third_party/zlib 의 하위가 아니다.
    repos = [_repo("zlib", "third_party/zlib")]
    assert resolve_repo("third_party/zlib-extra/a.c", repos) is None


def test_repo_relative():
    root = _repo("root", "")
    sub = _repo("zlib", "third_party/zlib")
    assert repo_relative("src/main.py", root) == "src/main.py"
    assert repo_relative("third_party/zlib/src/a.c", sub) == "src/a.c"
    assert repo_relative("third_party/zlib", sub) == ""


def test_build_repos_from_config_without_git(tmp_path):
    # git 없는 폴더라도 설정의 repo 항목은 그대로 구성된다(branch는 None).
    cfg = Config(repos=[RepoConfig(path=".", name="myroot")])
    repos = build_repos(tmp_path, cfg)
    assert len(repos) == 1
    assert repos[0].name == "myroot"
    assert repos[0].rel_root == ""


def test_build_repos_no_config_no_git(tmp_path):
    # 설정도 없고 git도 아니면 빈 목록
    assert build_repos(tmp_path, Config()) == []
