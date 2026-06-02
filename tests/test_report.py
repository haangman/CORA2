"""report 모듈 테스트 (데이터 빌드 + HTML 렌더)."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone

import pytest

from cora2.config import Config, OwnershipConfig
from cora2.report import build_report_data, render_html, write_report

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
        _commit(repo, "src/util.c", "int x;\n", "bob@ext.com", "2024-05-01T10:00:00+00:00")
        _commit(repo, "README.md", "# proj\n", "alice@in.com", "2024-06-03T10:00:00+00:00")
    else:
        (repo / "src").mkdir()
        (repo / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
        (repo / "src" / "util.c").write_text("int x;\n", encoding="utf-8")
        (repo / "README.md").write_text("# proj\n", encoding="utf-8")
    return repo


@pytest.fixture
def cfg():
    return Config(ownership=OwnershipConfig(internal_authors=["@in.com"]))


def test_top_level_structure(project, cfg):
    data = build_report_data(project, config=cfg, now=NOW)
    for key in ("root", "generatedAt", "dimensions", "tables", "colors",
                "config", "files", "meta"):
        assert key in data
    assert len(data["dimensions"]) == 9
    assert len(data["files"]) == 3


def test_tables_and_indices(project, cfg):
    data = build_report_data(project, config=cfg, now=NOW)
    tables = data["tables"]
    assert "Python" in tables["fileType"]
    # 파일별 ft 인덱스가 테이블을 올바르게 가리킨다
    by_path = {f["p"]: f for f in data["files"]}
    main = by_path["src/main.py"]
    assert tables["fileType"][main["ft"]] == "Python"


def test_file_features_present(project, cfg):
    data = build_report_data(project, config=cfg, now=NOW)
    for f in data["files"]:
        for key in ("p", "ft", "pur", "lic", "loc", "bin", "rd", "ownHdr", "ac", "cm"):
            assert key in f


def test_config_serialized(project, cfg):
    data = build_report_data(project, config=cfg, now=NOW)
    c = data["config"]
    assert c["size"]["tiny_max"] == 50
    assert c["recency"]["hot_days"] == 30
    assert c["ownership"]["internal_authors"] == ["@in.com"]


def test_colors_cover_live_dimensions(project, cfg):
    data = build_report_data(project, config=cfg, now=NOW)
    colors = data["colors"]
    # live 차원의 canonical 태그가 색을 가진다
    assert "Hot" in colors["recency"]["tags"]
    assert "Single-Author" in colors["author_pattern"]["tags"]
    assert "Tiny" in colors["size"]["tags"]


@pytest.mark.skipif(not _HAS_GIT, reason="git 미설치")
def test_git_features(project, cfg):
    data = build_report_data(project, config=cfg, now=NOW)
    by_path = {f["p"]: f for f in data["files"]}
    main = by_path["src/main.py"]
    # 2024-06-01T10:00 커밋 1개 → now(6/15 00:00)까지 13일(버림), 커밋기록 1건
    assert main["rd"] == 13
    assert len(main["cm"]) == 1
    # 커밋의 작성자 id 가 authors 테이블의 alice 를 가리킨다
    author_id = main["cm"][0][1]
    assert data["tables"]["authors"][author_id] == "alice@in.com"


# ---------- HTML 렌더 ----------

def test_render_html_compressed(project, cfg):
    data = build_report_data(project, config=cfg, now=NOW)
    html = render_html(data, compress=True)
    assert html.startswith("<!DOCTYPE html>")
    assert 'id="cora2-data"' in html
    assert 'data-enc="gzip+base64"' in html
    # 자산이 인라인됐는지
    assert "CORA2L" in html  # report_logic.js
    assert "tree-viewport" in html  # report.css/html
    # 플레이스홀더가 남아있지 않아야
    for ph in ("{{CSS}}", "{{JS}}", "{{DATA}}", "{{DATA_ENC}}"):
        assert ph not in html
    # 외부 http(s) 리소스 없음(자기완결형)
    assert "http://" not in html and "https://" not in html


def test_render_html_plain(project, cfg):
    data = build_report_data(project, config=cfg, now=NOW)
    html = render_html(data, compress=False)
    assert 'data-enc=""' in html
    # 평문 JSON 임베드 영역에는 조기 종료를 일으킬 "</" 가 없어야 한다
    start = html.index('id="cora2-data"')
    end = html.index("</script>", start)
    assert "</" not in html[start:end]


def test_write_report_creates_file(project, cfg, tmp_path):
    out = tmp_path / "report.html"
    result = write_report(project, out, config=cfg, now=NOW)
    assert result == out
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "<html" in text
    assert 'id="cora2-data"' in text
