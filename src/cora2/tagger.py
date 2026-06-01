"""태깅 오케스트레이션.

디렉터리를 스캔해 각 파일에 대해 repo/​git 통계를 결합한 FileContext를 만들고,
활성화된 모든 차원 태거를 실행해 TagReport를 생성한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cora2.classifier import scan_directory
from cora2.config import Config
from cora2.context import FileContext
from cora2.dimensions import build_dimensions
from cora2.gitinfo import GitIndex, build_git_index
from cora2.models import FileTags, TagReport
from cora2.repos import RepoInfo, build_repos, repo_relative, resolve_repo


def tag_directory(
    root: str | Path,
    config: Config | None = None,
    now: datetime | None = None,
) -> TagReport:
    """디렉터리를 9개 차원으로 태깅한다.

    now 는 recency/volatility 의 기준 시각으로, 미지정 시 현재(UTC).
    """
    cfg = config or Config()
    now = now or datetime.now(timezone.utc)
    root_path = Path(root)

    repos = build_repos(root_path, cfg)
    git_indexes = _build_git_indexes(repos)
    dimensions = build_dimensions(cfg)

    scan = scan_directory(root_path, cfg.ignore_dirs)

    files: list[FileTags] = []
    for entry in scan.entries:
        repo = resolve_repo(entry.path, repos)
        repo_rel = repo_relative(entry.path, repo) if repo else None
        git_stats = None
        if repo is not None:
            index = git_indexes.get(str(repo.root))
            if index is not None and index.available and repo_rel is not None:
                git_stats = index.get(repo_rel)

        ctx = FileContext(
            abs_path=root_path / entry.path,
            scan_rel=entry.path,
            config=cfg,
            now=now,
            repo=repo,
            repo_rel=repo_rel,
            git=git_stats,
        )
        tags = {dim.name: dim.tag(ctx) for dim in dimensions}
        files.append(
            FileTags(path=entry.path, repo=repo.name if repo else None, tags=tags)
        )

    return TagReport(root=str(root_path), files=files)


def _build_git_indexes(repos: list[RepoInfo]) -> dict[str, GitIndex]:
    """repo 루트별 git 인덱스를 한 번씩만 만든다."""
    indexes: dict[str, GitIndex] = {}
    for repo in repos:
        key = str(repo.root)
        if key not in indexes:
            indexes[key] = build_git_index(repo.root)
    return indexes
