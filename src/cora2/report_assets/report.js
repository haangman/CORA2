/* CORA2 리포트 — UI (바닐라 JS, 빌드 불필요).
 * 트리 가상화 / dot·폴더 집계 / 상세 패널 / 패널 리사이즈 / 설정 실시간 재태깅 / 범례·필터.
 * 순수 재태깅 로직은 CORA2L(report_logic.js)을 사용한다.
 */
(function () {
  "use strict";
  const L = window.CORA2L;
  const ROW_H = 24;
  const OVERSCAN = 8;

  let DATA = null;       // 임베드 데이터
  let CFG = null;        // 현재(조절 중) 설정
  let DEFAULT_CFG = null;
  let internalIds = new Set();
  let root = null;       // 트리 루트
  let allFiles = [];     // 파일 노드 배열
  let visible = [];      // 펼쳐진 가시 노드 평탄화
  let selected = null;   // 선택된 파일 노드
  let filterTerm = "";
  let disabledTags = new Set();  // "dim::tag" 비활성(범례 토글)

  // ---------- 데이터 로드/복원 ----------
  async function loadData() {
    const el = document.getElementById("cora2-data");
    const enc = el.dataset.enc || "";
    const raw = el.textContent.trim();
    if (enc === "gzip+base64") {
      const bytes = Uint8Array.from(atob(raw), (c) => c.charCodeAt(0));
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
      return JSON.parse(await new Response(stream).text());
    }
    return JSON.parse(raw);
  }

  // ---------- 트리 구성 ----------
  function buildTree() {
    root = { name: "", path: "", isDir: true, children: [], parent: null, expanded: true, depth: -1 };
    const dirMap = new Map([["", root]]);
    function getDir(path) {
      let d = dirMap.get(path);
      if (d) return d;
      const idx = path.lastIndexOf("/");
      const parentPath = idx < 0 ? "" : path.slice(0, idx);
      const name = idx < 0 ? path : path.slice(idx + 1);
      const parent = getDir(parentPath);
      d = { name, path, isDir: true, children: [], parent, expanded: false, depth: parent.depth + 1 };
      dirMap.set(path, d);
      parent.children.push(d);
      return d;
    }
    allFiles = [];
    for (const rec of DATA.files) {
      const p = rec.p;
      const idx = p.lastIndexOf("/");
      const dirPath = idx < 0 ? "" : p.slice(0, idx);
      const name = idx < 0 ? p : p.slice(idx + 1);
      const parent = getDir(dirPath);
      const node = { name, path: p, isDir: false, children: null, parent, file: rec, depth: parent.depth + 1 };
      parent.children.push(node);
      allFiles.push(node);
    }
    sortChildren(root);
  }

  function sortChildren(node) {
    if (!node.isDir) return;
    node.children.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name < b.name ? -1 : a.name > b.name ? 1 : 0;
    });
    for (const c of node.children) sortChildren(c);
  }

  // ---------- 재태깅 ----------
  function computeInternal() {
    internalIds = L.internalAuthorIds(DATA.tables.authors, CFG.ownership.internal_authors);
  }

  function tagsFor(rec) {
    const t = DATA.tables;
    return {
      file_type: [t.fileType[rec.ft]],
      purpose: rec.pur.map((i) => t.purpose[i]),
      ownership: L.ownershipTag(rec, CFG, internalIds),
      license: [t.license[rec.lic]],
      volatility: L.volatilityTag(rec.cm, CFG.volatility, internalIds),
      recency: L.recencyTag(rec.rd, CFG.recency),
      author_pattern: L.authorPatternTag(rec.ac, CFG.author_pattern),
      size: L.sizeTag(rec.loc, CFG.size),
      dummy: [rec.dummy],
    };
  }

  function retagAll() {
    computeInternal();
    for (const f of allFiles) f.tags = tagsFor(f.file);
    aggregate(root);
  }

  // 폴더 집계: dim -> tag -> count (post-order)
  function aggregate(node) {
    if (!node.isDir) {
      const agg = {};
      for (const dim in node.tags) {
        const m = (agg[dim] = {});
        for (const tag of node.tags[dim]) m[tag] = 1;
      }
      node.agg = agg;
      return agg;
    }
    const agg = {};
    for (const c of node.children) {
      const ca = aggregate(c);
      for (const dim in ca) {
        const m = agg[dim] || (agg[dim] = {});
        const cm = ca[dim];
        for (const tag in cm) m[tag] = (m[tag] || 0) + cm[tag];
      }
    }
    node.agg = agg;
    return agg;
  }

  // ---------- 가시 노드 평탄화(필터 반영) ----------
  let includeSet = null; // 필터 활성 시 표시할 노드 path 집합

  function computeFilter() {
    if (!filterTerm) { includeSet = null; return; }
    const term = filterTerm.toLowerCase();
    includeSet = new Set();
    for (const f of allFiles) {
      if (f.name.toLowerCase().includes(term)) {
        includeSet.add(f.path);
        let p = f.parent;
        while (p && p !== root) { includeSet.add(p.path); p = p.parent; }
      }
    }
  }

  function rebuildVisible() {
    visible = [];
    const filtering = !!includeSet;
    (function walk(node) {
      for (const c of node.children) {
        if (filtering && !includeSet.has(c.path)) continue;
        visible.push(c);
        if (c.isDir && (c.expanded || filtering)) walk(c);
      }
    })(root);
  }

  // ---------- 렌더링(가상화) ----------
  const viewport = () => document.getElementById("tree-viewport");
  const canvas = () => document.getElementById("tree-canvas");
  const rowsEl = () => document.getElementById("tree-rows");

  function renderVisible() {
    rebuildVisible();
    canvas().style.height = visible.length * ROW_H + "px";
    document.getElementById("tree-count").textContent = `${allFiles.length} 파일`;
    paintRows();
  }

  function paintRows() {
    const vp = viewport();
    const scrollTop = vp.scrollTop;
    const vh = vp.clientHeight;
    let start = Math.floor(scrollTop / ROW_H) - OVERSCAN;
    let end = Math.ceil((scrollTop + vh) / ROW_H) + OVERSCAN;
    start = Math.max(0, start);
    end = Math.min(visible.length, end);

    const frag = document.createDocumentFragment();
    for (let i = start; i < end; i++) frag.appendChild(rowEl(visible[i], i));
    const container = rowsEl();
    container.replaceChildren(frag);
  }

  function rowEl(node, index) {
    const div = document.createElement("div");
    div.className = "row " + (node.isDir ? "dir" : "file");
    if (selected && node === selected) div.className += " selected";
    div.style.top = index * ROW_H + "px";
    div.style.paddingLeft = 6 + node.depth * 14 + "px";

    const tw = document.createElement("span");
    tw.className = "twisty";
    tw.textContent = node.isDir ? (node.expanded || includeSet ? "▾" : "▸") : "";
    div.appendChild(tw);

    const ic = document.createElement("span");
    ic.className = "icon";
    ic.textContent = node.isDir ? "📁" : "📄";
    div.appendChild(ic);

    const lb = document.createElement("span");
    lb.className = "label";
    lb.textContent = node.name;
    div.appendChild(lb);

    const dots = document.createElement("span");
    dots.className = "dots";
    if (node.isDir) renderDirDots(dots, node);
    else renderFileDots(dots, node);
    div.appendChild(dots);

    div.addEventListener("click", (e) => onRowClick(node, e));
    return div;
  }

  function tagEnabled(dim, tag) { return !disabledTags.has(dim + "::" + tag); }
  function colorOf(dim, tag) {
    const d = DATA.colors[dim];
    return (d && d.tags[tag]) || "#888";
  }

  function renderFileDots(host, node) {
    for (const dim of DATA.dimensions) {
      for (const tag of node.tags[dim] || []) {
        if (!tagEnabled(dim, tag)) continue;
        const d = document.createElement("span");
        d.className = "dot";
        d.style.background = colorOf(dim, tag);
        d.title = dim + ": " + tag;
        host.appendChild(d);
      }
    }
  }

  function renderDirDots(host, node) {
    const agg = node.agg || {};
    for (const dim of DATA.dimensions) {
      const m = agg[dim];
      if (!m) continue;
      for (const tag in m) {
        if (!tagEnabled(dim, tag)) continue;
        const b = document.createElement("span");
        b.className = "fdot";
        b.style.background = colorOf(dim, tag);
        b.textContent = m[tag];
        b.title = dim + ": " + tag + " (" + m[tag] + ")";
        host.appendChild(b);
      }
    }
  }

  function onRowClick(node, e) {
    if (node.isDir) {
      if (!includeSet) { node.expanded = !node.expanded; renderVisible(); }
      return;
    }
    selected = node;
    renderDetail(node);
    paintRows();
  }

  // ---------- 상세 ----------
  function renderDetail(node) {
    const rec = node.file;
    const host = document.getElementById("detail-content");
    host.replaceChildren();

    const path = document.createElement("div");
    path.className = "path";
    path.innerHTML = `<strong>${esc(rec.p)}</strong>` +
      (rec.repo ? ` <span class="muted">repo=${esc(rec.repo)}</span>` : "");
    host.appendChild(path);

    for (const dim of DATA.dimensions) {
      const block = document.createElement("div");
      block.className = "detail-dim";
      const dn = document.createElement("div");
      dn.className = "dn";
      dn.textContent = dim;
      block.appendChild(dn);
      for (const tag of node.tags[dim] || []) {
        const chip = document.createElement("span");
        chip.className = "chip";
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.style.background = colorOf(dim, tag);
        chip.appendChild(dot);
        chip.appendChild(document.createTextNode(tag));
        block.appendChild(chip);
      }
      host.appendChild(block);
    }

    // 원시 피처
    const feat = document.createElement("div");
    feat.className = "feat";
    const lastDate = rec.rd === null ? "-" :
      new Date(Date.parse(DATA.generatedAt) - rec.rd * 86400000).toISOString().slice(0, 10);
    let winCommits = 0, winLines = 0;
    for (const [d, , ln] of rec.cm) if (d <= CFG.volatility.window_days) { winCommits++; winLines += ln; }
    const distinct = rec.ac.length;
    const rows = [
      ["LOC", rec.loc === null ? "(바이너리)" : rec.loc],
      ["바이너리", rec.bin ? "예" : "아니오"],
      ["최종수정 경과(일)", rec.rd === null ? "-" : rec.rd],
      ["최종수정 추정일", lastDate],
      ["커밋 수", rec.cm.length + (rec.cm.length >= DATA.meta.commitCap ? " (cap)" : "")],
      ["작성자 수", distinct],
      [`window(${CFG.volatility.window_days}일) 커밋`, winCommits],
      [`window 변경라인`, winLines],
    ];
    const tbl = document.createElement("table");
    for (const [k, v] of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${esc(k)}</td><td>${esc(String(v))}</td>`;
      tbl.appendChild(tr);
    }
    feat.appendChild(tbl);
    host.appendChild(feat);
  }

  // ---------- 요약 ----------
  function renderSummary() {
    const host = document.getElementById("summary");
    host.replaceChildren();
    const agg = root.agg || {};
    for (const dim of DATA.dimensions) {
      const m = agg[dim];
      if (!m) continue;
      const wrap = document.createElement("span");
      wrap.className = "summary-dim";
      wrap.appendChild(span("dimname", dim));
      const tags = Object.keys(m).sort((a, b) => m[b] - m[a]);
      for (const tag of tags) {
        if (!tagEnabled(dim, tag)) continue;
        const st = document.createElement("span");
        st.className = "summary-tag";
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.style.background = colorOf(dim, tag);
        st.appendChild(dot);
        st.appendChild(document.createTextNode(tag + " " + m[tag]));
        wrap.appendChild(st);
      }
      host.appendChild(wrap);
    }
  }

  // ---------- 범례 ----------
  function renderLegend() {
    const host = document.getElementById("legend");
    host.replaceChildren();
    for (const dim of DATA.dimensions) {
      const c = DATA.colors[dim];
      if (!c) continue;
      const block = document.createElement("div");
      block.className = "legend-dim";
      block.appendChild(span("ld-name", dim));
      for (const tag in c.tags) {
        const lt = document.createElement("span");
        lt.className = "legend-tag" + (tagEnabled(dim, tag) ? "" : " off");
        const dot = document.createElement("span");
        dot.className = "dot";
        dot.style.background = c.tags[tag];
        lt.appendChild(dot);
        lt.appendChild(document.createTextNode(tag));
        lt.addEventListener("click", () => {
          const key = dim + "::" + tag;
          if (disabledTags.has(key)) disabledTags.delete(key); else disabledTags.add(key);
          renderLegend(); renderSummary(); paintRows();
        });
        block.appendChild(lt);
      }
      host.appendChild(block);
    }
  }

  // ---------- 설정 패널 ----------
  const SLIDERS = [
    ["size", "size", [
      ["tiny_max", 1, 500, 1], ["small_max", 1, 1000, 1],
      ["medium_max", 1, 3000, 1], ["large_max", 1, 10000, 10],
    ]],
    ["recency", "recency", [
      ["hot_days", 1, 365, 1], ["active_days", 1, 730, 1],
      ["cooling_days", 1, 1095, 1], ["stable_days", 1, 1825, 5],
    ]],
    ["author_pattern", "author_pattern", [
      ["single_ratio", 0.5, 1, 0.01], ["few_max", 1, 10, 1],
      ["few_ratio", 0.5, 1, 0.01], ["shared_min", 2, 20, 1],
    ]],
    ["volatility", "volatility", [
      ["window_days", 7, 1825, 1],
      ["high_churn_commits", 1, 500, 1], ["medium_churn_commits", 1, 200, 1], ["low_churn_commits", 1, 50, 1],
      ["high_churn_lines", 10, 20000, 10], ["medium_churn_lines", 10, 10000, 10], ["low_churn_lines", 1, 2000, 1],
      ["internal_dominant_ratio", 0.5, 1, 0.01],
    ]],
  ];

  function buildSettings() {
    const host = document.getElementById("settings-content");
    host.replaceChildren();
    for (const [group, key, fields] of SLIDERS) {
      const g = document.createElement("div");
      g.className = "setting-group";
      g.appendChild(span("gname", group));
      for (const [field, min, max, step] of fields) {
        g.appendChild(sliderRow(key, field, min, max, step));
      }
      host.appendChild(g);
    }
    // 텍스트: ownership 리스트(실시간)
    const og = document.createElement("div");
    og.className = "setting-group";
    og.appendChild(span("gname", "ownership"));
    og.appendChild(textRow("internal_authors", "내부 작성자(쉼표)"));
    og.appendChild(textRow("external_paths", "외부 경로(쉼표)"));
    host.appendChild(og);

    // 고정 차원 안내
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = "file_type · purpose · license 는 생성 시 고정입니다(변경하려면 재생성).";
    host.appendChild(note);
  }

  function sliderRow(group, field, min, max, step) {
    const wrap = document.createElement("div");
    wrap.className = "setting";
    const lab = document.createElement("label");
    lab.appendChild(document.createTextNode(field));
    const val = document.createElement("span");
    val.className = "val";
    lab.appendChild(val);
    const input = document.createElement("input");
    input.type = "range";
    input.min = min; input.max = max; input.step = step;
    input.value = CFG[group][field];
    val.textContent = CFG[group][field];
    input.addEventListener("input", () => {
      const v = step < 1 ? parseFloat(input.value) : parseInt(input.value, 10);
      CFG[group][field] = v;
      val.textContent = v;
      scheduleRetag();
    });
    wrap.appendChild(lab);
    wrap.appendChild(input);
    return wrap;
  }

  function textRow(field, labelText) {
    const wrap = document.createElement("div");
    wrap.className = "setting";
    const lab = document.createElement("label");
    lab.textContent = labelText;
    const input = document.createElement("input");
    input.type = "text";
    input.value = (CFG.ownership[field] || []).join(", ");
    input.addEventListener("input", () => {
      CFG.ownership[field] = input.value.split(",").map((s) => s.trim()).filter(Boolean);
      scheduleRetag();
    });
    wrap.appendChild(lab);
    wrap.appendChild(input);
    return wrap;
  }

  // ---------- 재태깅 스케줄(디바운스) ----------
  let retagTimer = null;
  function scheduleRetag() {
    if (retagTimer) clearTimeout(retagTimer);
    retagTimer = setTimeout(() => {
      retagAll();
      renderSummary();
      paintRows();
      if (selected) renderDetail(selected);
    }, 150);
  }

  // ---------- 패널 리사이즈 ----------
  function setupSplitters() {
    for (const sp of document.querySelectorAll(".splitter")) {
      const targetId = sp.dataset.target;
      const dir = targetId === "detail-pane" ? -1 : 1;
      sp.addEventListener("pointerdown", (e) => {
        e.preventDefault();
        const pane = document.getElementById(targetId);
        const startX = e.clientX;
        const startW = pane.getBoundingClientRect().width;
        sp.setPointerCapture(e.pointerId);
        const onMove = (ev) => {
          const w = Math.max(80, startW + dir * (ev.clientX - startX));
          pane.style.flex = "0 0 " + w + "px";
          paintRows();
        };
        const onUp = () => {
          sp.removeEventListener("pointermove", onMove);
          sp.removeEventListener("pointerup", onUp);
          try { localStorage.setItem("cora2-" + targetId, pane.style.flex); } catch (e) {}
        };
        sp.addEventListener("pointermove", onMove);
        sp.addEventListener("pointerup", onUp);
      });
    }
    // 저장된 폭 복원
    for (const id of ["settings-pane", "detail-pane"]) {
      try {
        const v = localStorage.getItem("cora2-" + id);
        if (v) document.getElementById(id).style.flex = v;
      } catch (e) {}
    }
  }

  // ---------- 유틸 ----------
  function span(cls, text) { const s = document.createElement("span"); s.className = cls; s.textContent = text; return s; }
  function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  // ---------- 부트 ----------
  async function boot() {
    DATA = await loadData();
    DEFAULT_CFG = clone(DATA.config);
    CFG = clone(DATA.config);

    document.getElementById("rootinfo").textContent =
      `${DATA.root} · ${DATA.files.length} files · ${DATA.generatedAt.slice(0, 19).replace("T", " ")}`;

    buildTree();
    retagAll();
    buildSettings();
    renderLegend();
    renderSummary();
    renderVisible();
    setupSplitters();

    viewport().addEventListener("scroll", paintRows, { passive: true });
    window.addEventListener("resize", paintRows);

    document.getElementById("expand-all").addEventListener("click", () => { setExpandedAll(true); renderVisible(); });
    document.getElementById("collapse-all").addEventListener("click", () => { setExpandedAll(false); renderVisible(); });
    document.getElementById("filter-input").addEventListener("input", (e) => {
      filterTerm = e.target.value.trim();
      computeFilter();
      renderVisible();
    });
    document.getElementById("reset-btn").addEventListener("click", () => {
      CFG = clone(DEFAULT_CFG);
      disabledTags.clear();
      buildSettings();
      retagAll();
      renderLegend(); renderSummary(); paintRows();
      if (selected) renderDetail(selected);
    });
  }

  function setExpandedAll(v) {
    (function walk(node) {
      for (const c of node.children) if (c.isDir) { c.expanded = v; walk(c); }
    })(root);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
