#!/usr/bin/env python3
"""Build a thin public detail view from checksum-bound release records in CI."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter
import hashlib
import json
import math
import posixpath
import re
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "scripts/sources/2026"
SELECTED = ("inputs-2026", "runs-table6-ipho-icho", "runs-table6-nbpho-usapho")
OUTPUT = ROOT / "static/data/2026"


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", str(value)).strip("._") or "unnamed"


def canonical_path(name):
    marker = "experiments/2026_reval/"
    if marker in name:
        return name[name.index(marker):]
    return str(PurePosixPath(name))


def emit(path, value):
    data = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    # The public exporter is an allowlist, never a copy of provider wire data.
    for marker in (b'"reasoning_content":', b'"raw_response":', b'"raw_response_storage":', b'"attempt_files":', b'/Users/', b'/home/runner/'):
        require(marker not in data, f"Private/raw field in public output: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def download(row, directory, release):
    path = directory / row["filename"]
    url = f'https://github.com/{release["repository"]}/releases/download/{release["tag"]}/{row["filename"]}'
    for attempt in range(3):
        try:
            digest = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=90) as source, path.open("wb") as target:
                while chunk := source.read(1024 * 1024):
                    target.write(chunk)
                    digest.update(chunk)
            require(path.stat().st_size == row["bytes"], "Archive size mismatch")
            require(digest.hexdigest() == row["sha256"], "Archive checksum mismatch")
            print(f'Verified archive {row["filename"]} ({row["bytes"]} bytes)', flush=True)
            return path
        except Exception:
            path.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def archive_members(path):
    import zstandard
    if path.suffix == ".zip":
        class ZipAdapter:
            def __init__(self, archive):
                self.archive = archive

            def extractfile(self, member):
                return self.archive.open(member.info)

        class ZipMember:
            def __init__(self, info):
                self.info = info
                self.size = info.file_size
                self.linkname = ""

            def isfile(self):
                return not self.info.is_dir()

            def issym(self):
                return False

            def islnk(self):
                return False

        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                name = str(PurePosixPath(member.filename))
                require(not name.startswith("/") and ".." not in PurePosixPath(name).parts, "Unsafe ZIP path")
                yield ZipAdapter(archive), ZipMember(member), name
        return
    with path.open("rb") as source, zstandard.ZstdDecompressor().stream_reader(source) as stream:
        with tarfile.open(fileobj=stream, mode="r|") as archive:
            for member in archive:
                name = str(PurePosixPath(member.name))
                require(not name.startswith("/") and ".." not in PurePosixPath(name).parts, "Unsafe archive path")
                yield archive, member, name


def inspect(paths, analysis):
    results = {}
    for path in paths:
        if path.name.endswith(".json.zst"):
            import zstandard
            with path.open("rb") as handle, zstandard.ZstdDecompressor().stream_reader(handle) as stream:
                obj = json.load(stream)
            results[path.name] = {"json_keys": list(obj) if isinstance(obj, dict) else [], "matched_sealed_records": {}, "samples": {}, "roots": {}}
            continue
        roots = Counter()
        links = {}
        matches = {s["competition_key"]: {"solver": 0, "judge": 0, "items": False} for s in analysis["sources"]}
        samples = {}
        for archive, member, name in archive_members(path):
            if member.issym() or member.islnk():
                links[name] = member.linkname
            if not member.isfile():
                continue
            roots["/".join(name.split("/")[:4])] += 1
            for spec in analysis["sources"]:
                contest = spec["competition_key"]
                if name == spec["items_path"]:
                    data = archive.extractfile(member).read()
                    require(hashlib.sha256(data).hexdigest() == spec["items_sha256"], "Frozen items mismatch")
                    matches[contest]["items"] = True
                for stage in ("solver", "judge"):
                    if name.startswith(spec["run_root"] + "/" + stage + "/") and name.endswith(".json") and "-attempts/" not in name:
                        matches[contest][stage] += 1
                        key = contest + "/" + stage
                        if key not in samples:
                            obj = json.load(archive.extractfile(member))
                            samples[key] = {"path": name, "keys": list(obj), "fields": {k: obj[k] for k in ("terminal", "status", "route", "solver_route", "item_id", "score", "max_score") if k in obj}, "parsed_keys": list(obj.get("parsed") or {})}
        results[path.name] = {"roots": dict(roots), "links": links, "matched_sealed_records": matches, "samples": samples}
    print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)


def collect(paths, analysis):
    """Read whitelisted terminal files; resolve reuse links within the archives."""
    items = {}
    records = {}
    hashes = {}
    links = {}
    item_paths = {s["items_path"]: s for s in analysis["sources"]}
    terminal_pattern = re.compile(r"^experiments/2026_reval/runs/[^/]+/(solver|judge)/[^/]+/[^/]+/[^/]+/[^/]+[.]json$")
    for path in paths:
        if path.name.endswith(".json.zst"):
            continue
        for archive, member, raw_name in archive_members(path):
            name = canonical_path(raw_name)
            if member.issym() or member.islnk():
                target = member.linkname
                if not target.startswith("/") and not target.startswith("experiments/"):
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
                target = canonical_path(target)
                require(target.startswith("experiments/2026_reval/"), "Reuse link must stay inside archived inputs/runs")
                links[name] = target
                continue
            if not member.isfile():
                continue
            selected = name in item_paths or terminal_pattern.match(name) or name.endswith("/aggregate.json") or name.startswith("MANIFEST.")
            if not selected:
                continue
            data = archive.extractfile(member).read()
            digest = hashlib.sha256(data).hexdigest()
            if name in hashes:
                require(hashes[name] == digest, f"Conflicting copies of {name}")
                continue
            hashes[name] = digest
            if name in item_paths:
                spec = item_paths[name]
                require(digest == spec["items_sha256"], f"Frozen item checksum mismatch: {spec['competition_key']}")
                items[spec["competition_key"]] = [json.loads(line) for line in data.splitlines() if line.strip()]
            else:
                records[name] = json.loads(data)
    require(set(items) == {s["competition_key"] for s in analysis["sources"]}, "Frozen canonical items are missing")

    def resolve(name):
        seen = set()
        for _ in range(20):
            if name in records:
                return records[name], hashes[name], name
            require(name not in seen, "Reuse link cycle")
            seen.add(name)
            prefixes = [prefix for prefix in links if name == prefix or name.startswith(prefix + "/")]
            if not prefixes:
                return None, None, name
            prefix = max(prefixes, key=len)
            name = links[prefix] + name[len(prefix):]
        raise ValueError("Too many reuse links")

    return items, resolve


def image_catalog(paths, items):
    needed = {}
    descriptors = {}
    for rows in items.values():
        for item in rows:
            for key in ("question_image_paths", "official_solution_image_paths"):
                for name in item.get(key, []):
                    needed[canonical_path(name)] = None
            for key in ("question_image_assets", "official_solution_image_assets", "question_image_refs", "official_solution_image_refs"):
                for asset in item.get(key, []):
                    if isinstance(asset, dict) and asset.get("path"):
                        descriptors[canonical_path(asset["path"])] = asset
    images = {}
    for path in paths:
        if path.name.endswith(".json.zst"):
            continue
        for archive, member, raw_name in archive_members(path):
            name = canonical_path(raw_name)
            if not member.isfile() or name not in needed or name in images:
                continue
            data = archive.extractfile(member).read()
            require(data.startswith(b"\x89PNG\r\n\x1a\n"), f"Expected original PNG: {name}")
            digest = hashlib.sha256(data).hexdigest()
            asset = descriptors.get(name, {})
            expected = asset.get("sha256") or asset.get("image_sha256")
            if expected:
                require(digest == expected, f"Image changed: {name}")
            target = OUTPUT / "images" / (digest + ".png")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            page = asset.get("source_page") or asset.get("source_pdf_page")
            images[name] = {"src": str(target.relative_to(ROOT)), "sha256": digest, "label": f"Frozen source page {page}" if page else "Frozen reference page", "bytes": len(data)}
    require(set(images) == set(needed), f"Missing frozen images: {sorted(set(needed) - set(images))[:5]}")
    return images


def criterion_feedback(parsed):
    if parsed is None:
        return None
    fields = ("score", "max_score", "credit_summary", "deductions", "uncertain", "arithmetic_validated")
    result = {k: parsed[k] for k in fields if k in parsed}
    criteria_fields = ("criterion_id", "criterion", "max_score", "awarded", "candidate_evidence_quote", "reason")
    result["criteria"] = [{k: c[k] for k in criteria_fields if k in c} for c in parsed.get("criteria", [])]
    return result


def build(paths, analysis, release, allow_missing=False):
    scores = read(SOURCES / "table6_scores.json")
    items, resolve = collect(paths, analysis)
    counts = {"ipho2026": 23, "icho2026": 68, "nbpho2026": 28, "usapho2026": 34}
    selected = {}
    missing = []
    available_specs = []
    unavailable = {}
    for spec in analysis["sources"]:
        contest = spec["competition_key"]
        require(len(items[contest]) == counts[contest], f"Wrong item count: {contest}")
        aggregate, digest, origin = resolve(spec["aggregate_path"])
        if aggregate is None:
            missing.append(spec["aggregate_path"])
            unavailable[contest] = {"missing_run_root": spec["run_root"], "note": f'The final {"v8" if contest == "nbpho2026" else "v5"} per-question records are absent from the published release. Competition totals remain available; the earlier archived grades belong to a different run.'}
            continue
        else:
            if digest != spec["aggregate_sha256"]:
                print(f'Aggregate archive serialization differs from the analysis snapshot: {contest}; archive={digest}; analysis={spec["aggregate_sha256"]}. Checking all released numeric rows and terminal totals.', flush=True)
            for model in scores["rows"]:
                value = aggregate.get("aggregates", {}).get(model["route"], {}).get(items[contest][0]["benchmark_id"])
                require(isinstance(value, dict) and value.get("complete") is True, f"Incomplete archived aggregate row: {contest}/{model['route']}")
                require(value.get("score") is not None and math.isclose(float(value["score"]), model["competitions"][contest]["score"], abs_tol=1e-7), f"Archived aggregate does not match the released score: {contest}/{model['route']}")
        available_specs.append(spec)
        for model in scores["rows"]:
            route = model["route"]
            for item in items[contest]:
                pair = []
                for stage in ("solver", "judge"):
                    name = f'{spec["run_root"]}/{stage}/{safe_name(route)}/{safe_name(item["benchmark_id"])}/{safe_name(item["sequence_id"])}/{safe_name(item["item_id"])}.json'
                    record, digest, origin = resolve(name)
                    if record is None:
                        missing.append(name)
                    pair.append((record, digest, origin))
                selected[contest, route, item["item_id"]] = pair
    terminal_missing = [name for name in missing if not name.endswith("/aggregate.json")]
    require(not terminal_missing, f"Missing sealed terminal records: {terminal_missing[:5]}")
    require(not missing or allow_missing, f"Release is missing sealed runs: {missing}")
    images = image_catalog(paths, {spec["competition_key"]: items[spec["competition_key"]] for spec in available_specs})
    index = {"schema_version": "science_arena_2026_detail_index_v1", "source_commit": "c2a2acc4e311a8a7b0530de087fbf4e1b5cafe8c", "score_source_sha256": hashlib.sha256((SOURCES / "table6_scores.json").read_bytes()).hexdigest(), "benchmarks": {}, "cells": [], "unavailable": unavailable}
    report = {"schema_version": "science_arena_2026_detail_build_v1", "source_assets": {row["filename"]: row["sha256"] for row in release["assets"] if row["filename"] in {p.name for p in paths}}, "verified_cells": [], "output_sha256": {}, "model_answer_count": 0, "judge_record_count": 0, "missing_final_runs": unavailable, "missing_paths": missing}
    for spec in available_specs:
        contest = spec["competition_key"]
        rows = items[contest]
        by_sequence = {}
        for item in rows:
            by_sequence.setdefault(item["sequence_id"], []).append(item)
        factors = {}
        for sequence, group in by_sequence.items():
            raw_max = sum(float(item["max_score"]) for item in group)
            declared = {float(item["problem_raw_max"]) for item in group if item.get("problem_raw_max") is not None}
            require(len(declared) <= 1 and (not declared or math.isclose(next(iter(declared)), raw_max, abs_tol=1e-8)), f"Inconsistent raw maximum: {sequence}")
            weighted = any("problem_weight" in item for item in rows)
            weights = {float(item["problem_weight"]) for item in group} if weighted else {raw_max}
            require(len(weights) == 1, f"Inconsistent competition weight: {sequence}")
            factors[sequence] = next(iter(weights)) / raw_max
        natural_scale = sum(float(item["max_score"]) * factors[item["sequence_id"]] for item in rows)
        require(math.isclose(natural_scale, scores["explicit_raw_maxima"][contest], abs_tol=1e-8), "Competition scale mismatch")
        refs = [{"turn_id": item["item_id"], "label": item["item_id"].removeprefix(item["benchmark_id"].removesuffix("_theory") + "_"), "sequence_id": item["sequence_id"], "turn_index": item["turn_index"], "max_score": item["max_score"], "objective": False} for item in rows]
        shared = {"benchmark_id": contest, "turns": []}
        for item, ref in zip(rows, refs):
            caveats = []
            for key in ("rubric_type", "official_rubric_status", "official_answer_status", "gold_solution_status", "derived_rubric_status"):
                if item.get(key):
                    caveats.append(key + ": " + str(item[key]))
            for key in ("question_source", "solution_source"):
                if isinstance(item.get(key), dict) and item[key].get("provenance_status"):
                    caveats.append(key + ": " + item[key]["provenance_status"])
            shared["turns"].append({**ref, "question": item["question_text_native"], "question_staticized": item["question_text_staticized"], "question_images": [images[canonical_path(name)] for name in item.get("question_image_paths", [])], "solution_images": [images[canonical_path(name)] for name in item.get("official_solution_image_paths", [])], "reference_answer": item.get("reference_answer"), "official_answer": item.get("official_answer"), "official_solution": item.get("gold_solution") or item.get("official_solution"), "official_rubric": item.get("grading_rubric") or item.get("official_rubric"), "caveats": caveats})
        shared_path = OUTPUT / "questions" / (contest + ".json")
        report["output_sha256"][str(shared_path.relative_to(ROOT))] = emit(shared_path, shared)
        index["benchmarks"][contest] = {"turns": refs, "shared_path": str(shared_path.relative_to(ROOT))}
        for model in scores["rows"]:
            route = model["route"]
            output = {"benchmark": {"benchmark_id": contest}, "model": {"model_id": route, "display": model["display_name"], "input_mode": model["input_mode"]}, "turns": []}
            raw_scores = []
            contributions = []
            for item, ref in zip(rows, refs):
                (solver, solver_hash, solver_path), (judge, judge_hash, judge_path) = selected[contest, route, item["item_id"]]
                for record in (solver, judge):
                    require(record.get("terminal") is True and record.get("item_id") == item["item_id"] and record.get("benchmark_id") == item["benchmark_id"], "Terminal identity mismatch")
                require(solver.get("route") == judge.get("solver_route") == route, "Terminal route mismatch")
                require(solver.get("input_mode") == model["input_mode"], "Input mode mismatch")
                require(isinstance(solver.get("candidate_answer"), str), "Visible model answer missing")
                score = judge["score"]
                maximum = item["max_score"]
                require(score is not None and math.isfinite(float(score)) and 0 <= float(score) <= float(maximum), "Missing/invalid item score")
                require(math.isclose(float(judge["max_score"]), float(maximum), abs_tol=1e-9), "Judge maximum mismatch")
                parsed = judge.get("parsed")
                if parsed:
                    require(math.isclose(float(parsed["score"]), float(score), abs_tol=1e-9), "Parsed score mismatch")
                    require(math.isclose(sum(float(c["awarded"]) for c in parsed["criteria"]), float(score), abs_tol=1e-9), "Criterion sum mismatch")
                else:
                    require(float(score) == 0 and "no_answer" in judge.get("status", ""), "Unexpected missing feedback")
                    parsed = {"score": 0, "max_score": maximum, "criteria": [], "credit_summary": "Deterministic zero: the solver did not submit a usable answer; no judge API call was made.", "uncertain": False}
                ratio = float(score) / float(maximum)
                contribution = float(score) * factors[item["sequence_id"]]
                contributions.append(contribution)
                raw_scores.append(score)
                output["turns"].append({"turn_id": item["item_id"], "score": score, "max_score": maximum, "ratio": ratio, "verdict": "correct" if ratio >= 1 - 1e-9 else "wrong" if ratio <= 1e-9 else "partial", "candidate_answer": solver["candidate_answer"], "judge_model": judge.get("judge_route") or "google/gemini-3.5-flash", "judge_result": criterion_feedback(parsed), "solver_status": solver["status"], "judge_status": judge["status"], "competition_score": contribution, "competition_max_score": float(maximum) * factors[item["sequence_id"]], "source_terminal_sha256": {"solver": solver_hash, "judge": judge_hash}})
                report["model_answer_count"] += 1
                report["judge_record_count"] += 1
            total = sum(contributions)
            expected = model["competitions"][contest]["score"]
            require(math.isclose(total, expected, abs_tol=1e-7), f"Published total mismatch: {contest}/{route}: {total} != {expected}")
            detail_path = OUTPUT / "models" / contest / (safe_name(route) + ".json")
            report["output_sha256"][str(detail_path.relative_to(ROOT))] = emit(detail_path, output)
            index["cells"].append({"benchmark_id": contest, "model": route, "detail_path": str(detail_path.relative_to(ROOT)), "shared_path": str(shared_path.relative_to(ROOT)), "turn_scores": raw_scores})
            report["verified_cells"].append({"benchmark_id": contest, "model": route, "published_score": expected, "reconstructed_score": total, "turn_count": len(rows)})
    expected_count = len(scores["rows"]) * sum(counts[spec["competition_key"]] for spec in available_specs)
    require(report["model_answer_count"] == report["judge_record_count"] == expected_count, "Incomplete public detail coverage for an available sealed run")
    report["png_count"] = len({image["sha256"] for image in images.values()})
    report["output_sha256"][str((OUTPUT / "index.json").relative_to(ROOT))] = emit(OUTPUT / "index.json", index)
    emit(OUTPUT / "build_report.json", report)
    print(f'PASS: {len(index["cells"])} cells, {expected_count} visible answers/grades, every available published total reconstructed, {report["png_count"]} original PNGs.', flush=True)
    if unavailable:
        print('Unavailable final runs (explicitly documented, no substitute scores): ' + ', '.join(unavailable), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--allow-missing-runs", action="store_true", help="Publish fully verified available runs and explicitly document missing final runs")
    args = parser.parse_args()
    release = read(SOURCES / "release_assets.json")
    analysis = read(SOURCES / "analysis_manifest.json")
    rows = [row for row in release["assets"] if args.inspect or row["name"] in SELECTED]
    with tempfile.TemporaryDirectory(prefix="science-arena-release-") as temporary:
        with ThreadPoolExecutor(max_workers=3) as pool:
            paths = list(pool.map(lambda row: download(row, Path(temporary), release), rows))
        if args.inspect:
            inspect(paths, analysis)
        else:
            build(paths, analysis, release, args.allow_missing_runs)


if __name__ == "__main__":
    main()
