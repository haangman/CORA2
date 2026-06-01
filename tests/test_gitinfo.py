"""gitinfo 모듈 테스트.

임시 git repo를 만들고 작성자/날짜를 고정한 커밋을 생성해 통계를 검증한다.
git이 설치되어 있지 않으면 스킵한다.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timezone

import pytest

from cora2.gitinfo import build_git_index

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git 미설치"
)


def _run(args, cwd, env=None):
    proc = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=env
    )
    assert proc.returncode == 0, proc.stderr
    return proc


def _commit(repo, fname, content, author_email, date_iso, name="Dev"):
    (repo / fname).write_text(content, encoding="utf-8")
    _run(["git", "add", fname], cwd=repo)
    import os

    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": name,
            "GIT_COMMITTER_EMAIL": author_email,
            "GIT_AUTHOR_DATE": date_iso,
            "GIT_COMMITTER_DATE": date_iso,
        }
    )
    _run(["git", "commit", "-m", f"edit {fname}"], cwd=repo, env=env)


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main"], cwd=repo)
    _run(["git", "config", "commit.gpgsign", "false"], cwd=repo)
    # a.py: 두 명의 작성자, 두 번의 커밋
    _commit(repo, "a.py", "x = 1\n", "alice@in.com", "2024-01-01T10:00:00+00:00")
    _commit(repo, "a.py", "x = 1\ny = 2\nz = 3\n", "bob@ext.com", "2024-06-01T10:00:00+00:00")
    # b.py: 한 명, 한 번
    _commit(repo, "b.py", "print(1)\n", "alice@in.com", "2024-03-01T10:00:00+00:00")
    return repo


def test_build_index_available(git_repo):
    idx = build_git_index(git_repo)
    assert idx.available is True
    assert len(idx) == 2


def test_file_stats_aggregates(git_repo):
    idx = build_git_index(git_repo)
    a = idx.get("a.py")
    assert a is not None
    assert a.commit_count == 2
    assert set(a.authors) == {"alice@in.com", "bob@ext.com"}
    assert a.authors["alice@in.com"] == 1
    # first/last date
    assert a.first_date == datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    assert a.last_date == datetime(2024, 6, 1, 10, 0, tzinfo=timezone.utc)
    # 변경 라인: 1행 추가 + 2행 추가 = 3
    assert a.lines_changed == 3


def test_single_author_file(git_repo):
    idx = build_git_index(git_repo)
    b = idx.get("b.py")
    assert b.commit_count == 1
    assert list(b.authors) == ["alice@in.com"]


def test_window_stats(git_repo):
    idx = build_git_index(git_repo)
    a = idx.get("a.py")
    now = datetime(2024, 6, 15, tzinfo=timezone.utc)
    # 최근 30일 윈도우: 2024-06-01 커밋 1개만 포함
    commits, lines = a.window(now, 30)
    assert commits == 1
    assert lines == 2
    # 1년 윈도우: 둘 다 포함
    commits2, lines2 = a.window(now, 365)
    assert commits2 == 2


def test_non_git_dir_returns_empty(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    idx = build_git_index(plain)
    assert idx.available is False
    assert idx.get("a.py") is None


def test_normalize_rename_paths():
    from cora2.gitinfo import _normalize_path

    assert _normalize_path("old.c => new.c") == "new.c"
    assert _normalize_path("src/{old => new}/f.c") == "src/new/f.c"
    assert _normalize_path("a/b.c") == "a/b.c"
