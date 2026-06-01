"""태깅 결과 모델.

차원→태그 매핑을 파일별로 보관하고 JSON 직렬화/요약을 제공한다. 추후 "차원 조합
판별(rule engine)"은 `FileTags.tags`를 질의하는 방식으로 이 구조 위에 얹을 수 있다.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FileTags:
    """파일 하나의 차원별 태그."""

    path: str  # 스캔 루트 기준 상대경로(POSIX)
    repo: str | None
    tags: dict[str, list[str]] = field(default_factory=dict)

    def has(self, dimension: str, tag: str) -> bool:
        """특정 차원에 특정 태그가 있는지(추후 rule engine용 헬퍼)."""
        return tag in self.tags.get(dimension, [])

    def to_dict(self) -> dict:
        return {"path": self.path, "repo": self.repo, "tags": self.tags}


@dataclass
class TagReport:
    """스캔 전체의 태깅 결과."""

    root: str
    files: list[FileTags] = field(default_factory=list)

    def summary(self) -> dict:
        """차원별 태그 빈도 집계."""
        counts: dict[str, dict[str, int]] = {}
        for ft in self.files:
            for dim, tags in ft.tags.items():
                bucket = counts.setdefault(dim, {})
                for tag in tags:
                    bucket[tag] = bucket.get(tag, 0) + 1
        # 각 차원 내에서 빈도 내림차순 정렬
        return {
            dim: dict(sorted(bucket.items(), key=lambda kv: (-kv[1], kv[0])))
            for dim, bucket in counts.items()
        }

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "total_files": len(self.files),
            "files": [f.to_dict() for f in self.files],
            "summary": self.summary(),
        }
