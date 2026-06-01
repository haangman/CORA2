"""git history 추출.

repo별로 `git log --numstat`을 **한 번** 호출해 전체 커밋을 파싱하고, 파일별로
커밋 기록(작성자/날짜/변경라인)을 모은다. volatility/recency/author_pattern/ownership
차원이 이 통계를 사용한다. git이 없거나 repo가 git이 아니면 빈 인덱스를 돌려준다
(관련 차원은 호출부에서 degrade).
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

# 커밋 구분/필드 구분에 제어문자 사용 (작성자명·이메일과 충돌 방지)
_COMMIT_MARK = "\x01"
_FIELD_SEP = "\x1f"
_LOG_FORMAT = f"format:{_COMMIT_MARK}%H{_FIELD_SEP}%ae{_FIELD_SEP}%aI"

# "pre/{old => new}/post" 형태의 rename 표기
_BRACE_RENAME = re.compile(r"\{.*? => (.*?)\}")


@dataclass
class CommitRec:
    """한 커밋이 해당 파일을 건드린 기록."""

    sha: str
    email: str
    date: datetime
    added: int
    deleted: int


@dataclass
class GitFileStats:
    """파일 하나의 git 통계."""

    path: str  # repo 루트 기준 상대경로(POSIX)
    records: list[CommitRec] = field(default_factory=list)

    @property
    def commit_count(self) -> int:
        return len(self.records)

    @property
    def authors(self) -> Counter:
        return Counter(r.email for r in self.records)

    @property
    def lines_changed(self) -> int:
        return sum(r.added + r.deleted for r in self.records)

    @property
    def first_date(self) -> datetime | None:
        return min((r.date for r in self.records), default=None)

    @property
    def last_date(self) -> datetime | None:
        return max((r.date for r in self.records), default=None)

    def window(self, now: datetime, window_days: int) -> tuple[int, int]:
        """now 기준 window_days 이내의 (커밋수, 변경라인) 합."""
        cutoff = now - timedelta(days=window_days)
        commits = 0
        lines = 0
        for r in self.records:
            if r.date >= cutoff:
                commits += 1
                lines += r.added + r.deleted
        return commits, lines


class GitIndex:
    """repo 단위 파일→통계 인덱스. git이 없으면 available=False."""

    def __init__(self, available: bool, files: dict[str, GitFileStats]):
        self.available = available
        self._files = files

    def get(self, repo_rel: str) -> GitFileStats | None:
        return self._files.get(repo_rel.replace("\\", "/").strip("/"))

    def __len__(self) -> int:
        return len(self._files)


_EMPTY = GitIndex(available=False, files={})


def _normalize_path(raw: str) -> str:
    """numstat 경로 필드를 정규화한다(rename 표기 → 결과 경로)."""
    raw = raw.strip()
    if " => " in raw:
        if "{" in raw and "}" in raw:
            raw = _BRACE_RENAME.sub(lambda m: m.group(1), raw)
            # 빈 세그먼트 정리: "a//b" → "a/b"
            raw = re.sub(r"/+", "/", raw)
        else:
            raw = raw.split(" => ", 1)[1]
    return raw.strip().strip('"').replace("\\", "/").strip("/")


def _parse_int(token: str) -> int:
    """numstat의 추가/삭제 토큰을 정수로. 바이너리('-')는 0."""
    return 0 if token == "-" else int(token)


def build_git_index(repo_root: str | Path) -> GitIndex:
    """repo 루트에서 git log를 1회 호출해 파일별 통계 인덱스를 만든다."""
    root = Path(repo_root)
    try:
        proc = subprocess.run(
            [
                "git", "-C", str(root),
                "-c", "core.quotePath=false",
                "log", "--no-merges", "--numstat",
                f"--format={_LOG_FORMAT}",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, ValueError):
        return _EMPTY

    if proc.returncode != 0:
        return _EMPTY

    files: dict[str, GitFileStats] = {}
    cur: tuple[str, str, datetime] | None = None  # (sha, email, date)

    for line in proc.stdout.splitlines():
        if not line:
            continue
        if line.startswith(_COMMIT_MARK):
            sha, email, date_s = line[1:].split(_FIELD_SEP)
            try:
                date = datetime.fromisoformat(date_s)
            except ValueError:
                cur = None
                continue
            cur = (sha, email, date)
            continue

        # numstat 라인: added\tdeleted\tpath
        if cur is None:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added, deleted, raw_path = parts[0], parts[1], "\t".join(parts[2:])
        path = _normalize_path(raw_path)
        if not path:
            continue
        rec = CommitRec(
            sha=cur[0],
            email=cur[1],
            date=cur[2],
            added=_parse_int(added),
            deleted=_parse_int(deleted),
        )
        files.setdefault(path, GitFileStats(path=path)).records.append(rec)

    return GitIndex(available=True, files=files)
