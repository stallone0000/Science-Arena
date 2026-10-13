#!/usr/bin/env python3
"""Add the sealed 2026 release to the prebuilt dashboard without raw downloads."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "static/data"
SOURCE_COMMIT = "c2a2acc4e311a8a7b0530de087fbf4e1b5cafe8c"
REPO = "https://github.com/stallone0000/Science-Arena-code"
SHEET = "sealed_2026"
OVERALL = "overall_sealed_2026"
COUNTS = {"ipho2026": 23, "icho2026": 68, "nbpho2026": 28, "usapho2026": 34}
NOTE = (
    "August 2026 sealed release: 14 models, 4 competitions, 153 turns, 56 complete cells. "
    "Macro = equal-weight mean of the four normalized scores. V = original question images; "
    "T = reviewed answer-blind question text, no images. Judge: Gemini 3.5 Flash. "
    "95% intervals use 10,000 whole-question bootstrap samples; they do not measure "
    "generation or judge variance. Training exposure is indeterminate. "
    "Full question images, visible answers and judge records are available in the release assets. "
    "Select a competition, then click a colored question cell to inspect its answer and grade. "
    "IPhO solution PDFs have unverified official/final status; some rubrics are derived."
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fallback(manifest):
    e = html.escape
    sections = []
    for sheet in manifest["sheets"]:
        ids = sheet["benchmark_ids"]
        cells = {(c["benchmark_id"], c["model"]): c for c in manifest["cells"] if c["sheet_id"] == sheet["sheet_id"]}
        models = [m for m in manifest["models"] if (ids[0], m["model_id"]) in cells]
        if sheet.get("model_ids"):
            order = {route: n for n, route in enumerate(sheet["model_ids"])}
            models.sort(key=lambda m: order.get(m["model_id"], 999))
        else:
            models.sort(key=lambda m: -(cells[ids[0], m["model_id"]].get("reported_score") or 0))
        heads = "".join(f'<th>{e(manifest["benchmarks"][b]["name"])}<br>/{manifest["benchmarks"][b]["report_scale"]:g}</th>' for b in ids)
        rows = []
        for model in models:
            values = []
            for b in ids:
                cell = cells.get((b, model["model_id"]), {})
                score = cell.get("reported_score")
                value = f"{score:.2f}" if score is not None and cell.get("status") == "ok" else "N/A"
                if cell.get("ci95"):
                    value += f'<br><small>95% [{cell["ci95"][0]:.2f}, {cell["ci95"][1]:.2f}]</small>'
                values.append(f"<td>{value}</td>")
            mode = cells[ids[0], model["model_id"]].get("input_mode", "")
            label = "V · native images" if mode == "vision" else "T · frozen text" if mode else ""
            rows.append(f'<tr><th>{e(model["display"])}<br><small>{label}</small></th>{"".join(values)}</tr>')
        sections.append(f'<section><h2>{e(sheet["name"])}</h2><p>{e(sheet["description"])}</p><div class="scroll"><table><thead><tr><th>Model</th>{heads}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></section>')
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Science Arena Static Scores</title><style>body{font:14px system-ui;margin:20px;color:#263347}section{margin:24px 0}p{line-height:1.5}table{border-collapse:collapse}th,td{border:1px solid #d9ded8;padding:9px;text-align:left;white-space:nowrap}thead{background:#f0f4f1}small{font-weight:normal}.scroll{overflow:auto}</style><h1>Science Arena</h1><p>Static score fallback · 2026 release and archived results</p>' + "".join(sections) + '</html>\n'
    (DATA / "fallback.html").write_text(page, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "scripts/sources/2026")
    args = parser.parse_args()
    scores = load(args.source / "table6_scores.json")
    ci = load(args.source / "table6_bootstrap_macro_ci.json")
    analysis = load(args.source / "analysis_manifest.json")
    expected = {Path(line.split()[1].lstrip("*")).name: line.split()[0] for line in (args.source / "SHA256SUMS").read_text().splitlines() if line.strip()}
    hashes = {}
    for name in ("table6_scores.json", "table6_bootstrap_macro_ci.json", "analysis_manifest.json"):
        hashes[name] = hashlib.sha256((args.source / name).read_bytes()).hexdigest()
        require(hashes[name] == expected[name], f"Source checksum mismatch: {name}")
    for source in (scores, ci, analysis):
        require(source.get("publication_eligible") is True and source.get("deep_protocol_audit_complete") is True, "Source is not independently sealed for publication")
    require(scores["competition_order"] == list(COUNTS), "Unexpected competition roster")
    require(len(scores["rows"]) == 14 and len(ci["rows"]) == 14, "Expected 14 routes")
    intervals = {r["route"]: r for r in ci["rows"]}
    require(len(intervals) == 14 and {r["route"] for r in scores["rows"]} == set(intervals), "Route mismatch")
    manifest = load(DATA / "manifest.json")
    manifest["sheets"] = [s for s in manifest["sheets"] if s["sheet_id"] != SHEET]
    manifest["cells"] = [c for c in manifest["cells"] if c["sheet_id"] != SHEET]
    for benchmark in [OVERALL, *COUNTS]:
        manifest["benchmarks"].pop(benchmark, None)
    # Preserve archived numbers and identifiers, correcting their erroneous year labels.
    for benchmark in ("nbpho2025", "usapho2025"):
        b = manifest["benchmarks"][benchmark]
        b["name"] = b["name"].replace("2026", "2025")
        b["release_date"] = "2025 (archived; exact public date unverified)"
    for sheet in manifest["sheets"]:
        if sheet["sheet_id"] == "international_core":
            sheet["name"] = "Archived International"
            sheet["description"] = "Archived manual-evaluation scores and official human reference rows. Timing alone does not establish absence of training exposure."
        elif sheet["sheet_id"] == "extended_suite":
            sheet["name"] = "Archived Extended"
            sheet["description"] = "May 2026 text-only interleaved archive; NBPhO and USAPhO inputs are from 2025. These scores use an older protocol and are separate from the sealed 2026 release."
    model_ids = [r["route"] for r in scores["rows"]]
    manifest["sheets"].insert(0, {"sheet_id": SHEET, "name": "2026 Competitions", "description": NOTE, "benchmark_ids": [OVERALL, *COUNTS], "score_benchmark_ids": list(COUNTS), "model_ids": model_ids, "show_usage": False, "show_problem_cells": False})
    for contest, count in COUNTS.items():
        manifest["benchmarks"][contest] = {"benchmark_id": contest, "name": scores["rows"][0]["competitions"][contest]["display_name"], "discipline": "chemistry" if contest == "icho2026" else "physics", "report_scale": scores["explicit_raw_maxima"][contest], "max_score": scores["explicit_raw_maxima"][contest], "turn_count": count, "turns": [], "source_quality": "independently_sealed_2026_release", "reference_cutoffs": {}}
    manifest["benchmarks"][OVERALL] = {"benchmark_id": OVERALL, "name": "Overall · 2026", "overall": True, "report_scale": 100, "max_score": 100, "source_benchmark_ids": list(COUNTS)}
    for row in scores["rows"]:
        route = row["route"]
        if not any(m["model_id"] == route for m in manifest["models"]):
            manifest["models"].append({"model_id": route, "display": row["display_name"], "provider": route.split("/")[0]})
        percentages = []
        for contest, count in COUNTS.items():
            value = row["competitions"][contest]
            require(value["complete"] and not value["missing"], f"Incomplete {route}/{contest}")
            require(value["raw_max"] == scores["explicit_raw_maxima"][contest] and math.isfinite(value["score"]) and 0 <= value["score"] <= value["raw_max"], "Invalid score or maximum")
            pct = value["score"] / value["raw_max"] * 100
            require(math.isclose(pct, value["normalized_percent"], abs_tol=1e-9), "Normalized score mismatch")
            percentages.append(pct)
            manifest["cells"].append({"sheet_id": SHEET, "benchmark_id": contest, "model": route, "status": "ok", "score": value["score"], "reported_score": value["score"], "max_score": value["raw_max"], "report_scale": value["raw_max"], "pct": pct / 100, "turn_count": count, "expected_turn_count": count, "input_mode": row["input_mode"], "detail_path": "", "contamination": ""})
        macro = sum(percentages) / 4
        interval = intervals[route]
        require(math.isclose(macro, row["macro_mean_percent"], abs_tol=1e-9) and math.isclose(macro, interval["point_macro_mean_percent"], abs_tol=1e-9), "Macro mismatch")
        bounds = [interval["ci95_lower_percent"], interval["ci95_upper_percent"]]
        require(all(math.isfinite(v) for v in bounds) and 0 <= bounds[0] <= bounds[1] <= 100, "Invalid interval")
        manifest["cells"].append({"sheet_id": SHEET, "benchmark_id": OVERALL, "model": route, "status": "ok", "score": macro, "reported_score": macro, "max_score": 100, "report_scale": 100, "pct": macro / 100, "overall": True, "source_benchmark_ids": list(COUNTS), "input_mode": row["input_mode"], "ci95": bounds, "detail_path": ""})
    for contest in [OVERALL, *COUNTS]:
        ranked = sorted((c for c in manifest["cells"] if c["sheet_id"] == SHEET and c["benchmark_id"] == contest), key=lambda c: -c["reported_score"])
        previous = None
        for n, cell in enumerate(ranked, 1):
            if previous is None or cell["reported_score"] != previous:
                rank = n
            cell["rank"] = rank
            previous = cell["reported_score"]
    manifest["default_sheet"] = SHEET
    manifest["default_benchmark"] = OVERALL
    manifest["benchmark_order"] = [b for s in manifest["sheets"] for b in s["benchmark_ids"]]
    manifest["release_2026"] = {"source_commit": SOURCE_COMMIT, "source_sha256": hashes, "sealed_at": "2026-08-29", "release_tag": "cr-final-2026-08-31", "links": [{"label": "Code & reproducibility", "url": REPO}, {"label": "Score source", "url": f"{REPO}/blob/{SOURCE_COMMIT}/results/2026/table6/table6_scores.md"}, {"label": "Raw records & images", "url": f"{REPO}/releases/tag/cr-final-2026-08-31"}]}
    detail_index_path = DATA / "2026/index.json"
    if detail_index_path.is_file():
        details = load(detail_index_path)
        require(details["source_commit"] == SOURCE_COMMIT and details["score_source_sha256"] == hashes["table6_scores.json"], "Details are bound to a different score release")
        detail_cells = {(c["benchmark_id"], c["model"]): c for c in details["cells"]}
        available_contests = set(details["benchmarks"])
        unavailable_contests = set(details.get("unavailable", {}))
        require(available_contests.isdisjoint(unavailable_contests) and available_contests | unavailable_contests == set(COUNTS), "Incomplete detail availability metadata")
        require(len(detail_cells) == 14 * len(available_contests), "Expected a complete 14-route detail roster for each available competition")
        for contest, count in COUNTS.items():
            if contest in unavailable_contests:
                manifest["benchmarks"][contest]["show_problem_cells"] = False
                manifest["benchmarks"][contest]["detail_unavailable_note"] = details["unavailable"][contest]["note"]
                continue
            info = details["benchmarks"][contest]
            require(len(info["turns"]) == count and len({t["turn_id"] for t in info["turns"]}) == count, "Detail turn coverage mismatch")
            manifest["benchmarks"][contest]["turns"] = info["turns"]
            manifest["benchmarks"][contest]["show_problem_cells"] = True
        for cell in manifest["cells"]:
            if cell["sheet_id"] == SHEET and cell["benchmark_id"] in available_contests:
                detail = detail_cells[cell["benchmark_id"], cell["model"]]
                require(len(detail["turn_scores"]) == COUNTS[cell["benchmark_id"]], "Detail score coverage mismatch")
                cell.update({k: detail[k] for k in ("detail_path", "shared_path", "turn_scores")})
        manifest["sheets"][0]["show_problem_cells"] = True
    write(DATA / "manifest.json", manifest)
    fallback(manifest)
    print("Synced 56 sealed 2026 competition cells and 14 macro/CI rows; zero raw downloads or API calls.")


if __name__ == "__main__":
    main()
