# CORA2

프로젝트의 소스파일을 **9개 차원으로 태깅**하고, 간단히는 **단일 카테고리로 분류**하는
CLI 도구입니다. 태깅은 **파일 경로 + 파일 내용 + git history**를 근거로 하며, 차원의
조합으로 파일을 판별하는 데 활용할 수 있습니다. 프로젝트는 여러 git repo의 조합일 수
있고, 설정파일에서 폴더↔repo/branch를 지정합니다.

## 설치 / 실행

별도 런타임 의존성 없이 표준 라이브러리만 사용합니다(Python **3.11+**, git은 선택).
테스트는 `pytest`가 필요합니다.

```powershell
# 소스를 경로에 추가해 실행
$env:PYTHONPATH = "src"; python -m cora2 tag <경로>

# 또는 editable 설치 후 cora2 명령 사용
pip install -e .
cora2 tag <경로>
```

## 사용법

```text
# 리포트 생성 (HTML + JSON + CSV 항상 함께 생성)
python -m cora2 report <경로>                    # <경로>/cora2-report.{html,json,csv}
python -m cora2 report <경로> -o out.html --open # 경로 지정(out.json/out.csv 동반) + 브라우저로 열기

# 9개 차원 태깅 (터미널)
python -m cora2 tag <경로>                       # 차원별 태그 분포 요약
python -m cora2 tag <경로> --json                # 파일별 태그 JSON
python -m cora2 tag <경로> --list                # 파일별 태그 목록
python -m cora2 tag <경로> --config cora2.toml   # 설정파일 지정
python -m cora2 tag <경로> --dimension file_type,size   # 일부 차원만

# 단일 카테고리 분류 (가벼운 분류)
python -m cora2 classify <경로> [--json|--list|--group category|language]
```

## 리포트 (HTML + JSON + CSV)

`cora2 report` 는 **세 가지 형식을 같은 stem 으로 함께** 생성합니다
(`out.html` 지정 시 `out.json`, `out.csv` 동반).

- **HTML** — 아래 인터랙티브 뷰.
- **JSON** — `{root, generatedAt, dimensions, files:[{path, repo, tags{차원:[…]},
  features{loc, recency_days, commits, authors}}], summary}`.
- **CSV** — 컬럼: `path, repo, file_type, purpose, ownership, license, volatility,
  recency, author_pattern, size, dummy, loc, recency_days, commits, authors`.
  다중 태그 차원(purpose·volatility 등)은 한 셀에서 `;` 로 구분. Excel 한글 호환을 위해
  UTF-8 BOM 으로 기록됩니다.
- JSON/CSV 의 태그는 로드된 설정 기준이며 HTML 초기 상태(슬라이더 조절 전)와 동일합니다.

### 인터랙티브 HTML 뷰

HTML 은 의존성 없는 **단일 파일**입니다(더블클릭으로 열림).

- 분석한 프로젝트의 **폴더 트리**를 그대로 보여주고, 펼치고/클릭해서 탐색(수만 파일도 가상화로 부드럽게).
- 파일명 옆에 각 태그를 **그 태그 색의 원**으로, 폴더에는 **색 원 + 개수**로 표시.
- 파일 클릭 → **우측 상세 패널**(차원별 태그 + LOC/최종수정/커밋/작성자 등 원시 피처).
- 패널은 **드래그로 크기 조절**.
- 좌측 **설정 슬라이더**로 임계치를 조절하면 **실시간으로 재분류**되어 트리·요약이 즉시 갱신.
  - 실시간 조절: `size`, `recency`, `author_pattern`, `volatility`, `ownership`(경로/내부작성자).
  - 생성 시 고정(변경하려면 재생성): `file_type`, `purpose`, `license`.
- 기본은 gzip 압축 임베드. `--no-compress` 로 평문 임베드 가능.

### 예시 출력 (`tag`)

```text
루트: .
전체 파일: 36

[file_type]
  Python             30
  Config             4
  Docs               2

[purpose]
  Develop            23
  Test               7
  Config             3
...
```

## 9개 차원

| # | 차원 | 설명 | 태그(예) |
|---|------|------|----------|
| 1 | File Type | 확장자/내용 기반 언어·문서 유형 | C/C++, Python, Java, asm, Rust, CMake, Docs, Config, Shell |
| 2 | Purpose | 프로젝트 내 역할(다중 가능) | Develop, Build, Test, Infra, Tool, Core, Library, Config, Variant |
| 3 | Ownership | 원작자/유지보수 소재 | Internal, External, Unknown |
| 4 | License | 적용 라이선스 | GPL, MIT, Apache, SAMSUNG, 3rd party, unknown |
| 5 | Volatility | 변동성(churn + 개발자 구성) | High/Medium/Low/No-Churn + Only Internal/Internal-Dominant/Mixed/External-Dominant/Only External |
| 6 | Recency | 최종 수정 경과 | Hot, Active, Cooling, Stable, Dormant |
| 7 | Author Pattern | 작성자 분포 | Single-Author, Few-Author, Shared |
| 8 | Size | 크기(LOC) | Tiny, Small, Medium, Large, Massive |
| 9 | Dummy | 더미(차원 추가 템플릿) | dummy |

git 정보가 없거나 아직 커밋되지 않은 파일은 git 의존 차원(3 일부/5/6/7)이
`Unknown`/`No-Churn`/`unknown`으로 자동 degrade 됩니다.

## 설정 (cora2.toml)

모든 키는 생략 가능하며, 생략 시 코드에 정의된 기본값이 사용됩니다. 차원별 임계치
(churn/recency/size 기준 등), ownership/license 규칙, 그리고 **여러 repo 매핑**을 지정합니다.

```toml
[dimensions]
enabled = ["file_type", "purpose", "ownership", "license",
           "volatility", "recency", "author_pattern", "size", "dummy"]

[[repo]]
path = "."                 # 스캔 루트 기준 상대경로. "."은 루트 자신.
name = "cora2"
# branch 생략 시 git에서 자동 감지

[[repo]]
path = "third_party/zlib"  # 하위 폴더가 별도 repo인 경우
name = "zlib"
branch = "release"

[ownership]
internal_authors = ["@samsung.com"]
internal_entities = ["Samsung"]
external_paths = ["third_party/", "external/", "vendor/"]

[recency]
hot_days = 30
active_days = 90
# ...
```

전체 키는 저장소 루트의 [cora2.toml](./cora2.toml)을 참고하세요.

## 개발

```powershell
python -m pytest        # 전체 테스트
```

기여 워크플로와 자동화 규칙, 새 차원 추가 방법은 [CLAUDE.md](./CLAUDE.md)를 참고하세요.
