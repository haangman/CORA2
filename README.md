# CORA2

프로젝트의 소스파일을 **카테고리별로 분류**하는 CLI 도구입니다. 디렉터리를
재귀적으로 스캔해 각 파일을 카테고리(소스/테스트/설정/문서/빌드/데이터/에셋/기타)와
프로그래밍 언어로 분류하고 요약 통계를 제공합니다.

## 설치 / 실행

별도 의존성 없이 표준 라이브러리만 사용합니다. (테스트는 `pytest` 필요)

```powershell
# 소스를 경로에 추가해 실행
$env:PYTHONPATH = "src"; python -m cora2 <경로>

# 또는 editable 설치 후 cora2 명령 사용
pip install -e .
cora2 <경로>
```

## 사용법

```text
python -m cora2 <경로>                  # 카테고리/언어 요약 출력
python -m cora2 <경로> --json           # JSON 요약
python -m cora2 <경로> --list           # 파일별 분류 결과
python -m cora2 <경로> --group category # 카테고리별 묶음
python -m cora2 <경로> --group language # 언어별 묶음
```

### 예시 출력

```text
루트: .
전체 파일: 8

[카테고리별]
  source         4
  config         2
  test           2

[언어별]
  Python         6
```

## 분류 규칙

우선순위: **테스트 > 문서 > 빌드 > 설정 > 데이터 > 에셋 > 소스 > 기타**

- **test**: 경로에 `tests`/`spec` 등이 있거나 `test_`/`_test` 접두·접미사, `.test.`/`.spec.` 패턴
- **documentation**: `.md`, `.rst`, `.adoc`, `.txt`
- **build**: `Dockerfile`, `Makefile`, `setup.py`, `pom.xml` 등
- **config**: `.yml`, `.toml`, `.gitignore`, `package.json` 등
- **data**: `.csv`, `.json`, `.xml`, `.parquet` 등
- **asset**: 이미지/미디어/폰트
- **source**: 알려진 언어 확장자
- **other**: 그 외

`.git`, `node_modules`, `__pycache__`, `.venv`, `dist`, `build` 등은 스캔에서 제외됩니다.

## 개발

```powershell
python -m pytest        # 전체 테스트
```

기여 워크플로와 자동화 규칙은 [CLAUDE.md](./CLAUDE.md)를 참고하세요.
