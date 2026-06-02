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
import gzip
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from cora2.colors import CANONICAL_TAGS, build_colors
from cora2.config import Config
from cora2.context import FileContext
from cora2.dimensions.dummy import DummyDimension
from cora2.dimensions.file_type import FileTypeDimension
from cora2.dimensions.license import LicenseDimension
from cora2.dimensions.ownership import _COPYRIGHT
from cora2.dimensions.purpose import PurposeDimension
from cora2.dimensions.recency import RecencyDimension
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


def build_report_data(
    root: str | Path,
    config: Config | None = None,
    now: datetime | None = None,
) -> dict:
    """리포트 HTML 에 임베드할 데이터 dict 를 만든다."""
    cfg = config or Config()
    now = now or datetime.now(timezone.utc)
    root_path = Path(root)

    ft_dim = FileTypeDimension()
    pur_dim = PurposeDimension()
    lic_dim = LicenseDimension()
    dummy_dim = DummyDimension()

    file_type_tbl = _Interner()
    purpose_tbl = _Interner()
    license_tbl = _Interner()
    author_tbl = _Interner()

    # 범례 색을 위한 차원별 관측 태그 (live 차원은 canonical 로 시드)
    observed: dict[str, set] = {d: set(CANONICAL_TAGS.get(d, [])) for d in LIVE_DIMENSIONS}

    files: list[dict] = []
    commit_capped = 0

    for ctx in iter_contexts(root_path, cfg, now):
        ft = ft_dim.tag(ctx)[0]
        purposes = pur_dim.tag(ctx)
        lic = lic_dim.tag(ctx)[0]
        dummy = dummy_dim.tag(ctx)[0]

        observed.setdefault("file_type", set()).add(ft)
        observed.setdefault("purpose", set()).update(purposes)
        observed.setdefault("license", set()).add(lic)
        observed.setdefault("dummy", set()).add(dummy)

        rec = {
            "p": ctx.scan_rel,
            "repo": ctx.repo.name if ctx.repo else None,
            "ft": file_type_tbl.intern(ft),
            "pur": [purpose_tbl.intern(p) for p in purposes],
            "lic": license_tbl.intern(lic),
            "dummy": dummy,
            "loc": ctx.line_count,
            "bin": ctx.is_binary,
            "rd": _recency_days(ctx, now),
            "ownHdr": _ownership_header_signal(ctx),
        }

        # 작성자 분포 + 커밋 기록 (git 있을 때만)
        if ctx.git is not None and ctx.git.commit_count > 0:
            rec["ac"] = [
                [author_tbl.intern(email), count]
                for email, count in ctx.git.authors.items()
            ]
            records = ctx.git.records
            if len(records) > COMMIT_CAP:
                commit_capped += 1
                records = sorted(records, key=lambda r: r.date, reverse=True)[:COMMIT_CAP]
            cm = []
            for r in records:
                days = (now - r.date).days
                cm.append([max(0, days), author_tbl.intern(r.email), r.added + r.deleted])
            rec["cm"] = cm
        else:
            rec["ac"] = []
            rec["cm"] = []

        files.append(rec)

    colors = build_colors({d: sorted(s) for d, s in observed.items()})

    return {
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
    """리포트를 생성해 output 경로에 기록하고 그 경로를 반환한다."""
    data = build_report_data(root, config=config, now=now)
    html = render_html(data, compress=compress)
    out = Path(output)
    out.write_text(html, encoding="utf-8")
    return out
