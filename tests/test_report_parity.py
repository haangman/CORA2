"""JS↔Python 재태깅 패리티 테스트.

report_logic.js(브라우저 재태깅 로직)가 Python 차원 로직과 동일한 태그를 내는지
무작위 피처 벡터로 검증한다. node 가 없으면 스킵한다. 슬라이더로 조절되는 수치 차원
(size/recency/author_pattern/volatility)의 드리프트를 방지하는 것이 목적이다.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from cora2.config import Config, OwnershipConfig
from cora2.gitinfo import CommitRec, GitFileStats
from cora2.report import ASSET_DIR, _config_to_dict
from cora2.dimensions.author_pattern import AuthorPatternDimension
from cora2.dimensions.recency import RecencyDimension
from cora2.dimensions.size import SizeDimension
from cora2.dimensions.volatility import VolatilityDimension

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node 미설치")

NOW = datetime(2024, 6, 15, tzinfo=timezone.utc)
RUNNER = Path(__file__).parent / "parity_runner.cjs"
LOGIC = ASSET_DIR / "report_logic.js"


def _cfg() -> Config:
    # 내부 작성자: '@in' 으로 끝나는 이메일
    return Config(ownership=OwnershipConfig(internal_authors=["@in"]))


def _gfs(records: list[CommitRec]) -> GitFileStats:
    return GitFileStats(path="f", records=records)


def _build_vectors(cfg: Config):
    """무작위 벡터 + 각 벡터에 대한 Python 기대 태그를 만든다."""
    rng = random.Random(20240615)
    vectors = []
    expected = []

    size_dim, rec_dim, ap_dim, vol_dim = (
        SizeDimension(), RecencyDimension(), AuthorPatternDimension(), VolatilityDimension(),
    )

    # size
    for _ in range(120):
        loc = rng.choice([None] + list(range(0, 3000, 7)))
        ctx = SimpleNamespace(line_count=loc, config=cfg)
        expected.append(size_dim.tag(ctx))
        vectors.append({"kind": "size", "loc": loc})

    # recency
    for _ in range(120):
        rd = rng.randint(0, 1500)
        date = NOW - timedelta(days=rd)
        gfs = _gfs([CommitRec("s", "a@in", date, 1, 0)])
        ctx = SimpleNamespace(git=gfs, now=NOW, config=cfg, abs_path=Path("x"))
        expected.append(rec_dim.tag(ctx))
        # Python 의 경과일과 동일하게 산출
        rd_days = (NOW - date).days
        vectors.append({"kind": "recency", "rd": rd_days})

    # author_pattern
    for _ in range(120):
        n = rng.randint(1, 6)
        recs = []
        ac = []
        for i in range(n):
            count = rng.randint(1, 12)
            email = f"u{i}@x"
            for _ in range(count):
                recs.append(CommitRec("s", email, NOW, 1, 0))
            ac.append([i, count])
        ctx = SimpleNamespace(git=_gfs(recs), now=NOW, config=cfg)
        expected.append(ap_dim.tag(ctx))
        vectors.append({"kind": "author", "ac": ac})

    # volatility
    for _ in range(150):
        n = rng.randint(0, 8)
        recs = []
        cm = []
        internal_ids = []
        for i in range(n):
            days = rng.randint(0, 600)
            internal = rng.random() < 0.5
            email = "x@in" if internal else "x@ext"
            lines = rng.randint(0, 3000)
            recs.append(CommitRec("s", email, NOW - timedelta(days=days), lines, 0))
            cm.append([days, i, lines])
            if internal:
                internal_ids.append(i)
        ctx = SimpleNamespace(git=_gfs(recs), now=NOW, config=cfg)
        expected.append(vol_dim.tag(ctx))
        vectors.append({"kind": "vol", "cm": cm, "internalIds": internal_ids})

    return vectors, expected


def test_js_python_parity(tmp_path):
    cfg = _cfg()
    vectors, expected = _build_vectors(cfg)

    payload = {"cfg": _config_to_dict(cfg), "vectors": vectors}
    inp = tmp_path / "vectors.json"
    inp.write_text(json.dumps(payload), encoding="utf-8")

    proc = subprocess.run(
        ["node", str(RUNNER), str(LOGIC), str(inp)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stderr
    js_result = json.loads(proc.stdout)

    assert len(js_result) == len(expected)
    mismatches = [
        (i, vectors[i], expected[i], js_result[i])
        for i in range(len(expected))
        if expected[i] != js_result[i]
    ]
    assert not mismatches, f"{len(mismatches)}건 불일치: {mismatches[:5]}"
