"""차원1: File Type — 확장자/내용으로 프로그래밍 언어·문서 유형을 분류한다."""

from __future__ import annotations

from cora2.classifier import CONFIG_EXTS, CONFIG_NAMES, DOC_EXTS
from cora2.context import FileContext
from cora2.dimensions.base import Dimension

# 확장자 → File Type 태그 (C/C++ 처럼 묶어서 표기)
FILETYPE_BY_EXT: dict[str, str] = {
    ".c": "C/C++", ".h": "C/C++", ".cpp": "C/C++", ".cc": "C/C++",
    ".cxx": "C/C++", ".hpp": "C/C++", ".hh": "C/C++", ".hxx": "C/C++",
    ".py": "Python", ".pyi": "Python",
    ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".rs": "Rust",
    ".go": "Go",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".scala": "Scala",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".s": "asm", ".asm": "asm",
    ".sql": "SQL",
    ".css": "CSS", ".scss": "CSS", ".sass": "CSS", ".less": "CSS",
    ".html": "HTML", ".htm": "HTML",
    ".vue": "Vue",
    ".dart": "Dart",
    ".lua": "Lua",
    ".r": "R",
}

# 대문자 .S 도 어셈블리
_ASM_NAMES_SUFFIX = (".S",)

def _from_shebang(ctx: FileContext) -> str | None:
    head = ctx.head(128)
    if not head.startswith("#!"):
        return None
    first_line = head.splitlines()[0].lower()
    if "python" in first_line:
        return "Python"
    if "bash" in first_line or "/sh" in first_line or first_line.endswith("sh") or "zsh" in first_line:
        return "Shell"
    return None


class FileTypeDimension(Dimension):
    name = "file_type"

    def tag(self, ctx: FileContext) -> list[str]:
        name = ctx.name.lower()
        ext = ctx.ext

        # 특수 파일명: CMake
        if name == "cmakelists.txt" or ext == ".cmake":
            return ["CMake"]
        # Dockerfile
        if name == "dockerfile" or name.startswith("dockerfile."):
            return ["Docker"]
        # Makefile
        if name == "makefile" or ext == ".mk":
            return ["Make"]

        # 대문자 .S (어셈블리)
        if ctx.abs_path.suffix in _ASM_NAMES_SUFFIX:
            return ["asm"]

        if ext in FILETYPE_BY_EXT:
            return [FILETYPE_BY_EXT[ext]]

        if ext in DOC_EXTS:
            return ["Docs"]

        if ext in CONFIG_EXTS or ext in {".json", ".xml"} or name in CONFIG_NAMES:
            return ["Config"]

        # 확장자 불명 시 shebang 으로 스크립트 판정
        shebang = _from_shebang(ctx)
        if shebang:
            return [shebang]

        return ["Other"]
