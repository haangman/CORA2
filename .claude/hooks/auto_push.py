"""Stop 훅: 작업이 끝나면 변경사항을 자동으로 커밋하고 GitHub 에 푸시한다.

- git 저장소가 아니면 통과한다.
- 변경사항이 없으면 통과한다.
- origin 원격이 설정되어 있을 때만 푸시한다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

COMMIT_MSG = (
    "chore: 자동 커밋 (Claude Code 작업 종료)\n\n"
    "\U0001f916 Generated with [Claude Code](https://claude.com/claude-code)\n\n"
    "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def main() -> int:
    if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return 0

    status = _git("status", "--porcelain").stdout
    if not status.strip():
        return 0

    _git("add", "-A")
    _git("commit", "-m", COMMIT_MSG)

    branch = _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if _git("remote", "get-url", "origin").returncode == 0 and branch:
        _git("push", "origin", branch)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
