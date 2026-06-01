"""파일 단위 컨텍스트.

각 차원 태거가 판정에 필요한 정보를 한곳에 모은 객체. 파일 내용/LOC는 실제로
필요할 때 한 번만 읽도록 지연(lazy) 처리한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from cora2.config import Config
from cora2.gitinfo import GitFileStats
from cora2.repos import RepoInfo

# 바이너리 판정을 위해 읽는 선두 바이트 수
_SNIFF_BYTES = 4096
# 내용을 읽을 최대 바이트(거대 파일 보호)
_MAX_READ_BYTES = 2_000_000


@dataclass
class FileContext:
    """차원 태거에 전달되는 파일 컨텍스트."""

    abs_path: Path
    scan_rel: str  # 스캔 루트 기준 상대경로(POSIX)
    config: Config
    now: datetime
    repo: RepoInfo | None = None
    repo_rel: str | None = None
    git: GitFileStats | None = None

    # 내부 캐시
    _loaded: bool = field(default=False, repr=False)
    _text: str | None = field(default=None, repr=False)
    _is_binary: bool = field(default=False, repr=False)
    _size_bytes: int | None = field(default=None, repr=False)

    @property
    def name(self) -> str:
        return self.abs_path.name

    @property
    def ext(self) -> str:
        return self.abs_path.suffix.lower()

    @property
    def size_bytes(self) -> int:
        if self._size_bytes is None:
            try:
                self._size_bytes = self.abs_path.stat().st_size
            except OSError:
                self._size_bytes = 0
        return self._size_bytes

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            raw = self.abs_path.read_bytes()[:_MAX_READ_BYTES]
        except OSError:
            self._text = None
            self._is_binary = False
            return
        # NUL 바이트가 있으면 바이너리로 간주
        if b"\x00" in raw[:_SNIFF_BYTES]:
            self._is_binary = True
            self._text = None
            return
        self._text = raw.decode("utf-8", errors="replace")

    @property
    def is_binary(self) -> bool:
        self._load()
        return self._is_binary

    @property
    def text(self) -> str | None:
        """파일 텍스트. 바이너리면 None."""
        self._load()
        return self._text

    def head(self, n: int = 4096) -> str:
        """파일 선두 일부 텍스트(헤더 스캔용). 바이너리면 빈 문자열."""
        t = self.text
        return t[:n] if t else ""

    @property
    def line_count(self) -> int | None:
        """LOC(줄 수). 바이너리면 None."""
        t = self.text
        if t is None:
            return None
        if t == "":
            return 0
        # 마지막 줄에 개행이 없어도 한 줄로 카운트
        return t.count("\n") + (0 if t.endswith("\n") else 1)
