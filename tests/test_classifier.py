"""classifier 모듈 단위 테스트."""

from __future__ import annotations

import pytest

from cora2.classifier import (
    Category,
    classify_file,
    detect_language,
    scan_directory,
    summarize,
)


@pytest.mark.parametrize(
    "path,expected",
    [
        ("src/app/main.py", Category.SOURCE),
        ("lib/util.ts", Category.SOURCE),
        ("index.js", Category.SOURCE),
        ("styles/app.css", Category.SOURCE),
    ],
)
def test_classify_source(path, expected):
    assert classify_file(path) == expected


@pytest.mark.parametrize(
    "path",
    [
        "tests/test_main.py",
        "src/main_test.go",
        "components/Button.test.tsx",
        "spec/user.spec.js",
        "__tests__/helper.js",
    ],
)
def test_classify_test_takes_priority_over_source(path):
    # 테스트 파일은 소스 확장자를 가져도 TEST로 분류돼야 한다.
    assert classify_file(path) == Category.TEST


@pytest.mark.parametrize(
    "path,expected",
    [
        ("README.md", Category.DOCUMENTATION),
        ("docs/guide.rst", Category.DOCUMENTATION),
        ("config.yaml", Category.CONFIG),
        (".gitignore", Category.CONFIG),
        ("pyproject.toml", Category.CONFIG),
        ("Dockerfile", Category.BUILD),
        ("Makefile", Category.BUILD),
        ("data/users.csv", Category.DATA),
        ("assets/logo.png", Category.ASSET),
        ("notes.unknownext", Category.OTHER),
        ("LICENSE", Category.OTHER),
    ],
)
def test_classify_various_categories(path, expected):
    assert classify_file(path) == expected


def test_classify_is_case_insensitive_on_extension():
    assert classify_file("Main.PY") == Category.SOURCE
    assert classify_file("Photo.JPG") == Category.ASSET


def test_detect_language():
    assert detect_language("a.py") == "Python"
    assert detect_language("b.TSX") == "TypeScript"
    assert detect_language("c.unknown") is None


@pytest.fixture
def sample_project(tmp_path):
    """작은 가상 프로젝트 트리를 만든다."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "src" / "util.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("def test(): pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[x]\n", encoding="utf-8")
    # 제외돼야 하는 디렉터리
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("x\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dep.js").write_text("x\n", encoding="utf-8")
    return tmp_path


def test_scan_directory_classifies_and_prunes(sample_project):
    result = scan_directory(sample_project)
    paths = {e.path for e in result.entries}
    assert "src/main.py" in paths
    assert "tests/test_main.py" in paths
    # 제외 디렉터리의 파일은 결과에 없어야 한다.
    assert not any(p.startswith(".git/") for p in paths)
    assert not any(p.startswith("node_modules/") for p in paths)


def test_summarize_counts(sample_project):
    summary = summarize(scan_directory(sample_project))
    assert summary["total_files"] == 5  # main, util, test, README, pyproject
    assert summary["by_category"]["source"] == 2
    assert summary["by_category"]["test"] == 1
    assert summary["by_category"]["documentation"] == 1
    assert summary["by_category"]["config"] == 1
    assert summary["by_language"]["Python"] == 3


def test_scan_directory_rejects_non_directory(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        scan_directory(f)
