"""report 모듈 테스트 (데이터 빌드 + HTML 렌더)."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone

import pytest

import csv
import io
import json as _json

from cora2.config import Config, OwnershipConfig
from cora2.report import (
    build_outputs,
    build_report_data,
    render_html,
    to_csv,
    to_json,
    write_report,
    write_reports,
)
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


# ---------- build_outputs / JSON / CSV ----------

DIMENSIONS = [
    "file_type", "purpose", "ownership", "license",
    "volatility", "recency", "author_pattern", "size", "dummy",
]


def test_build_outputs_structure(project, cfg):
    outs = build_outputs(project, config=cfg, now=NOW)
    for key in ("root", "generatedAt", "dimensions", "data", "rows", "summary"):
        assert key in outs
    assert len(outs["rows"]) == 3
    for r in outs["rows"]:
        assert set(r["tags"].keys()) == set(DIMENSIONS)
        assert set(r["features"].keys()) == {"loc", "recency_days", "commits", "authors"}
    # data 는 기존 HTML 임베드 구조 유지
    assert "files" in outs["data"] and "colors" in outs["data"]


def test_build_report_data_delegates(project, cfg):
    # build_report_data 는 build_outputs()["data"] 와 동일 구조
    data = build_report_data(project, config=cfg, now=NOW)
    assert data == build_outputs(project, config=cfg, now=NOW)["data"]


def test_to_json_tags_and_features(project, cfg):
    outs = build_outputs(project, config=cfg, now=NOW)
    obj = _json.loads(to_json(outs))
    assert obj["dimensions"] == DIMENSIONS
    assert len(obj["files"]) == 3
    by_path = {f["path"]: f for f in obj["files"]}
    main = by_path["src/main.py"]
    assert main["tags"]["file_type"] == ["Python"]
    assert "loc" in main["features"] and "commits" in main["features"]
    # summary 정합: file_type Python 카운트
    assert obj["summary"]["file_type"].get("Python") == 1


def test_json_tags_match_tag_directory(project, cfg):
    # 내보내기 태그가 tag_directory 결과와 동일해야 한다(일관성)
    outs = build_outputs(project, config=cfg, now=NOW)
    report = tag_directory(project, config=cfg, now=NOW)
    export = {r["path"]: r["tags"] for r in outs["rows"]}
    expected = {f.path: f.tags for f in report.files}
    assert export == expected


def test_to_csv_header_and_rows(project, cfg):
    outs = build_outputs(project, config=cfg, now=NOW)
    text = to_csv(outs)
    reader = list(csv.reader(io.StringIO(text)))
    header = reader[0]
    assert header == ["path", "repo", *DIMENSIONS, "loc", "recency_days", "commits", "authors"]
    assert len(reader) == 1 + 3  # 헤더 + 3파일
    rows = {row[0]: row for row in reader[1:]}
    main = rows["src/main.py"]
    # file_type 컬럼(인덱스 2) = Python
    assert main[2] == "Python"


@pytest.mark.skipif(not _HAS_GIT, reason="git 미설치")
def test_to_csv_multivalue_join(project, cfg):
    outs = build_outputs(project, config=cfg, now=NOW)
    reader = list(csv.reader(io.StringIO(to_csv(outs))))
    header = reader[0]
    vol_idx = header.index("volatility")
    rows = {row[0]: row for row in reader[1:]}
    # volatility 는 churn + mix 2개 태그 → '; ' join
    assert "; " in rows["src/main.py"][vol_idx]


def test_write_reports_creates_three_files(project, cfg, tmp_path):
    out = tmp_path / "report.html"
    paths = write_reports(project, out, config=cfg, now=NOW)
    assert paths["html"].is_file()
    assert paths["json"].is_file()
    assert paths["csv"].is_file()
    assert paths["json"].suffix == ".json"
    assert paths["csv"].suffix == ".csv"
    # CSV 는 UTF-8 BOM 으로 기록
    assert paths["csv"].read_bytes().startswith(b"\xef\xbb\xbf")
    # JSON 파싱 가능
    _json.loads(paths["json"].read_text(encoding="utf-8"))
