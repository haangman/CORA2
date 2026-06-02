"""CORA2 명령줄 인터페이스.

서브커맨드:
    cora2 classify <경로> [--json|--list|--group category|language]
        경로/확장자 규칙 기반 단일 카테고리 분류(기존 기능).
    cora2 tag <경로> [--config FILE] [--dimension a,b,..] [--json|--list]
        파일 경로/내용/git history 기반 9개 차원 태깅.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

from cora2 import __version__
from cora2.classifier import scan_directory, summarize
from cora2.config import find_and_load
from cora2.tagger import tag_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cora2",
        description="프로젝트 소스파일을 분류·태깅합니다.",
    )
    parser.add_argument("--version", action="version", version=f"cora2 {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # classify (기존 기능)
    c = sub.add_parser("classify", help="단일 카테고리로 분류(경로/확장자 규칙)")
    c.add_argument("path", help="스캔할 디렉터리 경로")
    c.add_argument("--json", action="store_true", help="요약을 JSON으로 출력")
    c.add_argument("--list", action="store_true", help="파일별 분류 결과 출력")
    c.add_argument("--group", choices=["category", "language"], help="기준별 묶음 출력")

    # tag (신규: 9개 차원)
    t = sub.add_parser("tag", help="9개 차원으로 태깅")
    t.add_argument("path", help="스캔할 디렉터리 경로")
    t.add_argument("--config", help="설정파일(.toml) 경로 (생략 시 <경로>/cora2.toml 탐색)")
    t.add_argument("--dimension", help="실행할 차원만 쉼표로 지정 (예: file_type,size)")
    t.add_argument("--json", action="store_true", help="결과를 JSON으로 출력")
    t.add_argument("--list", action="store_true", help="파일별 태그 출력")

    # report (신규: 인터랙티브 HTML)
    r = sub.add_parser("report", help="인터랙티브 HTML 리포트 생성")
    r.add_argument("path", help="스캔할 디렉터리 경로")
    r.add_argument("-o", "--output", help="출력 HTML 경로 (생략 시 <경로>/cora2-report.html)")
    r.add_argument("--config", help="설정파일(.toml) 경로 (생략 시 <경로>/cora2.toml 탐색)")
    r.add_argument("--no-compress", action="store_true", help="데이터를 평문으로 임베드(압축 끔)")
    r.add_argument("--open", action="store_true", dest="open_browser", help="생성 후 브라우저로 열기")

    return parser


# ---------- classify 렌더링 (기존) ----------

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


def _cmd_classify(args) -> int:
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


# ---------- tag 렌더링 (신규) ----------

def _render_tag_summary(report) -> str:
    summary = report.summary()
    lines = [f"루트: {report.root}", f"전체 파일: {len(report.files)}", ""]
    for dim, bucket in summary.items():
        lines.append(f"[{dim}]")
        for tag, count in bucket.items():
            lines.append(f"  {tag:<18} {count}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _render_tag_list(report) -> str:
    lines = []
    for f in report.files:
        repo = f.repo or "-"
        lines.append(f"{f.path}  (repo={repo})")
        for dim, tags in f.tags.items():
            lines.append(f"  {dim:<16} {', '.join(tags)}")
    return "\n".join(lines)


def _cmd_tag(args) -> int:
    try:
        cfg = find_and_load(args.path, args.config)
    except FileNotFoundError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    if args.dimension:
        from cora2.dimensions import available_dimensions

        valid = set(available_dimensions())
        wanted = [d.strip() for d in args.dimension.split(",") if d.strip()]
        unknown = [d for d in wanted if d not in valid]
        if unknown:
            print(f"오류: 알 수 없는 차원: {', '.join(unknown)}", file=sys.stderr)
            return 2
        cfg.enabled_dimensions = wanted

    try:
        report = tag_directory(args.path, config=cfg)
    except (NotADirectoryError, FileNotFoundError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    elif args.list:
        print(_render_tag_list(report))
    else:
        print(_render_tag_summary(report))
    return 0


def _cmd_report(args) -> int:
    from pathlib import Path

    from cora2.report import write_report

    try:
        cfg = find_and_load(args.path, args.config)
    except FileNotFoundError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    output = args.output or str(Path(args.path) / "cora2-report.html")
    try:
        out = write_report(
            args.path, output, config=cfg, compress=not args.no_compress
        )
    except (NotADirectoryError, FileNotFoundError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    print(f"리포트 생성: {out}")
    if args.open_browser:
        import webbrowser

        webbrowser.open(out.resolve().as_uri())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "classify":
        return _cmd_classify(args)
    if args.command == "tag":
        return _cmd_tag(args)
    if args.command == "report":
        return _cmd_report(args)
    parser.error("알 수 없는 명령")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
