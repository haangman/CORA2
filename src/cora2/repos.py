"""repo 매핑 해석.

프로젝트가 여러 git repo의 조합일 수 있으므로, 설정파일의 [[repo]] 항목을 근거로
스캔 루트 하위 각 폴더가 어떤 repo/branch에 속하는지 해석한다. 설정에 repo가 없으면
스캔 루트 자체가 git repo인지 자동 감지하여 단일 repo로 취급한다.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from cora2.config import Config, RepoConfig


@dataclass
class RepoInfo:
    """해석된 repo 정보."""

    name: str
    root: Path  # repo 루트 절대경로
    rel_root: str  # 스캔 루트 기준 상대경로(POSIX), 루트 자신이면 ""
    branch: str | None = None
    remote: str | None = None


def _detect_branch(repo_root: Path) -> str | None:
    """git에서 현재 브랜치명을 감지한다. 실패 시 None."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, ValueError):
        return None
    if proc.returncode != 0:
        return None
    branch = proc.stdout.strip()
    return branch or None


def _is_git_repo(path: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except (OSError, ValueError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _norm_rel(rel: str) -> str:
    """설정의 repo path를 정규화한다. '.' → '' (루트), 후행 슬래시 제거."""
    rel = rel.replace("\\", "/").strip("/")
    if rel == ".":
        return ""
    return rel


def build_repos(scan_root: str | Path, config: Config) -> list[RepoInfo]:
    """설정으로부터 RepoInfo 목록을 만든다.

    - 설정에 [[repo]]가 있으면 각 항목을 사용(branch 미지정 시 자동 감지).
    - 없으면 스캔 루트가 git repo인 경우 단일 repo로 자동 구성.
    - 둘 다 아니면 빈 목록.
    """
    root = Path(scan_root).resolve()

    if config.repos:
        return [_from_config(root, rc) for rc in config.repos]

    if _is_git_repo(root):
        return [
            RepoInfo(
                name=root.name,
                root=root,
                rel_root="",
                branch=_detect_branch(root),
            )
        ]

    return []


def _from_config(scan_root: Path, rc: RepoConfig) -> RepoInfo:
    rel = _norm_rel(rc.path)
    repo_root = (scan_root / rel).resolve() if rel else scan_root
    branch = rc.branch if rc.branch is not None else _detect_branch(repo_root)
    name = rc.name or (repo_root.name if rel else scan_root.name)
    return RepoInfo(
        name=name,
        root=repo_root,
        rel_root=rel,
        branch=branch,
        remote=rc.remote,
    )


def resolve_repo(scan_rel: str, repos: list[RepoInfo]) -> RepoInfo | None:
    """스캔 루트 기준 상대경로(POSIX)에 대해 가장 구체적인(longest-prefix) repo를 반환.

    매칭되는 repo가 없으면 None.
    """
    scan_rel = scan_rel.replace("\\", "/").strip("/")
    best: RepoInfo | None = None
    best_len = -1
    for repo in repos:
        prefix = repo.rel_root  # "" 이면 루트(모두 매칭)
        if prefix == "":
            matched = True
        else:
            matched = scan_rel == prefix or scan_rel.startswith(prefix + "/")
        if matched and len(prefix) > best_len:
            best = repo
            best_len = len(prefix)
    return best


def repo_relative(scan_rel: str, repo: RepoInfo) -> str:
    """스캔 상대경로를 repo 루트 기준 상대경로로 변환한다."""
    scan_rel = scan_rel.replace("\\", "/").strip("/")
    if repo.rel_root == "":
        return scan_rel
    if scan_rel == repo.rel_root:
        return ""
    if scan_rel.startswith(repo.rel_root + "/"):
        return scan_rel[len(repo.rel_root) + 1:]
    return scan_rel
