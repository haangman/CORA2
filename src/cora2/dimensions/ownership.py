"""차원3: Ownership — 원작자/유지보수 책임 소재(Internal/External)를 분류한다.

판정 우선순위:
  1) 경로 prefix (third_party/ 등 external_paths) → External
  2) 저작권 헤더의 내부 엔티티 → Internal
  3) 저작권 헤더에 다른 엔티티 표기 → External
  4) git author 의 내/외부 비율 → 다수결
  5) 판정 불가 → Unknown
"""

from __future__ import annotations

import re

from cora2.config import Config
from cora2.context import FileContext
from cora2.dimensions.base import Dimension

_COPYRIGHT = re.compile(r"copyright|\(c\)|©", re.IGNORECASE)


def is_internal_email(email: str, config: Config) -> bool:
    """이메일이 내부 작성자 규칙에 맞는지. '@domain'은 접미 일치, 그 외는 정확 일치."""
    email = email.lower()
    for pat in config.ownership.internal_authors:
        p = pat.lower()
        if p.startswith("@"):
            if email.endswith(p):
                return True
        elif email == p:
            return True
    return False


def _matches_external_path(scan_rel: str, config: Config) -> bool:
    rel = scan_rel.replace("\\", "/").lstrip("/")
    for prefix in config.ownership.external_paths:
        pfx = prefix.replace("\\", "/").lstrip("/").rstrip("/")
        if pfx and (rel == pfx or rel.startswith(pfx + "/") or f"/{pfx}/" in f"/{rel}"):
            return True
    return False


class OwnershipDimension(Dimension):
    name = "ownership"

    def tag(self, ctx: FileContext) -> list[str]:
        cfg = ctx.config

        # 1) 경로 prefix
        if _matches_external_path(ctx.scan_rel, cfg):
            return ["External"]

        # 2~3) 저작권 헤더
        head = ctx.head(2048)
        if head:
            lowered = head.lower()
            for entity in cfg.ownership.internal_entities:
                if entity.lower() in lowered:
                    return ["Internal"]
            if _COPYRIGHT.search(head):
                # 내부 엔티티가 아닌 저작권 표기 → 외부로 본다
                return ["External"]

        # 4) git author 다수결
        if ctx.git is not None and ctx.git.commit_count > 0:
            internal = sum(
                count
                for email, count in ctx.git.authors.items()
                if is_internal_email(email, cfg)
            )
            total = sum(ctx.git.authors.values())
            if total > 0:
                return ["Internal"] if internal * 2 >= total else ["External"]

        # 5) 판정 불가
        return ["Unknown"]
