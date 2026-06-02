# CLAUDE.md

이 파일은 Claude Code가 이 저장소에서 작업할 때 따르는 가이드입니다.

## 프로젝트 개요

**CORA2**는 임의의 프로젝트 디렉터리를 스캔해 각 파일을 **9개의 차원으로 태깅**하고,
간단히는 **단일 카테고리로 분류**하는 Python CLI 도구입니다. 태깅은 파일 경로 + 파일
내용 + git history를 근거로 하며, 차원의 조합으로 추후 "판별(rule engine)"을 얹을 수
있게 태그 구조가 설계되어 있습니다. 프로젝트는 여러 git repo의 조합일 수 있습니다.

- 언어/런타임: **Python 3.11+** (개발 환경 3.12, `tomllib` 사용)
- 테스트: **pytest**
- 외부 런타임 의존성: 없음 (표준 라이브러리만 사용, git은 subprocess로 호출)

## 디렉터리 구조

```
CORA2/
├── src/cora2/
│   ├── __init__.py        # 공개 API 재노출, __version__
│   ├── classifier.py      # 카테고리 분류(규칙·스캔·요약) — file_type/purpose가 재사용
│   ├── config.py          # TOML 설정 로드 + 기본값 dataclass
│   ├── repos.py           # 폴더→repo/branch 매핑(longest-prefix), branch 자동감지
│   ├── gitinfo.py         # repo별 git log --numstat 1패스 파싱 → 파일별 통계
│   ├── context.py         # FileContext: 경로/내용(lazy)/LOC/git/repo/now
│   ├── models.py          # FileTags, TagReport (JSON 직렬화/요약)
│   ├── tagger.py          # 오케스트레이션: iter_contexts(공유) → tag_directory → TagReport
│   ├── report.py          # [HTML 리포트] 피처 추출 + 데이터 빌드 + render_html/write_report
│   ├── colors.py          # 차원→hue, 태그→hex 색상 매핑(리포트 임베드)
│   ├── report_assets/     # 단일 HTML로 인라인되는 원본 자산
│   │   ├── report.html    #   레이아웃 + {{CSS}}/{{JS}}/{{DATA}} 플레이스홀더
│   │   ├── report.css
│   │   ├── report_logic.js #  순수 재태깅 로직(DOM 비의존, 노드 패리티 테스트 대상)
│   │   └── report.js      #   UI: 가상화 트리/상세/리사이즈/설정 실시간 연동
│   ├── dimensions/
│   │   ├── __init__.py    # 레지스트리(build_dimensions/available_dimensions)
│   │   ├── base.py        # Dimension 인터페이스: name, tag(ctx)->list[str]
│   │   └── *.py           # 9개 차원 (아래 표)
│   ├── cli.py             # argparse 서브커맨드: classify / tag / report
│   └── __main__.py        # `python -m cora2` 진입점
├── tests/                 # classifier/config/repos/gitinfo/dimensions/tagger/cli/colors/report/report_parity
│   └── parity_runner.cjs  # 노드 패리티 러너(report_logic.js 로드)
├── .claude/
│   ├── settings.json      # 자동화 훅 설정
│   └── hooks/             # run_tests.py, auto_push.py
├── cora2.toml             # 샘플 설정 (모든 키 생략 가능, 생략 시 기본값)
├── pyproject.toml
├── README.md
└── CLAUDE.md
```

## 핵심 개념

### 카테고리 분류 (classifier.py — 기존)

- `Category` (Enum): `source`, `test`, `config`, `documentation`, `build`, `data`, `asset`, `other`
- `classify_file(path)`: 경로만으로 단일 카테고리. **우선순위: 테스트 > 문서 > 빌드 >
  설정 > 데이터 > 에셋 > 소스 > 기타.** (주의: `CMakeLists.txt`는 `.txt`라 여기선
  documentation으로 분류됨 — purpose 차원이 이를 별도 보완한다.)
- `scan_directory(root, ignore_dirs)`, `summarize(result)`.

### 9개 차원 태깅

| # | 차원(name) | 모듈 | 태그(예) | 비고 |
|---|------------|------|----------|------|
| 1 | `file_type` | file_type.py | C/C++, Python, Java, asm, Rust, CMake, Docs, Config, Shell | 확장자+파일명+shebang, 단일 |
| 2 | `purpose` | purpose.py | Develop, Build, Test, Infra, Tool, Core, Library, Config, Variant | **다중**, 경로 토큰+Category |
| 3 | `ownership` | ownership.py | Internal, External, Unknown | 경로>헤더>git author |
| 4 | `license` | license.py | GPL, MIT, Apache, SAMSUNG, 3rd party, unknown | 헤더>repo LICENSE>외부경로 |
| 5 | `volatility` | volatility.py | High/Medium/Low/No-Churn + Only Internal/Internal-Dominant/Mixed/External-Dominant/Only External | **다중**, 윈도우 커밋·라인 + 내외부비율 |
| 6 | `recency` | recency.py | Hot, Active, Cooling, Stable, Dormant | last commit(없으면 mtime) vs now |
| 7 | `author_pattern` | author_pattern.py | Single-Author, Few-Author, Shared | author 커밋 분포 |
| 8 | `size` | size.py | Tiny, Small, Medium, Large, Massive | LOC 기준 |
| 9 | `dummy` | dummy.py | dummy | 차원 추가 템플릿 |

- 모든 임계치/기준값은 `config.py`의 dataclass 기본값에 있으며 `cora2.toml`로 덮어쓴다.
- **git이 없거나 미커밋 파일**은 git 의존 차원(3 일부/5/6/7)이 Unknown/No-Churn/unknown으로 degrade.
- `tag_directory(root, config, now)`가 진입점. `now`를 주입하면 recency/volatility가 결정론적.

### 새 차원 추가 방법

1. `dimensions/<name>.py`에 `Dimension` 상속 클래스 작성(`name`, `tag(ctx)->list[str]`).
2. `dimensions/__init__.py`의 `_registry()`에 한 줄 등록.
3. 필요한 설정값은 `config.py`에 dataclass 추가 + `_apply`에서 병합, `cora2.toml`에 키 추가.
4. `tests/test_dimensions.py`에 경계값 테스트 추가.

### 인터랙티브 HTML 리포트 (report.py + report_assets)

- `cora2 report <경로> [-o out.html]` → **자기완결형 단일 HTML**. 폴더 트리(가상화),
  파일·폴더 옆 태그 색 dot/개수 배지, 클릭 시 우측 상세, 패널 리사이즈, 설정 슬라이더로
  **실시간 재분류**.
- 동작 방식: Python(`build_report_data`)이 **원시 피처**(LOC/경과일/커밋기록/작성자분포/
  ownership 헤더신호) + **범주형 태그**를 추출해 gzip+base64로 임베드 → 브라우저의
  `report_logic.js`가 슬라이더 값으로 **JS에서 재버킷**.
- **실시간 조절 가능**: size·recency·author_pattern·volatility(수치 임계치) + ownership
  (external_paths/internal_authors). **생성 시 고정**(변경하려면 재생성): file_type·purpose·license.
- **드리프트 방지**: `report_logic.js`는 Python 차원과 1:1 미러. 바꿀 때는 **양쪽 모두**
  수정하고 `tests/test_report_parity.py`(노드 패리티)로 검증. 순수 로직은 `report_logic.js`에만
  두고 `report.js`(UI)와 분리한다.
- 임베드 데이터 스키마/캡(파일당 커밋 `COMMIT_CAP=500`)은 `report.py` 상단 참고.

## 개발 워크플로 (반드시 준수)

1. **코드를 수정할 때마다 테스트를 실행한다.** 로컬에서는 `python -m pytest`.
   `.claude/hooks/run_tests.py`가 PostToolUse 훅으로 파일 편집 후 자동 실행되며,
   실패 시 결과가 피드백된다.
2. **새 동작을 추가하거나 변경하면 그에 맞는 테스트를 생성/갱신한다.**
   - 새 카테고리/규칙 → `tests/test_classifier.py`
   - 새 차원/판정 규칙 → `tests/test_dimensions.py` (경계값 포함)
   - 설정 키 변경 → `tests/test_config.py`
   - 새 CLI 옵션/출력 → `tests/test_cli.py`
   - 리포트 데이터/렌더 → `tests/test_report.py`
   - **재태깅 로직 변경 시 `report_logic.js`도 함께 수정** → `tests/test_report_parity.py`(노드)
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
$env:PYTHONPATH = "src"
# 인터랙티브 HTML 리포트
python -m cora2 report <경로> [-o out.html] [--config FILE] [--no-compress] [--open]
# 9개 차원 태깅
python -m cora2 tag <경로> [--config FILE] [--dimension file_type,size] [--json|--list]
# 단일 카테고리 분류(기존)
python -m cora2 classify <경로> [--json|--list|--group category|language]
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
