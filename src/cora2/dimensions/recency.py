"""차원6: Recency — 최종 수정 시점으로부터 경과 기간으로 분류한다.

git 의 마지막 커밋 날짜를 우선 사용하고, 없으면 파일시스템 mtime 으로 degrade 한다.
Hot / Active / Cooling / Stable / Dormant.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cora2.context import FileContext
from cora2.dimensions.base import Dimension


class RecencyDimension(Dimension):
    name = "recency"

    def tag(self, ctx: FileContext) -> list[str]:
        last = self._last_modified(ctx)
        if last is None:
            return ["unknown"]

        days = (ctx.now - last).days
        cfg = ctx.config.recency
        if days <= cfg.hot_days:
            return ["Hot"]
        if days <= cfg.active_days:
            return ["Active"]
        if days <= cfg.cooling_days:
            return ["Cooling"]
        if days <= cfg.stable_days:
            return ["Stable"]
        return ["Dormant"]

    @staticmethod
    def _last_modified(ctx: FileContext) -> datetime | None:
        if ctx.git is not None and ctx.git.last_date is not None:
            return ctx.git.last_date
        try:
            mtime = ctx.abs_path.stat().st_mtime
        except OSError:
            return None
        return datetime.fromtimestamp(mtime, tz=timezone.utc)
