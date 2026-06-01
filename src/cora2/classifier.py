"""소스파일 분류 핵심 로직.

파일을 확장자와 경로 패턴을 기준으로 카테고리(소스/테스트/설정/문서 등)와
프로그래밍 언어로 분류한다.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Category(str, Enum):
    """파일이 속하는 최상위 카테고리."""

    SOURCE = "source"
    TEST = "test"
    CONFIG = "config"
    DOCUMENTATION = "documentation"
    BUILD = "build"
    DATA = "data"
    ASSET = "asset"
    OTHER = "other"


# 확장자 -> 언어 이름. 언어 통계 및 SOURCE 판정에 사용한다.
LANGUAGE_BY_EXT: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".scala": "Scala",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".r": "R",
    ".dart": "Dart",
    ".lua": "Lua",
    ".vue": "Vue",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
    ".sass": "CSS",
    ".less": "CSS",
}

# 문서 확장자
DOC_EXTS = {".md", ".rst", ".adoc", ".txt"}

# 데이터 확장자
DATA_EXTS = {".csv", ".tsv", ".json", ".jsonl", ".xml", ".parquet", ".xlsx", ".db", ".sqlite"}

# 에셋(미디어/폰트) 확장자
ASSET_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".bmp",
    ".mp3", ".mp4", ".wav", ".mov", ".woff", ".woff2", ".ttf", ".otf", ".eot",
}

# 설정 파일 확장자
CONFIG_EXTS = {".yml", ".yaml", ".toml", ".ini", ".cfg", ".conf", ".env", ".properties"}

# 설정으로 취급할 정확한 파일명
CONFIG_NAMES = {
    ".gitignore", ".gitattributes", ".editorconfig", ".dockerignore",
    ".prettierrc", ".eslintrc", ".flake8", ".pylintrc", "tsconfig.json",
    "package.json", "pyproject.toml", "setup.cfg", "requirements.txt",
}

# 빌드/도구 설정으로 취급할 정확한 파일명
BUILD_NAMES = {
    "dockerfile", "makefile", "cmakelists.txt", "build.gradle", "pom.xml",
    "setup.py", "rakefile", "gulpfile.js", "webpack.config.js", "vite.config.js",
    ".babelrc", "procfile",
}

# 테스트로 판정하는 경로 디렉터리명
TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs"}

# 스캔 시 기본으로 제외할 디렉터리명
DEFAULT_IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "env", ".env", "dist", "build", ".idea", ".vscode", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "target", "out", ".next", ".tox", "coverage",
    "htmlcov", ".egg-info",
}


def detect_language(path: str | Path) -> str | None:
    """파일 확장자로 프로그래밍 언어를 추정한다. 모르면 None."""
    return LANGUAGE_BY_EXT.get(Path(path).suffix.lower())


def _is_test_file(path: Path) -> bool:
    """경로/파일명 규칙으로 테스트 파일 여부를 판정한다."""
    name = path.name.lower()
    parts = {p.lower() for p in path.parts}
    if parts & TEST_DIR_NAMES:
        return True
    stem = path.stem.lower()
    if stem.startswith("test_") or stem.endswith("_test"):
        return True
    # JS/TS 관례: foo.test.ts, foo.spec.js
    if ".test." in name or ".spec." in name:
        return True
    return False


def classify_file(path: str | Path) -> Category:
    """단일 파일을 카테고리로 분류한다.

    경로 정보만 사용하며 파일 내용은 읽지 않는다. 규칙 우선순위는
    테스트 > 문서 > 빌드 > 설정 > 데이터 > 에셋 > 소스 > 기타 순이다.
    """
    p = Path(path)
    name = p.name.lower()
    ext = p.suffix.lower()

    # 1) 테스트가 가장 우선 (소스 확장자를 가질 수 있으므로)
    if _is_test_file(p):
        return Category.TEST

    # 2) 문서
    if ext in DOC_EXTS:
        return Category.DOCUMENTATION

    # 3) 빌드/도구 설정 (정확한 파일명)
    if name in BUILD_NAMES:
        return Category.BUILD

    # 4) 설정 (파일명 또는 확장자)
    if name in CONFIG_NAMES or ext in CONFIG_EXTS:
        return Category.CONFIG

    # 5) 데이터
    if ext in DATA_EXTS:
        return Category.DATA

    # 6) 에셋
    if ext in ASSET_EXTS:
        return Category.ASSET

    # 7) 알려진 언어면 소스
    if ext in LANGUAGE_BY_EXT:
        return Category.SOURCE

    return Category.OTHER


@dataclass
class FileEntry:
    """분류된 단일 파일 정보."""

    path: str  # 스캔 루트 기준 상대 경로 (POSIX 구분자)
    category: Category
    language: str | None = None


@dataclass
class ScanResult:
    """디렉터리 스캔 결과."""

    root: str
    entries: list[FileEntry] = field(default_factory=list)


def scan_directory(
    root: str | Path,
    ignore_dirs: set[str] | None = None,
) -> ScanResult:
    """디렉터리를 재귀 순회하며 모든 파일을 분류한다.

    `ignore_dirs`에 포함된 이름의 디렉터리는 건너뛴다(기본값 사용 시
    .git, node_modules 등 일반적인 산출물 디렉터리 제외).
    """
    root_path = Path(root)
    if not root_path.is_dir():
        raise NotADirectoryError(f"디렉터리가 아닙니다: {root}")

    ignored = DEFAULT_IGNORE_DIRS if ignore_dirs is None else ignore_dirs
    result = ScanResult(root=str(root_path))

    for current, dirnames, filenames in _walk(root_path, ignored):
        for fname in sorted(filenames):
            fpath = current / fname
            rel = fpath.relative_to(root_path).as_posix()
            result.entries.append(
                FileEntry(
                    path=rel,
                    category=classify_file(fpath),
                    language=detect_language(fpath),
                )
            )
    return result


def _walk(root: Path, ignored: set[str]):
    """os.walk와 유사하되 ignored 디렉터리를 가지치기하며 순회한다."""
    import os

    for current, dirnames, filenames in os.walk(root):
        # 제외 디렉터리는 하위 순회 대상에서 제거 (in-place)
        dirnames[:] = [d for d in dirnames if d not in ignored]
        yield Path(current), dirnames, filenames


def summarize(result: ScanResult) -> dict:
    """스캔 결과를 카테고리/언어별 집계로 요약한다."""
    by_category: dict[str, int] = {}
    by_language: dict[str, int] = {}
    for entry in result.entries:
        by_category[entry.category.value] = by_category.get(entry.category.value, 0) + 1
        if entry.language:
            by_language[entry.language] = by_language.get(entry.language, 0) + 1

    return {
        "root": result.root,
        "total_files": len(result.entries),
        "by_category": dict(sorted(by_category.items(), key=lambda kv: (-kv[1], kv[0]))),
        "by_language": dict(sorted(by_language.items(), key=lambda kv: (-kv[1], kv[0]))),
    }
