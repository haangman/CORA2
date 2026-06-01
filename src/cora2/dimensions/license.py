"""차원4: License Type — 적용된 오픈소스/사내 라이선스를 분류한다.

판정 순서:
  1) 파일 헤더에서 config 라이선스 패턴(SPDX 등) 매칭
  2) 헤더의 내부 엔티티 → internal_tag(예: SAMSUNG)
  3) repo 의 LICENSE/COPYING 파일을 패턴 매칭
  4) external_paths 하위면 "3rd party"
  5) 그 외 "unknown"
"""

from __future__ import annotations

import re

from cora2.context import FileContext
from cora2.dimensions.base import Dimension
from cora2.dimensions.ownership import _matches_external_path

_LICENSE_FILE_NAMES = ("LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING", "COPYING.txt")


class LicenseDimension(Dimension):
    name = "license"

    def __init__(self) -> None:
        # repo 루트 경로 → LICENSE 파일에서 판정한 태그(또는 None) 캐시
        self._repo_license_cache: dict[str, str | None] = {}

    def _match_patterns(self, text: str, ctx: FileContext) -> str | None:
        for pat in ctx.config.license.patterns:
            if re.search(pat.regex, text, re.IGNORECASE):
                return pat.tag
        return None

    def _repo_license(self, ctx: FileContext) -> str | None:
        if ctx.repo is None:
            return None
        key = str(ctx.repo.root)
        if key in self._repo_license_cache:
            return self._repo_license_cache[key]

        result: str | None = None
        for fname in _LICENSE_FILE_NAMES:
            lf = ctx.repo.root / fname
            if lf.is_file():
                try:
                    text = lf.read_text(encoding="utf-8", errors="replace")[:8192]
                except OSError:
                    continue
                result = self._match_patterns(text, ctx)
                if result:
                    break
        self._repo_license_cache[key] = result
        return result

    def tag(self, ctx: FileContext) -> list[str]:
        cfg = ctx.config
        head = ctx.head(4096)

        # 1) 헤더 패턴
        if head:
            matched = self._match_patterns(head, ctx)
            if matched:
                return [matched]
            # 2) 내부 엔티티
            lowered = head.lower()
            for entity in cfg.ownership.internal_entities:
                if entity.lower() in lowered:
                    return [cfg.license.internal_tag]

        # 3) repo LICENSE 파일
        repo_lic = self._repo_license(ctx)
        if repo_lic:
            return [repo_lic]

        # 4) 외부 경로면 3rd party
        if _matches_external_path(ctx.scan_rel, cfg):
            return ["3rd party"]

        # 5) 불명
        return ["unknown"]
