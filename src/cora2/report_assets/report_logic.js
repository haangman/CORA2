/* CORA2 리포트 — 순수 재태깅 로직 (DOM 비의존).
 * Python 의 dimensions/*.py 와 1:1 미러링한다.
 * 노드 패리티 테스트가 이 파일을 require 해 Python 결과와 비교한다.
 */
(function (global) {
  "use strict";

  // ownership.is_internal_email 미러: '@domain'은 접미 일치, 그 외 정확 일치
  function isInternalEmail(email, internalAuthors) {
    email = (email || "").toLowerCase();
    for (const pat of internalAuthors || []) {
      const p = String(pat).toLowerCase();
      if (p.startsWith("@")) {
        if (email.endsWith(p)) return true;
      } else if (email === p) {
        return true;
      }
    }
    return false;
  }

  // 차원8 size (LOC). loc===null → unknown
  function sizeTag(loc, c) {
    if (loc === null || loc === undefined) return ["unknown"];
    if (loc <= c.tiny_max) return ["Tiny"];
    if (loc <= c.small_max) return ["Small"];
    if (loc <= c.medium_max) return ["Medium"];
    if (loc <= c.large_max) return ["Large"];
    return ["Massive"];
  }

  // 차원6 recency. rd(경과일)===null → unknown
  function recencyTag(rd, c) {
    if (rd === null || rd === undefined) return ["unknown"];
    if (rd <= c.hot_days) return ["Hot"];
    if (rd <= c.active_days) return ["Active"];
    if (rd <= c.cooling_days) return ["Cooling"];
    if (rd <= c.stable_days) return ["Stable"];
    return ["Dormant"];
  }

  // 차원7 author_pattern. ac: [[authorId,count],...]
  function authorPatternTag(ac, c) {
    if (!ac || ac.length === 0) return ["unknown"];
    const counts = ac.map((x) => x[1]).sort((a, b) => b - a);
    const distinct = counts.length;
    const total = counts.reduce((a, b) => a + b, 0);
    const top1 = counts[0] / total;
    const top3 = counts.slice(0, 3).reduce((a, b) => a + b, 0) / total;
    if (distinct === 1 || top1 >= c.single_ratio) return ["Single-Author"];
    if (distinct <= c.few_max || top3 >= c.few_ratio) return ["Few-Author"];
    return ["Shared"];
  }

  // 차원5 volatility. cm: [[daysAgo,authorId,lines],...]; internalIds: Set
  function volatilityTag(cm, c, internalIds) {
    if (!cm || cm.length === 0) return ["No-Churn"];
    let commits = 0, lines = 0, internal = 0;
    for (const [days, aid, ln] of cm) {
      if (days <= c.window_days) {
        commits += 1;
        lines += ln;
        if (internalIds.has(aid)) internal += 1;
      }
    }
    if (commits === 0) return ["No-Churn"];
    let churn;
    if (commits >= c.high_churn_commits || lines >= c.high_churn_lines) churn = "High-Churn";
    else if (commits >= c.medium_churn_commits || lines >= c.medium_churn_lines) churn = "Medium-Churn";
    else churn = "Low-Churn";

    const ratio = internal / commits;
    const ext = 1 - ratio;
    let mix;
    if (ratio === 1) mix = "Only Internal";
    else if (ext === 1) mix = "Only External";
    else if (ratio >= c.internal_dominant_ratio) mix = "Internal-Dominant";
    else if (ext >= c.internal_dominant_ratio) mix = "External-Dominant";
    else mix = "Mixed";
    return [churn, mix];
  }

  // 차원3 ownership. rec: {p, ownHdr, ac}; cfg: 전체 config; internalIds: Set
  function ownershipTag(rec, cfg, internalIds) {
    const rel = String(rec.p).replace(/\\/g, "/").replace(/^\/+/, "");
    for (let prefix of cfg.ownership.external_paths || []) {
      prefix = String(prefix).replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
      if (prefix && (rel === prefix || rel.startsWith(prefix + "/") ||
          ("/" + rel).indexOf("/" + prefix + "/") >= 0)) {
        return ["External"];
      }
    }
    if (rec.ownHdr === 1) return ["Internal"];
    if (rec.ownHdr === 2) return ["External"];
    if (rec.ac && rec.ac.length) {
      let internal = 0, total = 0;
      for (const [aid, count] of rec.ac) {
        total += count;
        if (internalIds.has(aid)) internal += count;
      }
      if (total > 0) return internal * 2 >= total ? ["Internal"] : ["External"];
    }
    return ["Unknown"];
  }

  // internalAuthors 규칙으로 authors 테이블에서 내부 작성자 id 집합 산출
  function internalAuthorIds(authorsTable, internalAuthors) {
    const s = new Set();
    authorsTable.forEach((email, id) => {
      if (isInternalEmail(email, internalAuthors)) s.add(id);
    });
    return s;
  }

  const api = {
    isInternalEmail, sizeTag, recencyTag, authorPatternTag,
    volatilityTag, ownershipTag, internalAuthorIds,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.CORA2L = api;
})(typeof window !== "undefined" ? window : globalThis);
