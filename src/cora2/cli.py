"""CORA2 명령줄 인터페이스.

사용 예:
    python -m cora2 <경로>              # 카테고리/언어 요약 출력
    python -m cora2 <경로> --json       # JSON 요약 출력
    python -m cora2 <경로> --list       # 파일별 분류 결과 출력
    python -m cora2 <경로> --group category  # 카테고리별 파일 묶음 출력
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

from cora2 import __version__
from cora2.classifier import scan_directory, summarize


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cora2",
        description="프로젝트 소스파일을 카테고리별로 분류합니다.",
    )
    parser.add_argument("path", help="스캔할 디렉터리 경로")
    parser.add_argument(
        "--json", action="store_true", help="요약을 JSON 형식으로 출력"
    )
    parser.add_argument(
        "--list", action="store_true", help="파일별 분류 결과를 모두 출력"
    )
    parser.add_argument(
        "--group",
        choices=["category", "language"],
        help="지정한 기준으로 파일을 묶어 출력",
    )
    parser.add_argument(
        "--version", action="version", version=f"cora2 {__version__}"
    )
    return parser


def _render_summary(summary: dict) -> str:
    lines = [
        f"루트: {summary['root']}",
        f"전체 파일: {summary['total_files']}",
        "",
        "[카테고리별]",
    ]
    for cat, count in summary["by_category"].items():
        lines.append(f"  {cat:<14} {count}")
    if summary["by_language"]:
        lines.append("")
        lines.append("[언어별]")
        for lang, count in summary["by_language"].items():
            lines.append(f"  {lang:<14} {count}")
    return "\n".join(lines)


def _render_list(entries) -> str:
    lines = []
    for e in entries:
        lang = e.language or "-"
        lines.append(f"{e.category.value:<14} {lang:<12} {e.path}")
    return "\n".join(lines)


def _render_group(entries, key: str) -> str:
    groups: dict[str, list[str]] = defaultdict(list)
    for e in entries:
        if key == "category":
            groups[e.category.value].append(e.path)
        else:
            groups[e.language or "(unknown)"].append(e.path)
    lines = []
    for name in sorted(groups):
        lines.append(f"[{name}] ({len(groups[name])})")
        for path in groups[name]:
            lines.append(f"  {path}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = scan_directory(args.path)
    except (NotADirectoryError, FileNotFoundError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summarize(result), ensure_ascii=False, indent=2))
    elif args.list:
        print(_render_list(result.entries))
    elif args.group:
        print(_render_group(result.entries, args.group))
    else:
        print(_render_summary(summarize(result)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
