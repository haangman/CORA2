"""cli 모듈 통합 테스트."""

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


def test_main_summary(sample_project, capsys):
    rc = main([str(sample_project)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "전체 파일: 3" in out
    assert "source" in out


def test_main_json(sample_project, capsys):
    rc = main([str(sample_project), "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["total_files"] == 3
    assert data["by_category"]["source"] == 1
    assert data["by_language"]["Python"] == 2


def test_main_list(sample_project, capsys):
    rc = main([str(sample_project), "--list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "main.py" in out
    assert "test_main.py" in out


def test_main_group_category(sample_project, capsys):
    rc = main([str(sample_project), "--group", "category"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "[source]" in out
    assert "[test]" in out


def test_main_missing_path_returns_error(capsys, tmp_path):
    missing = tmp_path / "does_not_exist"
    rc = main([str(missing)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "오류" in err
