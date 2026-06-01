"""차원2: Purpose — 파일이 프로젝트에서 수행하는 역할(다중 가능)을 분류한다.

경로의 디렉터리 토큰과 기존 Category 분류를 근거로 추론한다. 하나의 파일이 여러
purpose를 가질 수 있다(예: CMakeLists.txt → Build + Config).
"""

from __future__ import annotations

from cora2.classifier import Category, classify_file
from cora2.context import FileContext
from cora2.dimensions.base import Dimension

# 경로 토큰(소문자 디렉터리/파일명 조각) → purpose 태그
TOKEN_PURPOSE: dict[str, str] = {
    "test": "Test", "tests": "Test", "spec": "Test", "specs": "Test", "__tests__": "Test",
    "build": "Build", "cmake": "Build", "dist": "Build", "out": "Build",
    "ci": "Infra", ".github": "Infra", "docker": "Infra", "k8s": "Infra",
    "deploy": "Infra", "infra": "Infra", "terraform": "Infra", "ansible": "Infra",
    "tool": "Tool", "tools": "Tool", "script": "Tool", "scripts": "Tool",
    "lib": "Library", "libs": "Library", "library": "Library", "libraries": "Library",
    "core": "Core",
    "config": "Config", "conf": "Config", "configs": "Config", "settings": "Config",
    "variant": "Variant", "variants": "Variant", "flavor": "Variant", "flavors": "Variant",
}

# 빌드 관련 파일명/확장자 → purpose (classifier가 .txt 등으로 오분류하는 경우 보완)
BUILD_FILE_NAMES = {"cmakelists.txt", "makefile", "dockerfile"}
BUILD_FILE_EXTS = {".cmake", ".mk"}

# Category → purpose 기본 매핑
CATEGORY_PURPOSE: dict[Category, list[str]] = {
    Category.TEST: ["Test"],
    Category.BUILD: ["Build", "Config"],
    Category.CONFIG: ["Config"],
    Category.SOURCE: ["Develop"],
}


class PurposeDimension(Dimension):
    name = "purpose"

    def tag(self, ctx: FileContext) -> list[str]:
        purposes: set[str] = set()

        # 1) 경로 토큰 기반
        parts = [p.lower() for p in ctx.scan_rel.split("/")]
        for token in parts:
            if token in TOKEN_PURPOSE:
                purposes.add(TOKEN_PURPOSE[token])

        # 2) 빌드 파일명/확장자 보완
        name = ctx.name.lower()
        if name in BUILD_FILE_NAMES or name.startswith("dockerfile."):
            purposes.update(["Build", "Config"] if "cmake" in name else ["Build"])
        if ctx.ext in BUILD_FILE_EXTS:
            purposes.update(["Build", "Config"] if ctx.ext == ".cmake" else ["Build"])

        # 3) Category 기반
        category = classify_file(ctx.scan_rel)
        purposes.update(CATEGORY_PURPOSE.get(category, []))

        # 4) 소스인데 아무 역할도 못 잡았으면 Develop 기본
        if not purposes and category == Category.SOURCE:
            purposes.add("Develop")

        return sorted(purposes)
