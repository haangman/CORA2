# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 따르는 가이드입니다.

## 프로젝트 개요

**CORA2**는 임의의 프로젝트 디렉터리를 스캔해 소스파일을 **카테고리별로 분류**하는
Python CLI 도구입니다. 파일 내용을 읽지 않고 경로/파일명/확장자 규칙만으로 분류하여
빠르고 결정론적으로 동작합니다.

- 언어/런타임: **Python 3.10+** (개발 환경 3.12)
- 테스트: **pytest**
- 외부 런타임 의존성: 없음 (표준 라이브러리만 사용)

## 디렉터리 구조

```
CORA2/
├── src/cora2/
│   ├── __init__.py       # 공개 API 재노출, __version__
│   ├── classifier.py     # 핵심 분류 로직 (규칙·스캔·요약)
│   ├── cli.py            # argparse 기반 CLI
│   └── __main__.py       # `python -m cora2` 진입점
├── tests/
│   ├── test_classifier.py
│   └── test_cli.py
├── .claude/
│   ├── settings.json     # 자동화 훅 설정
│   └── hooks/            # 훅 스크립트 (run_tests.py, auto_push.py)
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

## 핵심 개념

- `Category` (Enum): `source`, `test`, `config`, `documentation`, `build`, `data`, `asset`, `other`
- `classify_file(path)`: 단일 파일을 카테고리로 분류. **규칙 우선순위는
  테스트 > 문서 > 빌드 > 설정 > 데이터 > 에셋 > 소스 > 기타.** 테스트가 소스보다
  우선이라 `tests/test_main.py`는 `.py`여도 `test`로 분류된다.
- `detect_language(path)`: 확장자로 언어 추정 (`LANGUAGE_BY_EXT`).
- `scan_directory(root)`: 재귀 순회. `DEFAULT_IGNORE_DIRS`(`.git`, `node_modules` 등)는 가지치기.
- `summarize(result)`: 카테고리별/언어별 집계 dict 반환.

분류 규칙을 바꿀 때는 `classifier.py` 상단의 매핑 테이블
(`LANGUAGE_BY_EXT`, `*_EXTS`, `*_NAMES`, `TEST_DIR_NAMES`, `DEFAULT_IGNORE_DIRS`)을 수정한다.

## 개발 워크플로 (반드시 준수)

1. **코드를 수정할 때마다 테스트를 실행한다.** 로컬에서는 `python -m pytest`.
   `.claude/hooks/run_tests.py`가 PostToolUse 훅으로 파일 편집 후 자동 실행되며,
   실패 시 결과가 피드백된다.
2. **새 동작을 추가하거나 변경하면 그에 맞는 테스트를 생성/갱신한다.**
   - 새 카테고리/규칙 → `tests/test_classifier.py`에 케이스 추가
   - 새 CLI 옵션/출력 → `tests/test_cli.py`에 케이스 추가
3. **작업이 끝나면 자동으로 GitHub에 푸시된다.** `.claude/hooks/auto_push.py`가
   Stop 훅으로 변경사항을 커밋·푸시한다(변경 없으면 무동작, origin 없으면 무동작).
4. 이 `CLAUDE.md`는 구조나 규칙이 바뀌면 **함께 갱신**한다.

### 테스트 실행

```powershell
python -m pytest          # 전체 (pyproject.toml이 pythonpath=src 설정)
python -m pytest -q tests/test_classifier.py
```

### CLI 실행

```powershell
$env:PYTHONPATH = "src"; python -m cora2 <경로> [--json|--list|--group category|language]
```

## 자동화 훅 (.claude/settings.json)

| 훅 | 시점 | 동작 |
|----|------|------|
| `PostToolUse` (Edit/Write/MultiEdit/NotebookEdit) | 파일 편집 직후 | `run_tests.py` → pytest, 실패 시 exit 2로 피드백 |
| `Stop` | 응답 종료 시 | `auto_push.py` → 변경사항 자동 커밋·푸시 |

훅은 PowerShell 실행정책에 영향받지 않도록 **Python 스크립트**로 작성되어
`python <스크립트>` 형태로 호출된다. 경로 변경 시 `settings.json`의 절대경로도 갱신할 것.

## 코드 스타일

- 모든 주석·docstring은 한국어로 작성한다.
- 타입 힌트를 사용하고 `from __future__ import annotations`를 둔다.
- 외부 의존성을 추가하지 않는다(표준 라이브러리 우선). 불가피하면 `pyproject.toml`에 명시.
