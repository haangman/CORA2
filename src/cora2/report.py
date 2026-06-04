"""HTML 리포트용 데이터 빌드.

`iter_contexts` 로 파일별 컨텍스트를 한 번 만든 뒤,
- 범주형 차원(file_type/purpose/license/dummy)은 태그를 그대로 산출(생성 시 고정)
- 수치/규칙 기반 차원(size/recency/author_pattern/volatility/ownership)은 브라우저에서
  실시간 재계산할 수 있도록 **원시 피처**(LOC, 최종수정 경과일, 커밋기록, 작성자 분포,
  ownership 헤더 신호)를 추출
하여 컴팩트한 임베드 데이터(dict)를 만든다.
"""

from __future__ import annotations

import base64
import csv
import gzip
import io
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from cora2.colors import CANONICAL_TAGS, build_colors
from cora2.config import Config
from cora2.context import FileContext
from cora2.dimensions.author_pattern import AuthorPatternDimension
from cora2.dimensions.dummy import DummyDimension
from cora2.dimensions.file_type import FileTypeDimension
from cora2.dimensions.license import LicenseDimension
from cora2.dimensions.ownership import OwnershipDimension, _COPYRIGHT
from cora2.dimensions.purpose import PurposeDimension
from cora2.dimensions.recency import RecencyDimension
from cora2.dimensions.size import SizeDimension
from cora2.dimensions.volatility import VolatilityDimension
from cora2.tagger import iter_contexts

# 파일당 임베드할 커밋 기록 상한(초대형 히스토리 보호)
COMMIT_CAP = 500

# JS 가 실시간 재계산하는 차원(범례 색을 canonical 로 시드)
LIVE_DIMENSIONS = ["ownership", "volatility", "recency", "author_pattern", "size"]

DIMENSIONS = [
    "file_type", "purpose", "ownership", "license",
    "volatility", "recency", "author_pattern", "size", "dummy",
]


class _Interner:
    """문자열 → 정수 id 인덱스 테이블."""

    def __init__(self) -> None:
        self._map: dict[str, int] = {}
        self.items: list[str] = []

    def intern(self, value: str) -> int:
        idx = self._map.get(value)
        if idx is None:
            idx = len(self.items)
            self._map[value] = idx
            self.items.append(value)
        return idx


def _ownership_header_signal(ctx: FileContext) -> int:
    """ownership 헤더 신호: 0 none / 1 internal-entity / 2 copyright."""
    head = ctx.head(2048)
    if not head:
        return 0
    lowered = head.lower()
    for entity in ctx.config.ownership.internal_entities:
        if entity.lower() in lowered:
            return 1
    if _COPYRIGHT.search(head):
        return 2
    return 0


def _config_to_dict(cfg: Config) -> dict:
    """JS 가 사용할 설정값(임계치/규칙)을 JSON 가능 dict 로 직렬화."""
    return {
        "size": asdict(cfg.size),
        "recency": asdict(cfg.recency),
        "author_pattern": asdict(cfg.author_pattern),
        "volatility": asdict(cfg.volatility),
        "ownership": {
            "internal_authors": list(cfg.ownership.internal_authors),
            "internal_entities": list(cfg.ownership.internal_entities),
            "external_paths": list(cfg.ownership.external_paths),
        },
    }


def _all_dimensions() -> list:
    """리포트는 enabled 설정과 무관하게 9개 차원 전부를 DIMENSIONS 순서로 산출한다."""
    return [
        FileTypeDimension(), PurposeDimension(), OwnershipDimension(),
        LicenseDimension(), VolatilityDimension(), RecencyDimension(),
        AuthorPatternDimension(), SizeDimension(), DummyDimension(),
    ]


def _raw_record(ctx: FileContext, now: datetime, dims: list) -> dict:
    """파일 하나의 순수 추출(인터닝 없음): 9차원 최종 태그 + 원시 피처."""
    tags = {dim.name: dim.tag(ctx) for dim in dims}
    authors: list[tuple[str, int]] = []
    commits: list[tuple[int, str, int]] = []
    commit_count = 0
    capped = False
    if ctx.git is not None and ctx.git.commit_count > 0:
        commit_count = ctx.git.commit_count
        authors = [(email, count) for email, count in ctx.git.authors.items()]
        records = ctx.git.records
        if len(records) > COMMIT_CAP:
            capped = True
            records = sorted(records, key=lambda r: r.date, reverse=True)[:COMMIT_CAP]
        for r in records:
            days = (now - r.date).days
            commits.append((max(0, days), r.email, r.added + r.deleted))
    return {
        "path": ctx.scan_rel,
        "repo": ctx.repo.name if ctx.repo else None,
        "tags": tags,
        "loc": ctx.line_count,
        "bin": ctx.is_binary,
        "rd": _recency_days(ctx, now),
        "ownHdr": _ownership_header_signal(ctx),
        "authors": authors,
        "commits": commits,
        "commit_count": commit_count,
        "capped": capped,
    }


def build_outputs(
    root: str | Path,
    config: Config | None = None,
    now: datetime | None = None,
) -> dict:
    """컨텍스트를 1회만 순회해 HTML 임베드 데이터와 JSON/CSV 행을 함께 만든다.

    반환: {root, generatedAt, dimensions, data(HTML용), rows(내보내기용), summary}.
    """
    cfg = config or Config()
    now = now or datetime.now(timezone.utc)
    root_path = Path(root)
    dims = _all_dimensions()

    file_type_tbl = _Interner()
    purpose_tbl = _Interner()
    license_tbl = _Interner()
    author_tbl = _Interner()

    # 범례 색을 위한 차원별 관측 태그 (live 차원은 canonical 로 시드)
    observed: dict[str, set] = {d: set(CANONICAL_TAGS.get(d, [])) for d in DIMENSIONS}

    files: list[dict] = []   # HTML 임베드용
    rows: list[dict] = []    # JSON/CSV용
    summary: dict[str, dict] = {}
    commit_capped = 0

    for ctx in iter_contexts(root_path, cfg, now):
        rec = _raw_record(ctx, now, dims)
        tags = rec["tags"]
        ft = tags["file_type"][0]
        purposes = tags["purpose"]
        lic = tags["license"][0]
        dummy = tags["dummy"][0]

        for dim, ts in tags.items():
            bucket = summary.setdefault(dim, {})
            for t in ts:
                bucket[t] = bucket.get(t, 0) + 1
                observed.setdefault(dim, set()).add(t)

        frec = {
            "p": rec["path"],
            "repo": rec["repo"],
            "ft": file_type_tbl.intern(ft),
            "pur": [purpose_tbl.intern(p) for p in purposes],
            "lic": license_tbl.intern(lic),
            "dummy": dummy,
            "loc": rec["loc"],
            "bin": rec["bin"],
            "rd": rec["rd"],
            "ownHdr": rec["ownHdr"],
        }
        if rec["authors"]:
            frec["ac"] = [[author_tbl.intern(e), c] for e, c in rec["authors"]]
            frec["cm"] = [[d, author_tbl.intern(e), ln] for d, e, ln in rec["commits"]]
        else:
            frec["ac"] = []
            frec["cm"] = []
        if rec["capped"]:
            commit_capped += 1
        files.append(frec)

        rows.append({
            "path": rec["path"],
            "repo": rec["repo"],
            "tags": tags,
            "features": {
                "loc": rec["loc"],
                "recency_days": rec["rd"],
                "commits": rec["commit_count"],
                "authors": len(rec["authors"]),
            },
        })

    colors = build_colors({d: sorted(s) for d, s in observed.items()})
    summary = {
        dim: dict(sorted(b.items(), key=lambda kv: (-kv[1], kv[0])))
        for dim, b in summary.items()
    }

    data = {
        "root": str(root_path),
        "generatedAt": now.isoformat(),
        "dimensions": DIMENSIONS,
        "liveDimensions": LIVE_DIMENSIONS,
        "tables": {
            "fileType": file_type_tbl.items,
            "purpose": purpose_tbl.items,
            "license": license_tbl.items,
            "authors": author_tbl.items,
        },
        "colors": colors,
        "config": _config_to_dict(cfg),
        "files": files,
        "meta": {"commitCap": COMMIT_CAP, "commitCappedFiles": commit_capped},
    }
    return {
        "root": str(root_path),
        "generatedAt": now.isoformat(),
        "dimensions": DIMENSIONS,
        "data": data,
        "rows": rows,
        "summary": summary,
    }


def build_report_data(
    root: str | Path,
    config: Config | None = None,
    now: datetime | None = None,
) -> dict:
    """리포트 HTML 에 임베드할 데이터 dict 를 만든다(build_outputs 에 위임)."""
    return build_outputs(root, config=config, now=now)["data"]


def _recency_days(ctx: FileContext, now: datetime) -> int | None:
    """최종 수정 경과일(없으면 None). RecencyDimension 의 판정과 동일한 기준."""
    last = RecencyDimension._last_modified(ctx)
    if last is None:
        return None
    return (now - last).days


# ---------- HTML 렌더 ----------

ASSET_DIR = Path(__file__).parent / "report_assets"


def _read_asset(name: str) -> str:
    return (ASSET_DIR / name).read_text(encoding="utf-8")


def render_html(data: dict, compress: bool = True) -> str:
    """임베드 데이터를 자기완결형 단일 HTML 문자열로 렌더한다."""
    template = _read_asset("report.html")
    css = _read_asset("report.css")
    js = _read_asset("report_logic.js") + "\n" + _read_asset("report.js")

    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if compress:
        raw = gzip.compress(payload.encode("utf-8"))
        embed = base64.b64encode(raw).decode("ascii")
        enc = "gzip+base64"
    else:
        # 평문 JSON 임베드 시 </script> 조기 종료 방지
        embed = payload.replace("</", "<\\/")
        enc = ""

    html = template.replace("{{CSS}}", css)
    html = html.replace("{{DATA_ENC}}", enc)
    html = html.replace("{{DATA}}", embed)
    # JS 는 마지막에 치환(다른 자산이 '{{JS}}' 를 포함할 가능성 차단)
    html = html.replace("{{JS}}", js)
    return html


def write_report(
    root: str | Path,
    output: str | Path,
    config: Config | None = None,
    now: datetime | None = None,
    compress: bool = True,
) -> Path:
    """HTML 리포트만 생성해 output 경로에 기록하고 그 경로를 반환한다."""
    data = build_report_data(root, config=config, now=now)
    html = render_html(data, compress=compress)
    out = Path(output)
    out.write_text(html, encoding="utf-8")
    return out


# ---------- JSON / CSV 내보내기 ----------

# CSV 의 차원 뒤에 붙는 피처 컬럼
_FEATURE_COLUMNS = ["loc", "recency_days", "commits", "authors"]


def to_json(outputs: dict) -> str:
    """build_outputs 결과를 내보내기용 JSON 문자열로 변환한다."""
    payload = {
        "root": outputs["root"],
        "generatedAt": outputs["generatedAt"],
        "dimensions": outputs["dimensions"],
        "files": [
            {
                "path": r["path"],
                "repo": r["repo"],
                "tags": r["tags"],
                "features": r["features"],
            }
            for r in outputs["rows"]
        ],
        "summary": outputs["summary"],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def to_csv(outputs: dict) -> str:
    """build_outputs 결과를 CSV 문자열로 변환한다(다중값 차원은 '; ' join)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    dims = outputs["dimensions"]
    writer.writerow(["path", "repo", *dims, *_FEATURE_COLUMNS])
    for r in outputs["rows"]:
        row = [r["path"], r["repo"] or ""]
        for dim in dims:
            row.append("; ".join(r["tags"].get(dim, [])))
        f = r["features"]
        row.append("" if f["loc"] is None else f["loc"])
        row.append("" if f["recency_days"] is None else f["recency_days"])
        row.append(f["commits"])
        row.append(f["authors"])
        writer.writerow(row)
    return buf.getvalue()


def write_reports(
    root: str | Path,
    output: str | Path,
    config: Config | None = None,
    now: datetime | None = None,
    compress: bool = True,
) -> dict[str, Path]:
    """HTML + JSON + CSV 를 같은 stem 으로 생성하고 경로 dict 를 반환한다."""
    outputs = build_outputs(root, config=config, now=now)

    out_html = Path(output)
    out_html.write_text(render_html(outputs["data"], compress=compress), encoding="utf-8")

    out_json = out_html.with_suffix(".json")
    out_json.write_text(to_json(outputs), encoding="utf-8")

    out_csv = out_html.with_suffix(".csv")
    # Excel 한글 호환: UTF-8 BOM, csv 의 \r\n 보존(newline="")
    out_csv.write_text(to_csv(outputs), encoding="utf-8-sig", newline="")

    return {"html": out_html, "json": out_json, "csv": out_csv}
