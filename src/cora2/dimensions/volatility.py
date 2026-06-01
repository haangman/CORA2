"""차원5: Volatility — 변동성을 분류한다(두 종류의 태그를 동시에 산출).

(a) Churn 수준: 윈도우 기간 내 커밋수/변경라인 기준 High/Medium/Low/No-Churn
(b) 개발자 구성: No-Churn 이 아닐 때, 내/외부 커밋 비율로
    Only Internal / Internal-Dominant / Mixed / External-Dominant / Only External

git 정보가 없으면 No-Churn 으로 degrade 한다.
"""

from __future__ import annotations

from cora2.context import FileContext
from cora2.dimensions.base import Dimension
from cora2.dimensions.ownership import is_internal_email


class VolatilityDimension(Dimension):
    name = "volatility"

    def tag(self, ctx: FileContext) -> list[str]:
        cfg = ctx.config.volatility

        if ctx.git is None or ctx.git.commit_count == 0:
            return ["No-Churn"]

        commits, lines = ctx.git.window(ctx.now, cfg.window_days)
        if commits == 0:
            return ["No-Churn"]

        churn = self._churn_tag(commits, lines, cfg)
        mix = self._mix_tag(ctx)
        return [churn, mix]

    @staticmethod
    def _churn_tag(commits: int, lines: int, cfg) -> str:
        # 커밋수/변경라인 각각의 버킷 중 더 높은 쪽을 채택
        if commits >= cfg.high_churn_commits or lines >= cfg.high_churn_lines:
            return "High-Churn"
        if commits >= cfg.medium_churn_commits or lines >= cfg.medium_churn_lines:
            return "Medium-Churn"
        return "Low-Churn"

    def _mix_tag(self, ctx: FileContext) -> str:
        cfg = ctx.config
        ratio_cfg = cfg.volatility.internal_dominant_ratio
        # 윈도우 내 커밋 기준 내/외부 집계
        cutoff_commits = [
            r
            for r in ctx.git.records
            if r.date >= ctx.now - _td(cfg.volatility.window_days)
        ]
        total = len(cutoff_commits)
        internal = sum(
            1 for r in cutoff_commits if is_internal_email(r.email, cfg)
        )
        ratio = internal / total
        ext_ratio = 1.0 - ratio

        if ratio == 1.0:
            return "Only Internal"
        if ext_ratio == 1.0:
            return "Only External"
        if ratio >= ratio_cfg:
            return "Internal-Dominant"
        if ext_ratio >= ratio_cfg:
            return "External-Dominant"
        return "Mixed"


def _td(days: int):
    from datetime import timedelta

    return timedelta(days=days)
