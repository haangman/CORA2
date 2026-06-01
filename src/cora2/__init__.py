"""CORA2 — 프로젝트 소스파일을 카테고리별로 분류하는 도구."""

from cora2.classifier import (
    Category,
    classify_file,
    detect_language,
    scan_directory,
    summarize,
)

__version__ = "0.1.0"

__all__ = [
    "Category",
    "classify_file",
    "detect_language",
    "scan_directory",
    "summarize",
    "__version__",
]
