"""cli 모듈 통합 테스트 (classify / tag 서브커맨드)."""

from __future__ import annotations

import json

import pytest

from cora2.cli import main


@pytest.fixture
def sample_project(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test(): pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")
    return tmp_path


# ---------- classify (기존 기능) ----------

def test_classify_summary(sample_project, capsys):
    rc = main(["classify", str(sample_project)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "전체 파일: 3" in out
    assert "source" in out


def test_classify_json(sample_project, capsys):
    rc = main(["classify", str(sample_project), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["total_files"] == 3
    assert data["by_category"]["source"] == 1
    assert data["by_language"]["Python"] == 2


def test_classify_list(sample_project, capsys):
    rc = main(["classify", str(sample_project), "--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "main.py" in out


def test_classify_group_category(sample_project, capsys):
    rc = main(["classify", str(sample_project), "--group", "category"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[source]" in out
    assert "[test]" in out


def test_classify_missing_path_returns_error(capsys, tmp_path):
    rc = main(["classify", str(tmp_path / "does_not_exist")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "오류" in err


# ---------- tag (신규) ----------

def test_tag_json(sample_project, capsys):
    rc = main(["tag", str(sample_project), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["total_files"] == 3
    paths = {f["path"] for f in data["files"]}
    assert "src/main.py" in paths
    # 각 파일은 9개 차원을 가진다
    for f in data["files"]:
        assert len(f["tags"]) == 9


def test_tag_summary(sample_project, capsys):
    rc = main(["tag", str(sample_project)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[file_type]" in out
    assert "Python" in out


def test_tag_list(sample_project, capsys):
    rc = main(["tag", str(sample_project), "--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "src/main.py" in out
    assert "file_type" in out


def test_tag_dimension_filter(sample_project, capsys):
    rc = main(["tag", str(sample_project), "--dimension", "file_type,size", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    for f in data["files"]:
        assert set(f["tags"].keys()) == {"file_type", "size"}


def test_tag_unknown_dimension_errors(sample_project, capsys):
    rc = main(["tag", str(sample_project), "--dimension", "nope"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "알 수 없는 차원" in err


def test_tag_missing_config_errors(sample_project, capsys):
    rc = main(["tag", str(sample_project), "--config", str(sample_project / "nope.toml")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "오류" in err
