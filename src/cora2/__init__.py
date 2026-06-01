"""CORA2 — 프로젝트 소스파일을 9개 차원으로 태깅·분류하는 도구."""

from cora2.classifier import (
    Category,
    classify_file,
    detect_language,
    scan_directory,
    summarize,
)
from cora2.config import Config, find_and_load, load_config
from cora2.models import FileTags, TagReport
from cora2.tagger import tag_directory

__version__ = "0.2.0"

__all__ = [
    # 기존 분류 API
    "Category",
    "classify_file",
    "detect_language",
    "scan_directory",
    "summarize",
    # 태깅 API
    "Config",
    "load_config",
    "find_and_load",
    "FileTags",
    "TagReport",
    "tag_directory",
    "__version__",
]
