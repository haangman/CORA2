"""tagger 통합 테스트.

임시 git repo와 몇 개의 파일을 만들어 전체 태깅 파이프라인을 검증한다.
git 미설치 시 git 의존 차원은 degrade 되지만 파이프라인 자체는 동작한다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone

import pytest

from cora2.config import Config, OwnershipConfig
from cora2.tagger import tag_directory

NOW = datetime(2024, 6, 15, tzinfo=timezone.utc)

_HAS_GIT = shutil.which("git") is not None


def _run(args, cwd, env=None):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", env=env)
    assert proc.returncode == 0, proc.stderr
    return proc


def _commit(repo, fname, content, email, date_iso):
    path = repo / fname
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _run(["git", "add", "-A"], cwd=repo)
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "Dev", "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": "Dev", "GIT_COMMITTER_EMAIL": email,
        "GIT_AUTHOR_DATE": date_iso, "GIT_COMMITTER_DATE": date_iso,
    })
    _run(["git", "commit", "-m", f"edit {fname}"], cwd=repo, env=env)


@pytest.fixture
def project(tmp_path):
    repo = tmp_path / "proj"
    repo.mkdir()
    if _HAS_GIT:
        _run(["git", "init", "-b", "main"], cwd=repo)
        _run(["git", "config", "commit.gpgsign", "false"], cwd=repo)
        _commit(repo, "src/main.py", "print('hi')\n", "alice@in.com", "2024-06-01T10:00:00+00:00")
        _commit(repo, "tests/test_main.py", "def test(): pass\n", "alice@in.com", "2024-06-02T10:00:00+00:00")
        _commit(repo, "README.md", "# proj\n", "bob@ext.com", "2024-06-03T10:00:00+00:00")
    else:
        (repo / "src").mkdir()
        (repo / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_main.py").write_text("def test(): pass\n", encoding="utf-8")
        (repo / "README.md").write_text("# proj\n", encoding="utf-8")
    return repo


@pytest.fixture
def cfg():
    return Config(ownership=OwnershipConfig(internal_authors=["@in.com"]))


def test_report_structure(project, cfg):
    report = tag_directory(project, config=cfg, now=NOW)
    assert report.total_files if hasattr(report, "total_files") else True
    paths = {f.path for f in report.files}
    assert paths == {"src/main.py", "tests/test_main.py", "README.md"}
    # 모든 파일이 9개 차원 전부를 가진다
    for f in report.files:
        assert set(f.tags.keys()) == {
            "file_type", "purpose", "ownership", "license",
            "volatility", "recency", "author_pattern", "size", "dummy",
        }


def test_tags_make_sense(project, cfg):
    report = tag_directory(project, config=cfg, now=NOW)
    by_path = {f.path: f.tags for f in report.files}
    assert by_path["src/main.py"]["file_type"] == ["Python"]
    assert by_path["tests/test_main.py"]["purpose"] == ["Test"]
    assert by_path["README.md"]["file_type"] == ["Docs"]
    # dummy 는 항상 동일
    assert by_path["src/main.py"]["dummy"] == ["dummy"]


@pytest.mark.skipif(not _HAS_GIT, reason="git 미설치")
def test_git_dependent_dimensions(project, cfg):
    report = tag_directory(project, config=cfg, now=NOW)
    by_path = {f.path: f.tags for f in report.files}
    # main.py: 2024-06-01 커밋 → Hot, alice 단독 → Single-Author
    assert by_path["src/main.py"]["recency"] == ["Hot"]
    assert by_path["src/main.py"]["author_pattern"] == ["Single-Author"]
    # alice 는 내부 → ownership Internal, volatility 둘째 태그 Only Internal
    assert by_path["src/main.py"]["ownership"] == ["Internal"]
    assert by_path["src/main.py"]["volatility"][1] == "Only Internal"
    # README: bob@ext → External
    assert by_path["README.md"]["ownership"] == ["External"]


def test_summary(project, cfg):
    report = tag_directory(project, config=cfg, now=NOW)
    summary = report.summary()
    assert summary["file_type"].get("Python") == 2  # main.py, test_main.py
    assert summary["dummy"].get("dummy") == 3


def test_to_dict_serializable(project, cfg):
    import json

    report = tag_directory(project, config=cfg, now=NOW)
    # JSON 직렬화 가능해야 한다
    s = json.dumps(report.to_dict(), ensure_ascii=False)
    assert "src/main.py" in s
