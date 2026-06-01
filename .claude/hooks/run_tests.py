"""PostToolUse 훅: 코드 파일이 수정될 때마다 pytest 를 실행한다.

테스트 실패 시 결과를 stderr 로 출력하고 exit code 2 로 종료하여
Claude Code 에 피드백한다. tests 디렉터리가 없으면 조용히 통과한다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    if not (ROOT / "tests").is_dir():
        return 0

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.run(
        [sys.executable, "-m", "pytest"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    output = (proc.stdout or "") + (proc.stderr or "")

    if proc.returncode != 0:
        print(f"pytest 실패 (exit {proc.returncode}):\n{output}", file=sys.stderr)
        return 2

    print(f"pytest 통과:\n{output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
