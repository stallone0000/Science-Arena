const state = {
  manifest: null,
  selectedSheet: "international_core",
  selectedBenchmark: "overall_international_core",
  selectedTurn: null,
  selectedModel: null,
  modelSearch: "",
  detailCache: new Map(),
  detailPromises: new Map(),
  sharedCache: new Map(),
  detailErrors: new Map(),
  benchmarkDetails: new Map(),
  detailRequestId: 0,
};

const CNY_PER_USD = 6.7657;

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function fmtNumber(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "N/A";
  if (Math.abs(number - Math.round(number)) < 1e-9) return String(Math.round(number));
  return number.toFixed(digits).replace(/\.?0+$/, "");
}

function costUsd(value) {
  if (value == null || value === "") return "N/A";
  const number = Number(value);
  if (!Number.isFinite(number)) return "N/A";
  return number / CNY_PER_USD;
}

function fmtCost(value) {
  const usd = costUsd(value);
  if (usd === "N/A") return "N/A";
  const digits = Math.abs(usd) < 0.01 ? 4 : Math.abs(usd) < 1 ? 3 : 2;
  return `$${fmtNumber(usd, digits)}`;
}

function costTitle(value) {
  if (value == null || value === "") return "No cost source available";
  const number = Number(value);
  if (!Number.isFinite(number)) return "No cost source available";
  return `Cost converted from CNY source records at 1 USD = ${CNY_PER_USD} CNY; source cost CNY ${fmtNumber(number, 3)}`;
}

function fmtTokens(value) {
  if (value == null || value === "") return "N/A";
  const number = Number(value);
  if (!Number.isFinite(number)) return "N/A";
  if (number >= 1_000_000) return `${fmtNumber(number / 1_000_000, 1)}M`;
  if (number >= 10_000) return `${fmtNumber(number / 1_000, 1)}k`;
  return Math.round(number).toLocaleString();
}

function scoreLabel(cell) {
  if (!cell || cell.status !== "ok" || cell.reported_score == null) return "N/A";
  return `${fmtNumber(cell.reported_score)}/${fmtNumber(cell.report_scale)}`;
}

function pctLabel(cell) {
  if (!cell || cell.status !== "ok" || cell.pct == null) return "N/A";
  return `${fmtNumber(Number(cell.pct) * 100, 1)}%`;
}

function ratioForBar(value, maxValue) {
  if (value == null || value === "") return 0;
  const number = Number(value);
  const max = Number(maxValue);
  if (!Number.isFinite(number) || !Number.isFinite(max) || max <= 0) return 0;
  return Math.max(0, Math.min(1, number / max));
}

function metricTone(kind, fillRatio) {
  if (kind !== "accuracy") return "";
  const value = Number(fillRatio);
  if (!Number.isFinite(value)) return "";
  if (value >= 0.78) return " metric-strong";
  if (value >= 0.48) return " metric-middle";
  return " metric-low";
}

function scoreRgb(fillRatio) {
  const r = Math.max(0, Math.min(1, Number(fillRatio) || 0));
  const red = [231, 76, 60];
  const yellow = [241, 196, 15];
  const green = [46, 204, 113];
  const start = r < 0.5 ? red : yellow;
  const end = r < 0.5 ? yellow : green;
  const local = r < 0.5 ? r / 0.5 : (r - 0.5) / 0.5;
  return start.map((x, i) => Math.round(x + (end[i] - x) * local)).join(",");
}

function metricCell(kind, fillRatio, main, sub = "", title = "") {
  const width = Math.max(0, Math.min(100, Number(fillRatio) * 100 || 0));
  const style = kind === "accuracy" ? ` style="--metric-score-rgb:${scoreRgb(fillRatio)}"` : "";
  return `
    <div class="metric-cell metric-${escapeHtml(kind)}${metricTone(kind, fillRatio)}"${style} title="${escapeHtml(title || `${main} ${sub}`)}">
      <span class="metric-fill" style="width:${width}%"></span>
      <span class="metric-content">
        <strong>${escapeHtml(main)}</strong>
        ${sub ? `<small>${escapeHtml(sub)}</small>` : ""}
      </span>
    </div>`;
}

function blockColor(turn) {
  if (!turn || turn.verdict === "missing") return "";
  const r = Number(turn.ratio ?? 0);
  if (turn.verdict !== "partial") return "";
  const red = [197, 73, 73];
  const yellow = [224, 174, 38];
  const green = [42, 151, 92];
  const start = r < 0.5 ? red : yellow;
  const end = r < 0.5 ? yellow : green;
  const local = r < 0.5 ? r / 0.5 : (r - 0.5) / 0.5;
  const mixed = start.map((x, i) => Math.round(x + (end[i] - x) * local));
  return `rgb(${mixed.join(",")})`;
}

function contamTag(value) {
  if (!value) return "";
  if (value === "pre_release_holdout") return `<span class="tag safe">pre-release</span>`;
  return `<span class="tag warn compact-warn" title="Possible timing/data leakage">!</span>`;
}

function rankTag(rank) {
  if (!rank) return "";
  return `<span class="tag rank">#${rank}</span>`;
}

function isCoreSheet() {
  return activeSheet()?.sheet_id === "international_core";
}

function modelSubtitle(model, cell) {
  if (activeSheet()?.sheet_id === "sealed_2026") {
    const mode = cell?.input_mode === "vision" ? "V · native images" : "T · frozen text";
    return `${escapeHtml(mode)} · ${escapeHtml(model.model_id)}`;
  }
  return `${escapeHtml(model.provider || "")}${model.release_date ? ` | ${escapeHtml(model.release_date)}` : ""}`;
}

function intervalLabel(cell) {
  return cell?.ci95 ? `95% [${fmtNumber(cell.ci95[0])}, ${fmtNumber(cell.ci95[1])}]` : "";
}

function isCoreOverall() {
  return Boolean(currentBenchmark()?.overall) && isCoreSheet();
}

function entryCountLabel(validCells, sheet = activeSheet()) {
  if (sheet?.sheet_id === "international_core") return "5 models + 4 human references";
  return `${validCells} models`;
}

function medalInfo(benchmarkId, score) {
  const cuts = state.manifest?.benchmarks?.[benchmarkId]?.reference_cutoffs || {};
  const value = Number(score);
  if (!Number.isFinite(value)) return null;
  const levels = [
    ["winner", "🏆", "winner"],
    ["gold", "🥇", "gold"],
    ["silver", "🥈", "silver"],
    ["bronze", "🥉", "bronze"],
  ];
  for (const [key, icon, label] of levels) {
    const cutoff = Number(cuts[key]);
    if (Number.isFinite(cutoff) && value >= cutoff) {
      return { key, icon, label };
    }
  }
  return null;
}

function medalTag(benchmarkId, score) {
  const medal = medalInfo(benchmarkId, score);
  if (!medal) return "";
  return `<span class="tag rank medal-tag medal-${escapeHtml(medal.key)}">${escapeHtml(`${medal.icon} ${medal.label}`)}</span>`;
}

function medalInline(benchmarkId, score) {
  const medal = medalInfo(benchmarkId, score);
  return medal ? `${medal.icon} ${medal.label}` : "";
}

function coreReferenceTag(modelId) {
  const tags = {
    "human/winner": ["winner", "🏆 No.1"],
    "human/gold": ["gold", "🥇 Gold"],
    "human/silver": ["silver", "🥈 Silver"],
    "human/bronze": ["bronze", "🥉 Bronze"],
  };
  if (!tags[modelId]) return "";
  const [key, label] = tags[modelId];
  return `<span class="tag rank medal-tag medal-${escapeHtml(key)}">${escapeHtml(label)}</span>`;
}

function coreScoreMetricCell(cell) {
  if (!cell || cell.status !== "ok" || cell.reported_score == null) {
    const label = cell?.status === "invalid" ? "Invalid" : "N/A";
    return invalidMetric(label, label);
  }
  const medal = medalInline(cell.benchmark_id, cell.reported_score);
  return metricCell(
    "accuracy",
    Number(cell.pct || 0),
    scoreLabel(cell),
    medal,
    `Score from reported_score / report_scale${medal ? `; ${medal}` : ""}`
  );
}

function cellBelongsToSheet(cell, sheetId = activeSheet()?.sheet_id) {
  return (cell?.sheet_id || "") === (sheetId || "");
}

function cellMapKey(benchmarkId, modelId) {
  return `${benchmarkId}::${modelId}`;
}

function activeBenchmarks() {
  const sheet = activeSheet();
  const ids = sheet?.benchmark_ids || state.manifest.benchmark_order || Object.keys(state.manifest.benchmarks || {});
  return ids.filter((id) => state.manifest.benchmarks[id]);
}

function activeSheets() {
  return Array.isArray(state.manifest.sheets) ? state.manifest.sheets : [];
}

function activeSheet() {
  const sheets = activeSheets();
  return sheets.find((sheet) => sheet.sheet_id === state.selectedSheet) || sheets[0] || null;
}

function sheetForBenchmark(benchmarkId) {
  return activeSheets().find((sheet) => (sheet.benchmark_ids || []).includes(benchmarkId)) || activeSheet();
}

function showUsageColumns() {
  if (currentBenchmark()?.overall) return false;
  const sheet = activeSheet();
  return sheet?.show_usage !== false;
}

function showProblemCells() {
  if (currentBenchmark()?.overall) return false;
  if (currentBenchmark()?.show_problem_cells != null) return currentBenchmark().show_problem_cells;
  const sheet = activeSheet();
  return sheet?.show_problem_cells !== false;
}

function ensureSelectedBenchmark() {
  const ids = activeBenchmarks();
  if (!ids.includes(state.selectedBenchmark)) {
    state.selectedBenchmark = ids[0] || "";
    state.selectedTurn = null;
    state.selectedModel = null;
  }
}

function currentBenchmark() {
  return state.manifest.benchmarks[state.selectedBenchmark];
}

function cellsByKey(sheetId = activeSheet()?.sheet_id) {
  const map = new Map();
  for (const cell of state.manifest.cells) {
    if (cellBelongsToSheet(cell, sheetId)) {
      map.set(cellMapKey(cell.benchmark_id, cell.model), cell);
    }
  }
  return map;
}

function filteredModels() {
  const q = state.modelSearch.trim().toLowerCase();
  const cellMap = cellsByKey();
  const benchmarkId = state.selectedBenchmark;
  const sheetModelIds = activeSheet()?.model_ids;
  const allowed = Array.isArray(sheetModelIds) ? new Set(sheetModelIds) : null;
  const modelsWithData = state.manifest.models.filter((model) => {
    return cellMap.has(cellMapKey(benchmarkId, model.model_id)) && (!allowed || allowed.has(model.model_id));
  });
  if (!q) return modelsWithData;
  return modelsWithData.filter((model) => {
    return [model.display, model.model_id, model.provider].join(" ").toLowerCase().includes(q);
  });
}

function leaderboardModels() {
  const cellMap = cellsByKey();
  const models = filteredModels().slice();
  const sheetModelIds = activeSheet()?.model_ids;
  if (isCoreSheet() && Array.isArray(sheetModelIds) && sheetModelIds.length) {
    const order = new Map(sheetModelIds.map((modelId, index) => [modelId, index]));
    return models.sort((a, b) => {
      const aOrder = order.has(a.model_id) ? order.get(a.model_id) : Number.MAX_SAFE_INTEGER;
      const bOrder = order.has(b.model_id) ? order.get(b.model_id) : Number.MAX_SAFE_INTEGER;
      if (aOrder !== bOrder) return aOrder - bOrder;
      return (a.display || a.model_id).localeCompare(b.display || b.model_id);
    });
  }
  return models.sort((a, b) => {
      const aCell = cellMap.get(cellMapKey(state.selectedBenchmark, a.model_id));
      const bCell = cellMap.get(cellMapKey(state.selectedBenchmark, b.model_id));
      const aOk = aCell?.status === "ok" && aCell?.reported_score != null;
      const bOk = bCell?.status === "ok" && bCell?.reported_score != null;
      if (aOk !== bOk) return aOk ? -1 : 1;
      if (aOk && bOk) return Number(bCell.reported_score) - Number(aCell.reported_score);
      return (a.display || a.model_id).localeCompare(b.display || b.model_id);
    });
}

function detailUrl(path) {
  if (!path) return "";
  return path.startsWith("/") ? path : `/${path}`;
}

function hideStaticFallback() {
  const fallback = $("staticFallback");
  if (fallback) fallback.hidden = true;
}

function renderLayoutMode() {
  const includeProblems = showProblemCells();
  const overall = Boolean(currentBenchmark()?.overall);
  const coreOverall = isCoreOverall();
  $("workbench")?.classList.toggle("summary-mode", !includeProblems && (!overall || coreOverall));
  $("workbench")?.classList.toggle("overall-mode", overall && !coreOverall);
  $("workbench")?.classList.toggle("sealed-2026", activeSheet()?.sheet_id === "sealed_2026");
  if ($("cellLegend")) $("cellLegend").hidden = !includeProblems;
  if ($("tableHint")) $("tableHint").hidden = !includeProblems;
  if ($("detailPanel")) $("detailPanel").hidden = !includeProblems;
}

function renderTabs() {
  ensureSelectedBenchmark();
  const sheets = activeSheets();
  $("sheetTabs").innerHTML = sheets
    .map((sheet) => {
      const active = sheet.sheet_id === activeSheet()?.sheet_id ? " active" : "";
      return `<button class="tab-button${active}" data-sheet="${escapeHtml(sheet.sheet_id)}">${escapeHtml(sheet.name)}</button>`;
    })
    .join("");

  $("sheetTabs").querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedSheet = button.dataset.sheet;
      state.selectedBenchmark = activeBenchmarks()[0] || "";
      state.selectedTurn = null;
      state.selectedModel = null;
      render();
      loadBenchmarkDetails();
    });
  });

  $("categoryTabs").innerHTML = activeBenchmarks()
    .map((benchmarkId) => {
      const bench = state.manifest.benchmarks[benchmarkId];
      const active = benchmarkId === state.selectedBenchmark ? " active" : "";
      return `<button class="competition-button${active}" data-benchmark="${escapeHtml(benchmarkId)}">${escapeHtml(bench.name)}</button>`;
    })
    .join("");

  $("categoryTabs").querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedBenchmark = button.dataset.benchmark;
      state.selectedTurn = null;
      state.selectedModel = null;
      render();
      loadBenchmarkDetails();
    });
  });
}

function renderSummary() {
  const sheet = activeSheet();
  const notes = [sheet?.description || state.manifest.protocol.note];
  if (currentBenchmark()?.detail_unavailable_note) notes.push(currentBenchmark().detail_unavailable_note);
  if (showProblemCells() && (sheet?.benchmark_ids || []).includes("ibo2023")) {
    notes.push(state.manifest.protocol.objective_note);
  }
  const description = notes.filter(Boolean).join("\n");
  $("sheetDescription").textContent = description;
  $("sheetDescription").title = description;
  $("releaseLinks").innerHTML = (state.manifest.release_2026?.links || [])
    .map((link) => `<a href="${escapeHtml(link.url)}" target="_blank" rel="noopener">${escapeHtml(link.label)}</a>`)
    .join(" · ");
}

function renderBenchmarkHeader() {
  const bench = currentBenchmark();
  $("benchmarkTitle").textContent = bench ? bench.name : "Leaderboard";
  if (!bench) {
    $("benchmarkMeta").textContent = "";
    return;
  }
  const sheet = activeSheet();
  const validCells = state.manifest.cells.filter((cell) => {
    return cellBelongsToSheet(cell, sheet?.sheet_id) && cell.benchmark_id === state.selectedBenchmark && cell.status === "ok";
  }).length;
  if (bench.overall) {
    const count = (bench.source_benchmark_ids || []).length;
    const pieces = isCoreSheet()
      ? [sheet?.name, "archived manual evaluation", `${count} competitions`, entryCountLabel(validCells, sheet)]
      : [sheet?.name, `${count} competitions`, entryCountLabel(validCells, sheet), "normalized score /100"];
    $("benchmarkMeta").textContent = pieces.filter(Boolean).join(" | ");
    return;
  }
  const pieces = [
    sheet?.name,
    bench.discipline,
    bench.release_date,
    bench.turn_count ? `${bench.turn_count} turns` : "",
    entryCountLabel(validCells, sheet),
    `scale ${fmtNumber(bench.report_scale)}`,
  ].filter(Boolean);
  $("benchmarkMeta").textContent = pieces.join(" | ");
}

function evaluatorLabel(turn, benchmarkId) {
  if (["ipho2025", "icho2025", "ibo2023"].includes(benchmarkId)) return "human evaluation";
  return turn.judge_model || "n/a";
}

function rankLabel(rank) {
  return rank ? `#${rank}` : "N/A";
}

function invalidMetric(label = "N/A", title = "") {
  return `
    <div class="metric-cell metric-invalid" title="${escapeHtml(title || label)}">
      <span class="metric-fill" style="width:0%"></span>
      <span class="metric-content"><strong>${escapeHtml(label)}</strong></span>
    </div>`;
}

function renderCoreOverallTable(models, cellMap, benchmarkIds) {
  const tableWidth = 342 + benchmarkIds.length * 182;
  const colgroup = `
    <colgroup>
      <col class="model-col" />
      ${benchmarkIds.map(() => `<col class="metric-col" />`).join("")}
    </colgroup>`;
  const head = `
    <thead>
      <tr>
        <th class="model-cell">Model Name</th>
        ${benchmarkIds.map((id) => `<th class="metric-head">${escapeHtml(state.manifest.benchmarks[id]?.name || id)}</th>`).join("")}
      </tr>
    </thead>`;
  const body = models
    .map((model) => {
      const scoreCells = benchmarkIds
        .map((id) => {
          const cell = cellMap.get(cellMapKey(id, model.model_id));
          return `<td>${coreScoreMetricCell(cell)}</td>`;
        })
        .join("");
      const tags = [
        coreReferenceTag(model.model_id),
        cellMap.get(cellMapKey(state.selectedBenchmark, model.model_id))?.status !== "ok" ? `<span class="tag invalid">invalid</span>` : "",
      ].join("");
      return `
        <tr>
          <td class="model-cell">
            <div class="model-title-row">
              <div class="model-name">${escapeHtml(model.display)}</div>
              <div class="score-tags">${tags || ""}</div>
            </div>
            <div class="model-sub">${modelSubtitle(model, cellMap.get(cellMapKey(state.selectedBenchmark, model.model_id)))}</div>
          </td>
          ${scoreCells}
        </tr>`;
    })
    .join("");
  $("scoreTable").innerHTML = `<table class="arena-table summary-table core-overall-table" style="width:${tableWidth}px">${colgroup}${head}<tbody>${body}</tbody></table>`;
}

function renderOverallTable() {
  const benchmarkId = state.selectedBenchmark;
  const bench = currentBenchmark();
  const cellMap = cellsByKey();
  const models = leaderboardModels();
  const benchmarkIds = bench?.source_benchmark_ids || [];
  if (!models.length) {
    $("scoreTable").innerHTML = `<div class="empty-state">No models match the current filter.</div>`;
    return;
  }
  if (isCoreSheet()) {
    renderCoreOverallTable(models, cellMap, benchmarkIds);
    return;
  }
  const tableWidth = 218 + 62 + 126 + benchmarkIds.length * 112;
  const colgroup = `
    <colgroup>
      <col class="model-col" />
      <col class="rank-col" />
      <col class="overall-score-col" />
      ${benchmarkIds.map(() => `<col class="overall-benchmark-col" />`).join("")}
    </colgroup>`;
  const head = `
    <thead>
      <tr>
        <th class="model-cell">Model Name</th>
        <th class="rank-head">Rank</th>
        <th class="overall-score-head">Normalized Score</th>
        ${benchmarkIds.map((id) => `<th class="overall-benchmark-head">${escapeHtml(state.manifest.benchmarks[id]?.name || id)}</th>`).join("")}
      </tr>
    </thead>`;
  const body = models
    .map((model) => {
      const overallCell = cellMap.get(cellMapKey(benchmarkId, model.model_id));
      const tags = [
        rankTag(overallCell?.rank),
        overallCell?.status !== "ok" ? `<span class="tag invalid">invalid</span>` : "",
      ].join("");
      const score = overallCell?.reported_score;
      const componentCells = benchmarkIds
        .map((id) => {
          const cell = cellMap.get(cellMapKey(id, model.model_id));
          if (!cell || cell.status !== "ok" || cell.reported_score == null) {
            const label = cell?.status === "invalid" ? "Invalid" : "N/A";
            return `<td>${invalidMetric(label, `${state.manifest.benchmarks[id]?.name || id}: ${label}`)}</td>`;
          }
          const metric = metricCell("accuracy", Number(cell.pct || 0), scoreLabel(cell), pctLabel(cell), `${state.manifest.benchmarks[id]?.name || id}: ${scoreLabel(cell)}`);
          return activeSheet()?.sheet_id === "sealed_2026"
            ? `<td><button class="score-drilldown" data-benchmark="${escapeHtml(id)}" data-model="${escapeHtml(model.model_id)}" aria-label="View ${escapeHtml(model.display)} on ${escapeHtml(state.manifest.benchmarks[id]?.name || id)}">${metric}</button></td>`
            : `<td>${metric}</td>`;
        })
        .join("");
      return `
        <tr>
          <td class="model-cell">
            <div class="model-title-row">
              <div class="model-name">${escapeHtml(model.display)}</div>
              <div class="score-tags">${tags || ""}</div>
            </div>
            <div class="model-sub">${modelSubtitle(model, cellMap.get(cellMapKey(state.selectedBenchmark, model.model_id)))}</div>
          </td>
          <td class="rank-value">${escapeHtml(rankLabel(overallCell?.rank))}</td>
          <td>${metricCell("accuracy", Number(overallCell?.pct || 0), fmtNumber(score, 2), intervalLabel(overallCell), "Mean normalized score across competitions in this sheet; interval covers question sampling only")}</td>
          ${componentCells}
        </tr>`;
    })
    .join("");
  $("scoreTable").innerHTML = `<table class="arena-table overall-table" style="width:${tableWidth}px;${activeSheet()?.sheet_id === "sealed_2026" ? "min-width:100%" : ""}">${colgroup}${head}<tbody>${body}</tbody></table>`;
  $("scoreTable").querySelectorAll(".score-drilldown").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedBenchmark = button.dataset.benchmark;
      state.selectedModel = button.dataset.model;
      state.selectedTurn = currentBenchmark()?.turns?.[0]?.turn_id || null;
      render();
      loadBenchmarkDetails();
      focusDetailPanel();
    });
  });
}

function renderScoreTable() {
  const benchmarkId = state.selectedBenchmark;
  const bench = currentBenchmark();
  const cellMap = cellsByKey();
  const models = leaderboardModels();
  const details = state.benchmarkDetails.get(benchmarkId);
  if (!bench) {
    $("scoreTable").innerHTML = `<div class="error">No competition selected.</div>`;
    return;
  }
  if (!models.length) {
    $("scoreTable").innerHTML = `<div class="empty-state">No models match the current filter.</div>`;
    return;
  }
  if (bench.overall) {
    renderOverallTable();
    return;
  }

  const turns = bench.turns || [];
  const includeUsage = showUsageColumns();
  const includeProblems = showProblemCells();
  const coreSheet = isCoreSheet();
  const maxCost = Math.max(...models.map((model) => Number(cellMap.get(cellMapKey(benchmarkId, model.model_id))?.cost_cny)).filter(Number.isFinite), 0);
  const maxTokens = Math.max(...models.map((model) => Number(cellMap.get(cellMapKey(benchmarkId, model.model_id))?.total_tokens)).filter(Number.isFinite), 0);
  const metricColumnCount = includeUsage ? 3 : 1;
  const problemColumnCount = includeProblems ? turns.length : 0;
  const tableWidth = includeProblems
    ? 218 + 94 * metricColumnCount + problemColumnCount * 30
    : coreSheet
    ? 860
    : 520;
  const scoreHeader = includeUsage || includeProblems ? "Accuracy" : "Score";
  const colgroup = `
    <colgroup>
      <col class="model-col" />
      <col class="metric-col" />
      ${includeUsage ? `<col class="metric-col" /><col class="metric-col" />` : ""}
      ${includeProblems ? turns.map(() => `<col class="problem-col" />`).join("") : ""}
    </colgroup>`;
  const head = `
    <thead>
      <tr>
        <th class="model-cell">Model Name</th>
        <th class="metric-head">${escapeHtml(scoreHeader)}</th>
        ${includeUsage ? `<th class="metric-head">Cost (USD)</th><th class="metric-head">Tokens</th>` : ""}
        ${includeProblems ? turns.map((turn) => `<th class="problem-head" title="${escapeHtml(turn.turn_id)}"><span>${escapeHtml(turn.label)}</span></th>`).join("") : ""}
      </tr>
    </thead>`;
  const body = models
    .map((model) => {
      const cell = cellMap.get(cellMapKey(benchmarkId, model.model_id));
      const detail = includeProblems ? details?.get(model.model_id) : null;
      const turnMap = new Map((detail?.turns || []).map((turn) => [turn.turn_id, turn]));
      const tags = [
        coreSheet ? coreReferenceTag(model.model_id) : rankTag(cell?.rank),
        coreSheet ? "" : medalTag(benchmarkId, cell?.reported_score),
        coreSheet ? "" : contamTag(cell?.contamination),
        cell?.status !== "ok" ? `<span class="tag invalid">invalid</span>` : "",
      ].join("");
      const problemCells = includeProblems ? turns
        .map((turnRef) => {
          if (coreSheet && cell?.reference_row && !cell?.detail_path) {
            const title = `${model.display} is an official human reference row; per-problem model-answer detail is available for model rows.`;
            return `<td class="problem-cell-wrap"><span class="problem-cell no-detail" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}"></span></td>`;
          }
          const turn = turnMap.get(turnRef.turn_id);
          const verdict = details ? turn?.verdict || "missing" : "loading";
          const active = state.selectedTurn === turnRef.turn_id && state.selectedModel === model.model_id ? " active" : "";
          const style = blockColor(turn) ? `style="background:${blockColor(turn)}"` : "";
          const disabled = !turn ? " disabled" : "";
          const title = turn
            ? `${model.display} - ${turn.label}: ${fmtNumber(turn.score)}/${fmtNumber(turn.max_score)}`
            : `${model.display} - ${turnRef.label}: detail not loaded`;
          return `<td class="problem-cell-wrap"><button class="problem-cell ${escapeHtml(verdict)}${active}" ${style}${disabled} data-model="${escapeHtml(model.model_id)}" data-turn="${escapeHtml(turnRef.turn_id)}" title="${escapeHtml(title)}" aria-label="${escapeHtml(title)}"></button></td>`;
        })
        .join("") : "";
      const tokenTitle = cell?.total_tokens != null
        ? `${Number(cell.total_tokens).toLocaleString()} total tokens; ${Number(cell.prompt_tokens || 0).toLocaleString()} prompt, ${Number(cell.completion_tokens || 0).toLocaleString()} completion`
        : "No token source available";
      return `
        <tr>
          <td class="model-cell">
            <div class="model-title-row">
              <div class="model-name">${escapeHtml(model.display)}</div>
              <div class="score-tags">${tags || ""}</div>
            </div>
            <div class="model-sub">${modelSubtitle(model, cellMap.get(cellMapKey(state.selectedBenchmark, model.model_id)))}</div>
          </td>
          <td>${coreSheet
            ? coreScoreMetricCell(cell)
            : includeUsage || includeProblems
            ? metricCell("accuracy", Number(cell?.pct || 0), pctLabel(cell), scoreLabel(cell), "Accuracy from reported_score / report_scale")
            : metricCell("accuracy", Number(cell?.pct || 0), scoreLabel(cell), "", "Score from reported_score / report_scale")}</td>
          ${includeUsage ? `<td>${metricCell("cost", ratioForBar(cell?.cost_cny, maxCost), fmtCost(cell?.cost_cny), "", costTitle(cell?.cost_cny))}</td>
          <td>${metricCell("tokens", ratioForBar(cell?.total_tokens, maxTokens), fmtTokens(cell?.total_tokens), "", tokenTitle)}</td>` : ""}
          ${problemCells}
        </tr>`;
    })
    .join("");
  const tableClass = includeProblems
    ? "arena-table"
    : coreSheet
    ? "arena-table summary-table core-score-table"
    : "arena-table summary-table";
  $("scoreTable").innerHTML = `<table class="${tableClass}" style="width:${tableWidth}px">${colgroup}${head}<tbody>${body}</tbody></table>`;
  $("scoreTable").querySelectorAll(".problem-cell").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.disabled) return;
      state.selectedModel = button.dataset.model;
      state.selectedTurn = button.dataset.turn;
      renderScoreTable();
      renderDetail();
      if (activeSheet()?.sheet_id === "sealed_2026") loadSelectedDetail();
      focusDetailPanel();
    });
  });
}

function detailKey(benchmarkId, modelId) {
  return `${benchmarkId}::${modelId}`;
}

async function loadDetail(cell) {
  if (!cell?.detail_path) return null;
  const key = detailKey(cell.benchmark_id, cell.model);
  if (state.detailCache.has(key)) return state.detailCache.get(key);
  if (state.detailPromises.has(key)) return state.detailPromises.get(key);
  const promise = (async () => {
    const data = await fetchDetail(cell.detail_path);
    if (cell.shared_path) {
      if (!state.sharedCache.has(cell.shared_path)) {
        const sharedPromise = fetchDetail(cell.shared_path).catch((error) => {
          state.sharedCache.delete(cell.shared_path);
          throw error;
        });
        state.sharedCache.set(cell.shared_path, sharedPromise);
      }
      const shared = await state.sharedCache.get(cell.shared_path);
      if (data.model?.model_id !== cell.model) throw new Error("Detail model does not match the selected row.");
      const questions = new Map(shared.turns.map((turn) => [turn.turn_id, turn]));
      data.turns = data.turns.map((turn) => {
        const question = questions.get(turn.turn_id);
        if (!question) throw new Error("A frozen question is missing from this detail record.");
        return {
          ...question,
          ...turn,
          question: cell.input_mode === "text_staticized" ? question.question_staticized : question.question,
          input_mode: cell.input_mode,
        };
      });
    }
    state.detailCache.set(key, data);
    return data;
  })();
  state.detailPromises.set(key, promise);
  try {
    return await promise;
  } finally {
    state.detailPromises.delete(key);
  }
}

async function fetchDetail(path) {
  const url = detailUrl(path);
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to load detail (HTTP ${response.status}). Please retry.`);
  return response.json();
}

async function loadSelectedDetail() {
  const benchmarkId = state.selectedBenchmark;
  const modelId = state.selectedModel;
  const turnId = state.selectedTurn;
  if (!modelId || !turnId) return;
  const key = detailKey(benchmarkId, modelId);
  state.detailErrors.delete(key);
  try {
    const cell = cellsByKey().get(cellMapKey(benchmarkId, modelId));
    const detail = await loadDetail(cell);
    if (benchmarkId !== state.selectedBenchmark || modelId !== state.selectedModel || turnId !== state.selectedTurn) return;
    if (!detail) throw new Error("Detail record is unavailable.");
    state.benchmarkDetails.get(benchmarkId)?.set(modelId, detail);
    renderScoreTable();
    renderDetail();
  } catch (error) {
    if (benchmarkId !== state.selectedBenchmark || modelId !== state.selectedModel || turnId !== state.selectedTurn) return;
    state.detailErrors.set(key, error.message);
    renderDetail();
  }
}

async function loadBenchmarkDetails() {
  const benchmarkId = state.selectedBenchmark;
  const requestId = ++state.detailRequestId;
  if (!benchmarkId || !state.manifest.benchmarks[benchmarkId]) {
    $("scoreTable").innerHTML = `<div class="error">No competition selected.</div>`;
    return;
  }
  if (!showProblemCells()) {
    state.benchmarkDetails.set(benchmarkId, new Map());
    renderScoreTable();
    renderDetail();
    return;
  }
  const cellMap = cellsByKey();
  const models = filteredModels();
  if (!models.length) {
    state.benchmarkDetails.set(benchmarkId, new Map());
    renderScoreTable();
    return;
  }
  if (activeSheet()?.sheet_id === "sealed_2026") {
    const bench = currentBenchmark();
    const previews = new Map(models.map((model) => {
      const key = detailKey(benchmarkId, model.model_id);
      const cached = state.detailCache.get(key);
      if (cached) return [model.model_id, cached];
      const cell = cellMap.get(cellMapKey(benchmarkId, model.model_id));
      const turns = (bench.turns || []).map((ref, index) => {
        const score = cell.turn_scores?.[index];
        const ratio = score == null ? null : score / ref.max_score;
        return { ...ref, score, ratio, verdict: ratio == null ? "missing" : ratio >= 1 - 1e-9 ? "correct" : ratio <= 1e-9 ? "wrong" : "partial" };
      });
      return [model.model_id, { benchmark: bench, model, turns, preview: true }];
    }));
    state.benchmarkDetails.set(benchmarkId, previews);
    renderScoreTable();
    renderDetail();
    if (state.selectedModel && state.selectedTurn) loadSelectedDetail();
    return;
  }
  try {
    const pairs = await Promise.all(
      models.map(async (model) => {
        const cell = cellMap.get(cellMapKey(benchmarkId, model.model_id));
        const detail = await loadDetail(cell).catch(() => null);
        return [model.model_id, detail];
      })
    );
    if (requestId !== state.detailRequestId || benchmarkId !== state.selectedBenchmark) return;
    state.benchmarkDetails.set(benchmarkId, new Map(pairs));
    renderScoreTable();
    renderDetail();
  } catch (error) {
    if (requestId !== state.detailRequestId) return;
    $("scoreTable").innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
  }
}

function focusDetailPanel() {
  if (!window.matchMedia("(max-width: 1100px)").matches) return;
  requestAnimationFrame(() => {
    $("detailPanel")?.scrollIntoView({ block: "start", behavior: "auto" });
  });
}

function textBlock(title, value, boxClass = "response-box") {
  if (value == null || value === "") return "";
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return `
    <section class="detail-box ${escapeHtml(boxClass)}">
      <h4>${escapeHtml(title)}</h4>
      <pre class="text-block">${escapeHtml(text)}</pre>
    </section>`;
}

function figureBlock(image, index) {
  const values = Array.isArray(image.extracted_values) && image.extracted_values.length
    ? `<ul>${image.extracted_values.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul>`
    : "";
  return `
    <figure class="question-figure">
      <a href="${escapeHtml(detailUrl(image.src))}" target="_blank" rel="noopener">
        <img src="${escapeHtml(detailUrl(image.src))}" alt="${escapeHtml(image.label || `Figure ${index + 1}`)}" loading="lazy" />
      </a>
      <figcaption>
        <strong>${escapeHtml(image.label || `Figure ${index + 1}`)}</strong>
        ${image.description ? `<span>${escapeHtml(image.description)}</span>` : ""}
        ${values}
      </figcaption>
    </figure>`;
}

function questionBlock(turn) {
  const images = Array.isArray(turn.question_images) ? turn.question_images : [];
  return `
    <section class="detail-box problem-box">
      <h4>Problem Details</h4>
      <div class="${images.length ? "question-stack" : ""}">
        ${images.length ? `<div class="media-rail" aria-label="Problem figures">${images.map((image, index) => figureBlock(image, index)).join("")}</div>` : ""}
        <pre class="text-block question-text-block">${escapeHtml(turn.question || "")}</pre>
      </div>
    </section>`;
}

function renderDetail() {
  if (!state.selectedTurn || !state.selectedModel) {
    $("detailPanel").innerHTML = `
      <div class="empty-detail">
        <h3>Problem Details</h3>
        <p>Select a problem cell in the leaderboard.</p>
      </div>`;
    return;
  }
  const details = state.benchmarkDetails.get(state.selectedBenchmark);
  const detail = details?.get(state.selectedModel);
  const turn = detail?.turns?.find((row) => row.turn_id === state.selectedTurn);
  if (detail?.preview) {
    const error = state.detailErrors.get(detailKey(state.selectedBenchmark, state.selectedModel));
    $("detailPanel").innerHTML = error
      ? `<div class="error">${escapeHtml(error)} <button id="retryDetail" type="button">Retry</button></div>`
      : `<div class="loading">Loading model answer and scoring feedback…</div>`;
    $("retryDetail")?.addEventListener("click", () => {
      state.detailErrors.delete(detailKey(state.selectedBenchmark, state.selectedModel));
      renderDetail();
      loadSelectedDetail();
    });
    return;
  }
  if (!detail || !turn) {
    $("detailPanel").innerHTML = `<div class="error">Detail not available.</div>`;
    return;
  }
  const model = detail.model || {};
  const bench = { ...detail.benchmark, ...state.manifest.benchmarks[state.selectedBenchmark] };
  const statusTag = `<span class="tag ${turn.verdict === "correct" ? "safe" : turn.verdict === "wrong" ? "warn" : ""}">${escapeHtml(turn.verdict)}</span>`;
  const evaluator = evaluatorLabel(turn, state.selectedBenchmark);
  const latest = activeSheet()?.sheet_id === "sealed_2026";
  $("detailPanel").innerHTML = `
    <div class="detail-content">
      <div class="detail-kicker">
        <span class="tag rank">${escapeHtml(bench.name || state.selectedBenchmark)}</span>
        <span class="tag">${escapeHtml(model.display || state.selectedModel)}</span>
        ${statusTag}
      </div>
      <h3>${escapeHtml(turn.label)}</h3>
      <p class="detail-muted">${escapeHtml(turn.turn_id)} | score ${fmtNumber(turn.score)}/${fmtNumber(turn.max_score)} | evaluator: ${escapeHtml(evaluator)}</p>
      ${turn.competition_score != null ? `<p class="detail-muted">Raw item grading points above; contribution to the competition total: ${fmtNumber(turn.competition_score, 4)}/${fmtNumber(turn.competition_max_score, 4)}.</p>` : ""}
      ${questionBlock(turn)}
      ${textBlock("Model Answer", turn.candidate_answer, "response-box")}
      ${textBlock("Evaluation Feedback", turn.judge_result, "judgment-box")}
      ${textBlock(latest ? "Reference Answer Used for Scoring" : "Official Answer", latest ? turn.reference_answer : turn.official_answer, "solution-box")}
      ${latest ? textBlock("Worked Reference Solution", turn.official_solution, "solution-box") : ""}
      ${turn.solution_images?.length ? `<section class="detail-box solution-box"><h4>Reference Solution Pages</h4><div class="media-rail">${turn.solution_images.map(figureBlock).join("")}</div></section>` : ""}
      ${textBlock(latest ? "Scoring Rubric" : "Rubric", turn.official_rubric, "rubric-box")}
      ${turn.generation_error || turn.judge_error ? textBlock("Run Errors", { generation_error: turn.generation_error, judge_error: turn.judge_error }, "error-box") : ""}
      ${turn.caveats?.length ? textBlock("Caveats", turn.caveats, "rubric-box") : ""}
    </div>`;
}

function render() {
  ensureSelectedBenchmark();
  renderTabs();
  renderLayoutMode();
  renderSummary();
  renderBenchmarkHeader();
  renderScoreTable();
  renderDetail();
}

async function init() {
  const response = await fetch("/static/data/manifest.json");
  state.manifest = await response.json();
  state.selectedSheet = state.manifest.default_sheet || state.selectedSheet;
  state.selectedBenchmark = state.manifest.default_benchmark || state.selectedBenchmark;
  state.selectedSheet = activeSheet()?.sheet_id || "";
  ensureSelectedBenchmark();
  $("modelSearch").addEventListener("input", (event) => {
    state.modelSearch = event.target.value;
    render();
    loadBenchmarkDetails();
  });
  render();
  hideStaticFallback();
  loadBenchmarkDetails();
}

init().catch((error) => {
  const app = $("app");
  const message = `<div class="runtime-error">Failed to load interactive dashboard: ${escapeHtml(error.message)}. Static scores are shown below.</div>`;
  if (app) app.insertAdjacentHTML("afterbegin", message);
});
