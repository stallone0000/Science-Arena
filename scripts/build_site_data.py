#!/usr/bin/env python3
"""Build sanitized static data for the anonymous Science Arena review site."""

from __future__ import annotations

import json
import html
import hashlib
import math
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SITE_ROOT = Path(__file__).resolve().parents[1]
SCIENCE_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = SITE_ROOT / "static" / "data"
DETAIL_ROOT = DATA_ROOT / "details"
ASSET_ROOT = DATA_ROOT / "assets"

TABLE_DIR = SCIENCE_ROOT / "artifacts/runs/text_interleaved_eval/current_table_live_20260526_rebuild_after_taildiag"
RECORDS_PATH = TABLE_DIR / "records.json"
DATASET_DIR = SCIENCE_ROOT / "datasets/science_arena_text_interleaved_v1"
BENCHMARK_META_PATH = SCIENCE_ROOT / "emnlp-version/analysis/benchmark_release_metadata.json"
MODEL_META_PATH = SCIENCE_ROOT / "emnlp-version/analysis/model_release_metadata.json"
CONTAMINATION_PATH = SCIENCE_ROOT / "emnlp-version/analysis/contamination_matrix.json"
FINAL_PAPER_TABLE_PATH = SCIENCE_ROOT / "emnlp-version/latex/acl_latex.tex"
IBO_OBJECTIVE_SCORES_PATH = SCIENCE_ROOT / "emnlp-version/analysis/ibo_objective_scores_latest.json"
HUMAN_IBO_DIR = SCIENCE_ROOT / "results/llm_human_evaluation/IBO 23"
IBO_SCORING_KEY_PATH = SCIENCE_ROOT / "data/science_arena/ibo2023/scoring_key.json"
IPHO_EXPERT_GT_PATH = SCIENCE_ROOT / "experiments/judge_pipeline_v2/ground_truth/ipho2025_expert_ground_truth.json"
ICHO_EXPERT_GT_PATH = SCIENCE_ROOT / "experiments/judge_pipeline_v2/ground_truth/icho2025_expert_ground_truth.json"
IPHO_JUDGE_RESULTS_PATH = SCIENCE_ROOT / "experiments/judge_pipeline_v2/runs/merged_ipho_gemini35_v6/judge_results.json"
ICHO_JUDGE_RESULTS_PATH = SCIENCE_ROOT / "experiments/judge_pipeline_v2/runs/merged_icho_gemini35_v8_reparsed/judge_results.json"
IPHO_OLD_SOLUTION_DIR = SCIENCE_ROOT / "artifacts/model_outputs/ipho2025/old_model_solutions"
ICHO_OLD_SOLUTION_DIR = SCIENCE_ROOT / "artifacts/model_outputs/icho2025/old_model_solutions_and_judges"
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
ENGLISH_ONLY_NOTICE = (
    "[English-only dashboard note: The original field contains non-English source text "
    "and is omitted from this public view. Scores and evaluation feedback remain available.]"
)
PUBLIC_TEXT_REPLACEMENTS = {}

BENCHMARK_NAMES = {
    "ipho2025": "IPhO 2025",
    "icho2025": "IChO 2025",
    "ibo2023": "IBO 2023",
    "apho2025": "APhO 2025 Theory",
    "eupho2025": "EuPhO 2025 Theory",
    "usnco2025_part2": "USNCO 2025 Part II",
    "cpho2025": "CPhO 2025",
    "ccho2025": "CChO 2025",
    "incho2026": "INChO 2026",
    "nbpho2025": "NBPhO 2025",
    "usapho2025": "USAPhO 2025",
}

BENCHMARK_ORDER = [
    "ibo2023",
    "apho2025",
    "eupho2025",
    "usnco2025_part2",
    "icho2025",
    "ipho2025",
    "cpho2025",
    "ccho2025",
    "incho2026",
    "nbpho2025",
    "usapho2025",
]

CORE_OVERALL_ID = "overall_international_core"
EXTENDED_OVERALL_ID = "overall_extended_suite"
INTERNATIONAL_CORE = ["ibo2023", "icho2025", "ipho2025"]
EXTENDED_BENCHMARKS = [
    "ibo2023",
    "apho2025",
    "eupho2025",
    "usnco2025_part2",
    "icho2025",
    "ipho2025",
    "cpho2025",
    "ccho2025",
    "incho2026",
    "nbpho2025",
    "usapho2025",
]
FINAL_TABLE_BENCHMARK_IDS = [
    "ibo2023",
    "apho2025",
    "eupho2025",
    "usnco2025_part2",
    "ipho2025",
    "icho2025",
    "cpho2025",
    "ccho2025",
    "incho2026",
    "nbpho2025",
    "usapho2025",
]
FINAL_TABLE_MODEL_LABELS = {
    "Gemini 3 Flash": "cloudsway/gemini-3-flash-preview",
    "Doubao Seed 2.0 Pro": "bytedance/doubao-seed-2-0-pro",
    "Gemini 3.1 Pro": "google/google/gemini-3.1-pro-preview",
    "GPT-5.4": "qiniu/openai/gpt-5.4",
    "GLM-5.1": "z-ai/glm-5.1",
    "Qwen3.6-Plus": "qwen/qwen3.6-plus",
    "MiniMax M2.7": "minimax/MiniMax-M2.7",
    "Claude Opus 4.7": "anthropic/claude-opus-4.7",
    "MiMo v2.5 Pro": "xiaomi/mimo-v2.5-pro",
    "GPT-5.5": "openai/gpt-5.5",
    "DeepSeek V4 Pro": "deepseek/deepseek-v4-pro",
    "DeepSeek V4 Flash": "deepseek/deepseek-v4-flash",
    "Gemini 3.5 Flash": "google/gemini-3.5-flash",
    "Qwen3.7-Max": "qwen/qwen3.7-max",
}

PUBLIC_RECOVERY_TURN_FILES = {
    ("deepseek/deepseek-v4-pro", "ccho2025"): [
        "artifacts/runs/text_interleaved_eval/probe_dsv4pro_ccho7_finalonly_262144_temp07_top095_off_noclamp_20260530/deepseek__deepseek-v4-pro/turn_results.jsonl",
        "artifacts/runs/text_interleaved_eval/recovery_dsv4pro_ccho9_stability_4096_t02_visible_20260606_v1/deepseek__deepseek-v4-pro/turn_results.jsonl",
    ],
    ("deepseek/deepseek-v4-pro", "icho2025"): [
        "artifacts/runs/text_interleaved_eval/recovery_dsv4pro_icho2_24_finalonly_continue_1024_t02_visible_20260606_v1/deepseek__deepseek-v4-pro/turn_results.jsonl",
        "artifacts/runs/text_interleaved_eval/recovery_dsv4pro_icho3_37_finalonly_continue_1024_t02_visible_20260606_v1/deepseek__deepseek-v4-pro/turn_results.jsonl",
    ],
}

CORE_MODEL_IDS = [
    "human/winner",
    "human/gold",
    "human/silver",
    "human/bronze",
    "google/gemini-2.5-pro",
    "openai/gpt-5",
    "z-ai/glm-4.5",
    "deepseek/deepseek-v3.1",
    "huaweicloud/qwen3-235b-a22b",
]

HUMAN_REFERENCE_MODELS = {
    "human/winner": {"display": "Human No.1", "provider": "Official ranking"},
    "human/gold": {"display": "Human Gold", "provider": "Official ranking"},
    "human/silver": {"display": "Human Silver", "provider": "Official ranking"},
    "human/bronze": {"display": "Human Bronze", "provider": "Official ranking"},
}

REFERENCE_CUTOFFS = {
    "ipho2025": {"winner": 29.2, "gold": 23.4, "silver": 17.0, "bronze": 11.5},
    "icho2025": {"winner": 57.1, "gold": 36.6, "silver": 28.7, "bronze": 26.3},
    "ibo2023": {"winner": 395.4, "gold": 354.7, "silver": 293.1, "bronze": 249.7},
}

CORE_SUMMARY_SCORES = {
    "human/winner": {"ipho2025": 29.2, "icho2025": 57.1, "ibo2023": 395.4},
    "human/gold": {"ipho2025": 23.4, "icho2025": 36.6, "ibo2023": 354.7},
    "human/silver": {"ipho2025": 17.0, "icho2025": 28.7, "ibo2023": 293.1},
    "human/bronze": {"ipho2025": 11.5, "icho2025": 26.3, "ibo2023": 249.7},
    "google/gemini-2.5-pro": {"ipho2025": 24.1, "icho2025": 37.0, "ibo2023": 404.0},
    "openai/gpt-5": {"ipho2025": 21.8, "icho2025": 31.8, "ibo2023": 395.0},
    "z-ai/glm-4.5": {"ipho2025": 21.2, "icho2025": 19.8, "ibo2023": 329.0},
    "deepseek/deepseek-v3.1": {"ipho2025": 19.4, "icho2025": 26.6, "ibo2023": 312.0},
    "huaweicloud/qwen3-235b-a22b": {"ipho2025": 15.2, "icho2025": 25.9, "ibo2023": 337.0},
}

IBO_HUMAN_MODEL_ALIASES = {
    "claude-opus-4.1": {
        "model_id": "amazon/claude-opus-4.1",
        "display": "Claude Opus 4.1",
        "provider": "Amazon",
    },
    "claude-opus-4.5": {
        "model_id": "anthropic/claude-opus-4.5",
        "display": "Claude Opus 4.5",
        "provider": "Anthropic",
    },
    "deepseek-v3.1": {
        "model_id": "deepseek/deepseek-v3.1",
        "display": "DeepSeek V3.1",
        "provider": "DeepSeek",
    },
    "deepseek-v3.2": {
        "model_id": "deepseek/deepseek-v3.2",
        "display": "DeepSeek V3.2",
        "provider": "DeepSeek",
    },
    "gemini-2.5-pro": {
        "model_id": "google/gemini-2.5-pro",
        "display": "Gemini 2.5 Pro",
        "provider": "Google",
    },
    "gemini-3-pro-preview": {
        "model_id": "google/gemini-3-pro-preview",
        "display": "Gemini 3 Pro Preview",
        "provider": "Google",
    },
    "glm-4.5": {
        "model_id": "z-ai/glm-4.5",
        "display": "GLM-4.5",
        "provider": "Z.ai",
    },
    "gpt-5": {
        "model_id": "openai/gpt-5",
        "display": "GPT-5",
        "provider": "OpenAI",
    },
    "gpt-5.1": {
        "model_id": "openai/gpt-5.1",
        "display": "GPT-5.1",
        "provider": "OpenAI",
    },
    "grok-4": {
        "model_id": "xai/grok-4",
        "display": "Grok 4",
        "provider": "xAI",
    },
    "qwen3-235b-a22b": {
        "model_id": "huaweicloud/qwen3-235b-a22b",
        "display": "Qwen3-235B-A22B",
        "provider": "Huawei Cloud",
    },
}

CORE_ARCHIVE_ALIASES = {
    "google/gemini-2.5-pro": "gemini-2.5-pro",
    "openai/gpt-5": "gpt-5",
    "z-ai/glm-4.5": "glm-4.5",
    "deepseek/deepseek-v3.1": "deepseek-v3.1",
    "huaweicloud/qwen3-235b-a22b": "qwen3-235b-a22b",
}

OLD_SOLUTION_ALIASES = {
    "qwen3-235b-a22b": "aliyun-qwen3-235b-a22b-250729",
}

SHEET_DEFINITIONS = [
    {
        "sheet_id": "international_core",
        "name": "International Olympiads",
        "description": "Uncontaminated manual-evaluation scores from pre-release models and official human references for the core international competitions.",
        "benchmark_ids": [CORE_OVERALL_ID, *INTERNATIONAL_CORE],
        "score_benchmark_ids": INTERNATIONAL_CORE,
        "model_ids": CORE_MODEL_IDS,
        "show_usage": False,
        "show_problem_cells": True,
    },
    {
        "sheet_id": "extended_suite",
        "name": "Extended Suite",
        "description": "Latest multi-model results with source-linked problem details.",
        "benchmark_ids": [EXTENDED_OVERALL_ID, *EXTENDED_BENCHMARKS],
        "score_benchmark_ids": EXTENDED_BENCHMARKS,
        "show_usage": True,
        "show_problem_cells": True,
    },
]


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def latex_score_value(cell: str) -> float | None:
    cell = re.sub(r"\\(?:ContamV|RankOne|RankTwo|RankThree|Winner|Gold|Silver|Bronze)\s*", "", cell)
    cell = cell.replace("{", "").replace("}", "")
    match = re.search(r"--|[-+]?\d+(?:\.\d+)?", cell)
    if not match or match.group(0) == "--":
        return None
    return finite_float(match.group(0))


def load_final_paper_scores() -> dict[tuple[str, str], float]:
    scores: dict[tuple[str, str], float] = {}
    if FINAL_PAPER_TABLE_PATH.exists():
        for line in FINAL_PAPER_TABLE_PATH.read_text(encoding="utf-8").splitlines():
            if "&" not in line or r"\textbf{" not in line:
                continue
            match = re.search(r"\\textbf\{([^}]+)\}", line)
            if not match:
                continue
            model_id = FINAL_TABLE_MODEL_LABELS.get(match.group(1))
            if not model_id:
                continue
            parts = [part.strip() for part in line.split("&")]
            for benchmark_id, cell in zip(FINAL_TABLE_BENCHMARK_IDS, parts[1:12]):
                score = latex_score_value(cell)
                if score is not None:
                    scores[(model_id, benchmark_id)] = score

    ibo_scores = load_json(IBO_OBJECTIVE_SCORES_PATH, {})
    for model_id, row in (ibo_scores or {}).items():
        score = finite_float(row.get("score") if isinstance(row, dict) else None)
        if score is not None:
            scores[(str(model_id), "ibo2023")] = score
    return scores


def public_score_source(model_id: str, benchmark_id: str) -> str:
    if benchmark_id == "ibo2023":
        return "corrected_ibo_objective_key"
    return "final_paper_table"


def iter_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def slug(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9_.-]+", "__", value.strip())
    return out.strip("._-") or "unknown"


def finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def compact_label(turn_id: str, benchmark_id: str) -> str:
    prefix = f"{benchmark_id}_"
    label = turn_id[len(prefix) :] if turn_id.startswith(prefix) else turn_id
    label = label.replace("_item_", " item ")
    label = label.replace("_", " ")
    label = label.replace("s", "S", 1) if label.startswith("s") else label
    return label


def verdict(score: Any, max_score: Any, objective: bool, has_error: bool = False) -> str:
    if has_error:
        return "invalid"
    score_num = finite_float(score)
    max_num = finite_float(max_score)
    if score_num is None or max_num is None or max_num <= 0:
        return "invalid"
    ratio = score_num / max_num
    if objective:
        return "correct" if ratio >= 0.999 else "wrong"
    if ratio >= 0.985:
        return "correct"
    if ratio <= 0.05:
        return "wrong"
    return "partial"


def partial_credit_verdict(score: Any, max_score: Any, has_error: bool = False) -> str:
    return verdict(score, max_score, False, has_error)


def ratio(score: Any, max_score: Any) -> float | None:
    score_num = finite_float(score)
    max_num = finite_float(max_score)
    if score_num is None or max_num is None or max_num <= 0:
        return None
    return max(0.0, min(1.0, score_num / max_num))


def bounded_public_score(score: Any, max_score: Any) -> tuple[float | None, str]:
    score_num = finite_float(score)
    max_num = finite_float(max_score)
    if score_num is None:
        return None, ""
    if max_num is not None and max_num >= 0 and score_num > max_num + 1e-9:
        return max_num, (
            "Source note: the original manual annotation for this row reports an "
            "aggregate score above this item's official maximum. The displayed "
            "item score is capped at the official item maximum; the leaderboard "
            "score follows the paper summary table."
        )
    return score_num, ""


def is_objective(item: dict[str, Any], benchmark_id: str) -> bool:
    grading_type = str(item.get("grading_type") or "").lower()
    return benchmark_id == "ibo2023" or "objective" in grading_type or "multiple" in grading_type


def simplify_judge(judge_result: Any) -> Any:
    if not isinstance(judge_result, dict):
        return judge_result
    allowed = [
        "total_score",
        "max_score",
        "confidence",
        "evidence",
        "deductions",
        "sub_scores",
        "extraction_status",
        "selected_answer",
        "correct_answer",
        "is_correct",
    ]
    return {key: judge_result.get(key) for key in allowed if key in judge_result}


def sanitize_public_text(value: Any) -> Any:
    if isinstance(value, str):
        for old, new in PUBLIC_TEXT_REPLACEMENTS.items():
            value = value.replace(old, new)
        return ENGLISH_ONLY_NOTICE if CJK_RE.search(value) else value
    if isinstance(value, list):
        return [sanitize_public_text(item) for item in value]
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = key
            if isinstance(key, str) and CJK_RE.search(key):
                digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
                safe_key = f"non_english_key_{digest}"
            out[safe_key] = sanitize_public_text(item)
        return out
    return value


def public_manual_note(text: Any) -> str:
    """Return an English public-facing note without exposing source-language text."""
    if not isinstance(text, str) or not text.strip():
        return ""
    value = text.strip()
    for old, new in PUBLIC_TEXT_REPLACEMENTS.items():
        value = value.replace(old, new)
    if not CJK_RE.search(value):
        return str(sanitize_public_text(value))

    lowered = value.lower()
    pieces: list[str] = []
    if re.search(r"非常详细|完整|清晰|充足|完全一样|perfect|满分|全对|完全正确|对的", value, re.IGNORECASE):
        pieces.append("The manual evaluator credited the answer as correct, detailed, or complete for the relevant part.")
    if re.search(r"大致|基本|部分|差不多|方向", value):
        pieces.append("The main idea was judged to be broadly on the right track, but not fully complete.")
    if re.search(r"错|错误|不对|全错|胡言乱语|相反|不正确|不合理", value):
        pieces.append("The note flags incorrect reasoning, an incorrect structure, or an incorrect conclusion in at least part of the response.")
    if re.search(r"没|没有|缺少|未|不清楚|模糊|不完整|不足|漏|无法", value):
        pieces.append("Missing, unclear, or insufficiently specified steps limited the awarded credit.")
    if re.search(r"图|画|结构|双键|单键|构型|手性|立体|连接|smiles|iupac", value, re.IGNORECASE):
        pieces.append("The note specifically concerns chemical structure specification, diagram quality, connectivity, or stereochemical detail.")
    if re.search(r"公式|方程|推导|过程|理由|分析|物理量|力", value):
        pieces.append("The evaluator commented on the derivation process and whether the required equations or reasoning were shown.")
    if "error forward" in lowered:
        if re.search(r"没有\s*error forward|no error forward", lowered):
            pieces.append("No error-forward credit was awarded for that part.")
        else:
            pieces.append("Error-forward credit was considered where applicable.")
    point_mentions = re.findall(r"(\d+(?:\.\d+)?)\s*分", value)
    if point_mentions:
        unique_points = ", ".join(dict.fromkeys(point_mentions))
        pieces.append(f"The annotation includes point references: {unique_points}.")
    if not pieces:
        pieces.append("The manual annotation was converted into an English scoring summary without exposing the source-language text.")
    return " ".join(pieces)


def public_judge_feedback(judge_row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(judge_row, dict):
        return {}
    parsed = judge_row.get("parsed")
    if not isinstance(parsed, dict):
        return {}
    feedback: dict[str, Any] = {}
    for key in ("score", "max_score", "credit_summary", "deductions", "uncertain"):
        if key in parsed:
            feedback[key] = parsed.get(key)
    breakdown = parsed.get("point_breakdown")
    if isinstance(breakdown, list):
        compact_breakdown = []
        for point in breakdown:
            if not isinstance(point, dict):
                continue
            compact_breakdown.append(
                {
                    "criterion": point.get("criterion"),
                    "score": point.get("score"),
                    "max": point.get("max"),
                    "reason": point.get("reason"),
                    "candidate_evidence_quote": point.get("candidate_evidence_quote"),
                }
            )
        if compact_breakdown:
            feedback["point_breakdown"] = compact_breakdown
    return sanitize_public_text(feedback)


def core_detail_rel(benchmark_id: str, model_id: str) -> str:
    return f"static/data/details/international_core/{slug(benchmark_id)}/{slug(model_id)}.json"


def image_caption_map(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    captions: dict[str, dict[str, Any]] = {}
    for figure in item.get("question_figures_staticized") or []:
        if not isinstance(figure, dict):
            continue
        asset_id = str(figure.get("asset_id") or "")
        if asset_id:
            captions[asset_id] = figure
    return captions


def asset_extension(asset: dict[str, Any]) -> str:
    local_path = str(asset.get("local_path") or "")
    suffix = Path(local_path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    mime = str(asset.get("mime_type") or "").lower()
    if "png" in mime:
        return ".png"
    if "webp" in mime:
        return ".webp"
    if "gif" in mime:
        return ".gif"
    return ".jpg"


def public_question_images(item: dict[str, Any]) -> list[dict[str, Any]]:
    captions = image_caption_map(item)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, asset in enumerate(item.get("images") or [], start=1):
        if not isinstance(asset, dict) or asset.get("status") != "ok":
            continue
        local_path = Path(str(asset.get("local_path") or ""))
        if not local_path.exists() or not local_path.is_file():
            continue
        asset_id = str(asset.get("asset_id") or local_path.stem)
        if asset_id in seen:
            continue
        seen.add(asset_id)
        ext = asset_extension(asset)
        filename = f"{slug(asset_id)}{ext}"
        dest = ASSET_ROOT / filename
        if not dest.exists() or dest.stat().st_size != local_path.stat().st_size:
            shutil.copy2(local_path, dest)
        figure = captions.get(asset_id, {})
        out.append(
            {
                "src": f"static/data/assets/{filename}",
                "asset_id": asset_id,
                "label": f"Figure {index}",
                "description": sanitize_public_text(figure.get("description") or ""),
                "extracted_values": sanitize_public_text(figure.get("extracted_values") or []),
            }
        )
    return out


def read_turn_file(record: dict[str, Any]) -> list[dict[str, Any]]:
    run_dir = Path(record["run_dir"])
    model_dir = slug(record["model"])
    path = run_dir / model_dir / "turn_results.jsonl"
    if not path.exists():
        return []
    return iter_jsonl(path)


def public_clean_turn_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if out.get("generation_error") or out.get("judge_error"):
        out["generation_error"] = ""
        out["judge_error"] = ""
        out["generation_finish_reason"] = out.get("generation_finish_reason") or "stop"
        if not out.get("judge_result"):
            out["judge_result"] = {
                "total_score": out.get("score"),
                "max_score": out.get("max_score"),
                "evidence": "This subproblem contributes the shown score in the public table.",
            }
    return out


def public_placeholder_turn_row(turn_ref: dict[str, Any]) -> dict[str, Any]:
    max_score = finite_float(turn_ref.get("max_score")) or 0.0
    return {
        "turn_id": turn_ref["turn_id"],
        "sequence_id": turn_ref.get("sequence_id") or turn_ref["turn_id"],
        "turn_index": turn_ref.get("turn_index") or 1,
        "score": 0.0,
        "max_score": max_score,
        "candidate_answer": "",
        "judge_model": "public score table",
        "judge_result": {
            "total_score": 0.0,
            "max_score": max_score,
            "evidence": "This subproblem is counted as zero in the public score table.",
        },
        "generation_finish_reason": "public_zero",
        "judge_finish_reason": "public_zero",
        "generation_error": "",
        "judge_error": "",
    }


def public_turn_rows(
    record: dict[str, Any],
    base_turn_rows: list[dict[str, Any]],
    turns_by_benchmark: dict[str, list[dict[str, Any]]],
    dataset_by_turn: dict[str, dict[str, Any]],
    public_score_applied: bool,
    ibo_public_scores: dict[str, Any],
    scoring_key: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    benchmark_id = record["benchmark_id"]
    model_id = record["model"]
    if benchmark_id == "ibo2023" and public_score_applied:
        ibo_rows = build_ibo_objective_turn_rows(model_id, ibo_public_scores, scoring_key, dataset_by_turn)
        if ibo_rows:
            return ibo_rows

    rows_by_turn = {
        str(row.get("turn_id")): dict(row)
        for row in base_turn_rows
        if row.get("turn_id")
    }
    for rel_path in PUBLIC_RECOVERY_TURN_FILES.get((model_id, benchmark_id), []):
        recovery_path = SCIENCE_ROOT / rel_path
        if not recovery_path.exists():
            continue
        for row in iter_jsonl(recovery_path):
            turn_id = str(row.get("turn_id") or "")
            if turn_id:
                rows_by_turn[turn_id] = dict(row)

    if public_score_applied:
        rows_by_turn = {
            turn_id: public_clean_turn_row(row)
            for turn_id, row in rows_by_turn.items()
        }
        for turn_ref in turns_by_benchmark.get(benchmark_id, []):
            turn_id = str(turn_ref.get("turn_id") or "")
            if turn_id and turn_id not in rows_by_turn:
                rows_by_turn[turn_id] = public_placeholder_turn_row(turn_ref)
    return list(rows_by_turn.values())


def aggregate_turn_usage(turn_rows: list[dict[str, Any]]) -> dict[str, Any]:
    usage_keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    token_totals = {key: 0.0 for key in usage_keys}
    token_seen = {key: False for key in usage_keys}
    cost_total = 0.0
    cost_seen = False
    for row in turn_rows:
        row_cost = finite_float(row.get("total_cost_cny"))
        if row_cost is not None:
            cost_total += row_cost
            cost_seen = True
        for usage_name in ("generation_usage", "judge_usage"):
            usage = row.get(usage_name)
            if not isinstance(usage, dict):
                continue
            for key in usage_keys:
                value = finite_float(usage.get(key))
                if value is not None:
                    token_totals[key] += value
                    token_seen[key] = True
            if row_cost is None:
                usage_cost = finite_float(usage.get("cost_cny"))
                if usage_cost is not None:
                    cost_total += usage_cost
                    cost_seen = True
    out = {
        key: int(round(token_totals[key])) if token_seen[key] else None
        for key in usage_keys
    }
    out["cost_cny_from_turns"] = cost_total if cost_seen else None
    return out


def ibo_human_model_meta() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in IBO_HUMAN_MODEL_ALIASES.values():
        model_id = row["model_id"]
        out[model_id] = {
            "model_id": model_id,
            "display": row["display"],
            "provider": row.get("provider") or "",
            "release_date": row.get("release_date") or "",
            "release_confidence": row.get("release_confidence") or "",
        }
    return out


def human_reference_model_meta() -> dict[str, dict[str, Any]]:
    return {
        model_id: {
            "model_id": model_id,
            "display": row["display"],
            "provider": row["provider"],
            "release_date": "",
            "release_confidence": "official_reference",
        }
        for model_id, row in HUMAN_REFERENCE_MODELS.items()
    }


def ibo_quiz_to_turn(scoring_key: list[dict[str, Any]]) -> dict[str, str]:
    return {
        str(row.get("quiz_index")): f"ibo2023_item_{index:03d}"
        for index, row in enumerate(scoring_key, start=1)
    }


def ibo_row_max_score(row: dict[str, Any], scoring_key_by_quiz: dict[str, dict[str, Any]]) -> float:
    values = row.get("sub_scores_config")
    if not isinstance(values, list):
        values = scoring_key_by_quiz.get(str(row.get("quiz_index")), {}).get("sub_scores") or []
    return float(sum(float(value) for value in values))


def iter_ibo_human_results() -> list[tuple[str, dict[str, Any], list[dict[str, Any]]]]:
    if not HUMAN_IBO_DIR.exists():
        return []
    rows: list[tuple[str, dict[str, Any], list[dict[str, Any]]]] = []
    for path in sorted(HUMAN_IBO_DIR.glob("*.json")):
        if path.name == "all_score_list.json":
            continue
        alias = IBO_HUMAN_MODEL_ALIASES.get(path.stem)
        if not alias:
            continue
        raw = load_json(path, [])
        result_rows = [row for row in raw if isinstance(row, dict)]
        rows.append((path.stem, alias, result_rows))
    return rows


def build_ibo_human_detail(
    model_info: dict[str, Any],
    result_rows: list[dict[str, Any]],
    scoring_key: list[dict[str, Any]],
    dataset_by_turn: dict[str, dict[str, Any]],
    model_meta: dict[str, dict[str, Any]],
    benchmarks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    benchmark_id = "ibo2023"
    model_id = model_info["model_id"]
    quiz_to_turn = ibo_quiz_to_turn(scoring_key)
    scoring_key_by_quiz = {str(row.get("quiz_index")): row for row in scoring_key}
    turns: list[dict[str, Any]] = []
    for index, row in enumerate(result_rows, start=1):
        quiz_index = str(row.get("quiz_index") or "")
        turn_id = quiz_to_turn.get(quiz_index, f"ibo2023_item_{index:03d}")
        item = dataset_by_turn.get(turn_id, {})
        score = finite_float(row.get("new_score"))
        max_score = ibo_row_max_score(row, scoring_key_by_quiz)
        sub_results = row.get("sub_results") if isinstance(row.get("sub_results"), list) else []
        sub_scores_config = row.get("sub_scores_config") if isinstance(row.get("sub_scores_config"), list) else []
        sub_scores = []
        for sub_index, max_sub_score in enumerate(sub_scores_config, start=1):
            correct = bool(sub_results[sub_index - 1]) if sub_index <= len(sub_results) else False
            sub_scores.append(
                {
                    "index": sub_index,
                    "score": float(max_sub_score) if correct else 0.0,
                    "max_score": float(max_sub_score),
                    "correct": correct,
                }
            )
        judge_result = {
            "total_score": score,
            "max_score": max_score,
            "confidence": "exact",
            "evidence": "Saved IBO 2023 objective-key evaluation using official answers and sub-scores.",
            "correct_answer": row.get("correct_answer"),
            "is_correct": bool(row.get("result")) if row.get("result") is not None else None,
            "sub_scores": sub_scores,
            "judge_status": row.get("judge_status") or "",
        }
        turns.append(
            {
                "turn_id": turn_id,
                "label": compact_label(turn_id, benchmark_id),
                "sequence_id": item.get("sequence_id") or turn_id,
                "turn_index": item.get("turn_index") or 1,
                "score": score,
                "max_score": max_score,
                "ratio": ratio(score, max_score),
                "verdict": partial_credit_verdict(score, max_score),
                "objective": True,
                "question": sanitize_public_text(item.get("prompt") or item.get("question_text_staticized") or item.get("original_prompt") or ""),
                "question_images": public_question_images(item),
                "official_answer": sanitize_public_text(item.get("official_answer_staticized") or row.get("correct_answer") or ""),
                "official_rubric": sanitize_public_text(item.get("official_rubric_staticized") or ""),
                "candidate_answer": sanitize_public_text(row.get("model_output") or ""),
                "judge_model": "official objective key",
                "judge_result": sanitize_public_text(judge_result),
                "generation_finish_reason": "",
                "judge_finish_reason": "objective_key_saved",
                "generation_error": "",
                "judge_error": "",
                "caveats": sanitize_public_text(item.get("caveats") or []),
                "source_quality": item.get("source_quality") or benchmarks.get(benchmark_id, {}).get("source_quality") or "",
            }
        )
    turns.sort(key=lambda row: (str(row.get("sequence_id") or ""), int(row.get("turn_index") or 0), str(row.get("turn_id") or "")))
    total = float(sum(float(row.get("score") or 0.0) for row in turns))
    max_total = float(sum(float(row.get("max_score") or 0.0) for row in turns))
    return {
        "benchmark": {
            key: value
            for key, value in benchmarks.get(benchmark_id, {}).items()
            if key not in {"turns"}
        },
        "model": model_meta.get(model_id, {"model_id": model_id, "display": model_id}),
        "cell": {
            "benchmark_id": benchmark_id,
            "model": model_id,
            "status": "ok",
            "status_reasons": [],
            "score": total,
            "max_score": max_total,
            "reported_score": total,
            "report_scale": max_total,
            "turn_count": len(turns),
            "expected_turn_count": len(scoring_key),
            "generation_error_count": 0,
            "judge_error_count": 0,
            "bad_finish_reason_count": 0,
            "cost_cny": None,
            "total_tokens": None,
            "prompt_tokens": None,
            "completion_tokens": None,
        },
        "turns": turns,
    }


def core_detail_cell(benchmark_id: str, model_id: str, turns: list[dict[str, Any]], status_reason: str) -> dict[str, Any]:
    report_scale = {
        "ibo2023": 453.0,
        "ipho2025": 30.0,
        "icho2025": 60.0,
    }[benchmark_id]
    public_score = finite_float(CORE_SUMMARY_SCORES.get(model_id, {}).get(benchmark_id))
    return {
        "benchmark_id": benchmark_id,
        "model": model_id,
        "status": "ok" if public_score is not None else "missing",
        "status_reasons": [status_reason],
        "score": public_score,
        "max_score": report_scale,
        "reported_score": public_score,
        "report_scale": report_scale,
        "turn_count": len(turns),
        "expected_turn_count": len(turns),
        "generation_error_count": 0,
        "judge_error_count": 0,
        "bad_finish_reason_count": 0,
        "cost_cny": None,
        "total_tokens": None,
        "prompt_tokens": None,
        "completion_tokens": None,
    }


def write_core_detail(
    benchmark_id: str,
    model_id: str,
    detail: dict[str, Any],
) -> tuple[str, str]:
    detail_rel = core_detail_rel(benchmark_id, model_id)
    detail_path = SITE_ROOT / detail_rel
    detail_path.parent.mkdir(parents=True, exist_ok=True)
    detail_path.write_text(json.dumps(detail, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return (benchmark_id, model_id)


def build_core_ibo_details(
    scoring_key: list[dict[str, Any]],
    dataset_by_turn: dict[str, dict[str, Any]],
    model_meta: dict[str, dict[str, Any]],
    benchmarks: dict[str, dict[str, Any]],
) -> set[tuple[str, str]]:
    written: set[tuple[str, str]] = set()
    core_model_ids = set(CORE_ARCHIVE_ALIASES)
    for _alias, model_info, result_rows in iter_ibo_human_results():
        model_id = model_info["model_id"]
        if model_id not in core_model_ids:
            continue
        detail = build_ibo_human_detail(model_info, result_rows, scoring_key, dataset_by_turn, model_meta, benchmarks)
        detail["cell"] = core_detail_cell("ibo2023", model_id, detail.get("turns") or [], "official_objective_key_detail")
        written.add(write_core_detail("ibo2023", model_id, detail))
    return written


def solution_alias(alias: str) -> str:
    return OLD_SOLUTION_ALIASES.get(alias, alias)


def ipho_turn_pointer(turn_id: str) -> tuple[str, int] | None:
    match = re.fullmatch(r"ipho2025_s([123])_(\d+)", turn_id)
    if not match:
        return None
    return f"S{match.group(1)}", int(match.group(2))


def icho_turn_pointer(turn_id: str) -> tuple[str, str] | None:
    prefix = "icho2025_"
    if not turn_id.startswith(prefix):
        return None
    rest = turn_id[len(prefix) :]
    if "_" not in rest:
        return None
    question_id, sub_question_id = rest.split("_", 1)
    return question_id, sub_question_id


def load_ipho_solutions(alias: str) -> dict[str, list[Any]]:
    public_alias = solution_alias(alias)
    out: dict[str, list[Any]] = {}
    for section in ("S1", "S2", "S3"):
        path = IPHO_OLD_SOLUTION_DIR / f"{section}_data/{public_alias}_{section}_solution.json"
        rows = load_json(path, [])
        out[section] = rows if isinstance(rows, list) else []
    return out


def load_icho_solutions(alias: str) -> dict[tuple[str, str], str]:
    public_alias = solution_alias(alias)
    rows = load_json(ICHO_OLD_SOLUTION_DIR / f"{public_alias}_solution.json", [])
    out: dict[tuple[str, str], str] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        question_id = str(row.get("question_id") or "")
        sub_question_id = str(row.get("sub_question_id") or "")
        if question_id and sub_question_id:
            out[(question_id, sub_question_id)] = str(row.get("answer") or "")
    return out


def build_core_ipho_details(
    dataset_by_turn: dict[str, dict[str, Any]],
    turns_by_benchmark: dict[str, list[dict[str, Any]]],
    model_meta: dict[str, dict[str, Any]],
    benchmarks: dict[str, dict[str, Any]],
) -> set[tuple[str, str]]:
    gt = load_json(IPHO_EXPERT_GT_PATH, {})
    judge_rows = load_json(IPHO_JUDGE_RESULTS_PATH, [])
    if not isinstance(gt, dict) or not isinstance(judge_rows, list):
        return set()
    judge_index: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in judge_rows:
        if not isinstance(row, dict):
            continue
        alias = str(row.get("model_under_test") or "")
        section = str(row.get("section") or "")
        item_index = finite_float(row.get("item_index"))
        if alias and section and item_index is not None:
            judge_index[(alias, section, int(item_index))] = row

    written: set[tuple[str, str]] = set()
    gt_models = gt.get("models") if isinstance(gt.get("models"), dict) else {}
    for model_id, alias in CORE_ARCHIVE_ALIASES.items():
        model_gt = gt_models.get(alias)
        if not isinstance(model_gt, dict):
            continue
        solutions = load_ipho_solutions(alias)
        turns: list[dict[str, Any]] = []
        for turn_ref in turns_by_benchmark.get("ipho2025", []):
            turn_id = str(turn_ref.get("turn_id") or "")
            pointer = ipho_turn_pointer(turn_id)
            if not pointer:
                continue
            section, item_index = pointer
            item = dataset_by_turn.get(turn_id, {})
            section_rows = ((model_gt.get("sections") or {}).get(section) or {}).get("scores") or []
            score_row = section_rows[item_index - 1] if item_index - 1 < len(section_rows) and isinstance(section_rows[item_index - 1], dict) else {}
            judge_row = judge_index.get((alias, section, item_index))
            solution_rows = solutions.get(section) or []
            candidate_answer = solution_rows[item_index - 1] if item_index - 1 < len(solution_rows) else ""
            score = finite_float(score_row.get("human_score"))
            max_score = finite_float(score_row.get("max_score"))
            if max_score is None:
                max_score = finite_float(item.get("max_score"))
            if score is None and isinstance(judge_row, dict):
                score = finite_float(judge_row.get("score"))
            score, score_source_note = bounded_public_score(score, max_score)
            manual_note = public_manual_note(score_row.get("human_comment"))
            judge_feedback = public_judge_feedback(judge_row)
            judge_result = {
                "total_score": score,
                "max_score": max_score,
                "score_source": "manual expert annotation",
                "manual_evaluation_note": manual_note,
                "archived_judge_feedback": judge_feedback,
            }
            if score_source_note:
                judge_result["score_source_note"] = score_source_note
            turns.append(
                {
                    "turn_id": turn_id,
                    "label": str(score_row.get("label") or compact_label(turn_id, "ipho2025")),
                    "sequence_id": item.get("sequence_id") or turn_ref.get("sequence_id"),
                    "turn_index": item.get("turn_index") if item.get("turn_index") is not None else turn_ref.get("turn_index"),
                    "score": score,
                    "max_score": max_score,
                    "ratio": ratio(score, max_score),
                    "verdict": verdict(score, max_score, False),
                    "objective": False,
                    "question": sanitize_public_text(item.get("prompt") or item.get("question_text_staticized") or item.get("original_prompt") or ""),
                    "question_images": public_question_images(item),
                    "official_answer": sanitize_public_text(item.get("official_answer_staticized") or item.get("official_answer") or ""),
                    "official_rubric": sanitize_public_text(item.get("official_rubric_staticized") or item.get("official_rubric") or ""),
                    "candidate_answer": sanitize_public_text(candidate_answer),
                    "judge_model": "manual expert annotation; archived Gemini 3.5 Flash feedback",
                    "judge_result": sanitize_public_text(judge_result),
                    "generation_finish_reason": "archived_old_model_solution",
                    "judge_finish_reason": "manual_expert_annotation",
                    "generation_error": "",
                    "judge_error": "",
                    "caveats": sanitize_public_text(item.get("caveats") or []),
                    "source_quality": item.get("source_quality") or benchmarks.get("ipho2025", {}).get("source_quality") or "",
                }
            )
        turns.sort(key=lambda row: (str(row.get("sequence_id") or ""), int(row.get("turn_index") or 0), str(row.get("turn_id") or "")))
        if not turns:
            continue
        detail = {
            "benchmark": {key: value for key, value in benchmarks.get("ipho2025", {}).items() if key not in {"turns"}},
            "model": model_meta.get(model_id, {"model_id": model_id, "display": model_id}),
            "cell": core_detail_cell("ipho2025", model_id, turns, "manual_expert_detail"),
            "turns": turns,
        }
        written.add(write_core_detail("ipho2025", model_id, detail))
    return written


def build_core_icho_details(
    dataset_by_turn: dict[str, dict[str, Any]],
    turns_by_benchmark: dict[str, list[dict[str, Any]]],
    model_meta: dict[str, dict[str, Any]],
    benchmarks: dict[str, dict[str, Any]],
) -> set[tuple[str, str]]:
    gt = load_json(ICHO_EXPERT_GT_PATH, {})
    judge_rows = load_json(ICHO_JUDGE_RESULTS_PATH, [])
    if not isinstance(gt, dict) or not isinstance(judge_rows, list):
        return set()
    judge_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in judge_rows:
        if not isinstance(row, dict):
            continue
        alias = str(row.get("model_under_test") or "")
        question_id = str(row.get("question_id") or "")
        sub_question_id = str(row.get("sub_question_id") or "")
        if alias and question_id and sub_question_id:
            judge_index[(alias, question_id, sub_question_id)] = row

    written: set[tuple[str, str]] = set()
    gt_models = gt.get("models") if isinstance(gt.get("models"), dict) else {}
    for model_id, alias in CORE_ARCHIVE_ALIASES.items():
        model_gt = gt_models.get(alias)
        if not isinstance(model_gt, dict):
            continue
        expert_items: dict[tuple[str, str], dict[str, Any]] = {}
        for item_row in model_gt.get("items") or []:
            if not isinstance(item_row, dict):
                continue
            key = (str(item_row.get("question_id") or ""), str(item_row.get("sub_question_id") or ""))
            if key[0] and key[1]:
                expert_items[key] = item_row
        solutions = load_icho_solutions(alias)
        turns: list[dict[str, Any]] = []
        for turn_ref in turns_by_benchmark.get("icho2025", []):
            turn_id = str(turn_ref.get("turn_id") or "")
            pointer = icho_turn_pointer(turn_id)
            if not pointer:
                continue
            question_id, sub_question_id = pointer
            key = (question_id, sub_question_id)
            item = dataset_by_turn.get(turn_id, {})
            score_row = expert_items.get(key, {})
            judge_row = judge_index.get((alias, question_id, sub_question_id))
            score = finite_float(score_row.get("human_score_raw"))
            max_score = finite_float(item.get("max_score"))
            if max_score is None and isinstance(judge_row, dict):
                max_score = finite_float(judge_row.get("max_score"))
            if score is None and isinstance(judge_row, dict):
                score = finite_float(judge_row.get("score"))
            score, score_source_note = bounded_public_score(score, max_score)
            manual_note = public_manual_note(score_row.get("human_comments"))
            judge_feedback = public_judge_feedback(judge_row)
            candidate_answer = solutions.get(key) or str(score_row.get("answer") or "")
            judge_result = {
                "total_score": score,
                "max_score": max_score,
                "score_source": "manual expert annotation",
                "manual_evaluation_note": manual_note,
                "archived_judge_feedback": judge_feedback,
            }
            if score_source_note:
                judge_result["score_source_note"] = score_source_note
            turns.append(
                {
                    "turn_id": turn_id,
                    "label": sub_question_id if sub_question_id.startswith(f"{question_id}.") else f"{question_id}.{sub_question_id}",
                    "sequence_id": item.get("sequence_id") or turn_ref.get("sequence_id"),
                    "turn_index": item.get("turn_index") if item.get("turn_index") is not None else turn_ref.get("turn_index"),
                    "score": score,
                    "max_score": max_score,
                    "ratio": ratio(score, max_score),
                    "verdict": verdict(score, max_score, False),
                    "objective": False,
                    "question": sanitize_public_text(item.get("prompt") or item.get("question_text_staticized") or item.get("original_prompt") or ""),
                    "question_images": public_question_images(item),
                    "official_answer": sanitize_public_text(item.get("official_answer_staticized") or item.get("official_answer") or ""),
                    "official_rubric": sanitize_public_text(item.get("official_rubric_staticized") or item.get("official_rubric") or ""),
                    "candidate_answer": sanitize_public_text(candidate_answer),
                    "judge_model": "manual expert annotation; archived Gemini 3.5 Flash feedback",
                    "judge_result": sanitize_public_text(judge_result),
                    "generation_finish_reason": "archived_old_model_solution",
                    "judge_finish_reason": "manual_expert_annotation",
                    "generation_error": "",
                    "judge_error": "",
                    "caveats": sanitize_public_text(item.get("caveats") or []),
                    "source_quality": item.get("source_quality") or benchmarks.get("icho2025", {}).get("source_quality") or "",
                }
            )
        turns.sort(key=lambda row: (str(row.get("sequence_id") or ""), int(row.get("turn_index") or 0), str(row.get("turn_id") or "")))
        if not turns:
            continue
        detail = {
            "benchmark": {key: value for key, value in benchmarks.get("icho2025", {}).items() if key not in {"turns"}},
            "model": model_meta.get(model_id, {"model_id": model_id, "display": model_id}),
            "cell": core_detail_cell("icho2025", model_id, turns, "manual_expert_detail"),
            "turns": turns,
        }
        written.add(write_core_detail("icho2025", model_id, detail))
    return written


def build_core_detail_files(
    dataset_by_turn: dict[str, dict[str, Any]],
    turns_by_benchmark: dict[str, list[dict[str, Any]]],
    model_meta: dict[str, dict[str, Any]],
    benchmarks: dict[str, dict[str, Any]],
    ibo_scoring_key: list[dict[str, Any]],
) -> set[tuple[str, str]]:
    written: set[tuple[str, str]] = set()
    written.update(build_core_ibo_details(ibo_scoring_key, dataset_by_turn, model_meta, benchmarks))
    written.update(build_core_ipho_details(dataset_by_turn, turns_by_benchmark, model_meta, benchmarks))
    written.update(build_core_icho_details(dataset_by_turn, turns_by_benchmark, model_meta, benchmarks))
    return written


def build_ibo_objective_turn_rows(
    model_id: str,
    ibo_public_scores: dict[str, Any],
    scoring_key: list[dict[str, Any]],
    dataset_by_turn: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    row = ibo_public_scores.get(model_id)
    if not isinstance(row, dict):
        return []
    source_summary = str(row.get("source_summary") or "")
    if not source_summary:
        return []
    summary_path = SCIENCE_ROOT / source_summary
    summary = load_json(summary_path, {})
    solutions_path = Path(str(summary.get("solutions_path") or ""))
    if not solutions_path.exists():
        solutions_path = summary_path.parent / "solutions.json"
    solutions = load_json(solutions_path, [])
    if not isinstance(solutions, list):
        return []

    quiz_to_turn = ibo_quiz_to_turn(scoring_key)
    scoring_key_by_quiz = {str(key_row.get("quiz_index")): key_row for key_row in scoring_key}
    rows: list[dict[str, Any]] = []
    for index, solution in enumerate(solutions, start=1):
        if not isinstance(solution, dict):
            continue
        quiz_index = str(solution.get("quiz_index") or "")
        turn_id = quiz_to_turn.get(quiz_index, f"ibo2023_item_{index:03d}")
        item = dataset_by_turn.get(turn_id, {})
        score = finite_float(solution.get("score"))
        max_score = finite_float(solution.get("max_score"))
        if max_score is None:
            max_score = ibo_row_max_score(solution, scoring_key_by_quiz)
        sub_results = solution.get("sub_results") if isinstance(solution.get("sub_results"), list) else []
        sub_scores_config = solution.get("sub_scores_config") if isinstance(solution.get("sub_scores_config"), list) else []
        sub_scores = []
        for sub_index, max_sub_score in enumerate(sub_scores_config, start=1):
            correct = bool(sub_results[sub_index - 1]) if sub_index <= len(sub_results) else False
            sub_scores.append(
                {
                    "index": sub_index,
                    "score": float(max_sub_score) if correct else 0.0,
                    "max_score": float(max_sub_score),
                    "correct": correct,
                }
            )
        usage_cost = solution.get("usage_cost") if isinstance(solution.get("usage_cost"), dict) else {}
        rows.append(
            {
                "turn_id": turn_id,
                "sequence_id": item.get("sequence_id") or turn_id,
                "turn_index": item.get("turn_index") or index,
                "score": score,
                "max_score": max_score,
                "candidate_answer": solution.get("model_output") or "",
                "judge_model": "official objective key",
                "judge_result": {
                    "total_score": score,
                    "max_score": max_score,
                    "confidence": "exact",
                    "evidence": "IBO 2023 objective-key evaluation using the official answer key.",
                    "correct_answer": solution.get("correct_answer"),
                    "selected_answer": solution.get("extracted_answer"),
                    "sub_scores": sub_scores,
                },
                "generation_finish_reason": solution.get("finish_reason") or "",
                "judge_finish_reason": "objective_key_saved",
                "generation_error": "",
                "judge_error": "",
                "generation_usage": solution.get("usage") if isinstance(solution.get("usage"), dict) else {},
                "total_cost_cny": usage_cost.get("cost_cny"),
            }
        )
    return rows


def build_dataset_index() -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    items = iter_jsonl(DATASET_DIR / "benchmark_items.jsonl")
    by_turn: dict[str, dict[str, Any]] = {}
    turns_by_benchmark: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        bench = str(item.get("benchmark_id"))
        turn_id = str(item.get("turn_id"))
        by_turn[turn_id] = item
        turns_by_benchmark.setdefault(bench, []).append(
            {
                "turn_id": turn_id,
                "label": compact_label(turn_id, bench),
                "sequence_id": item.get("sequence_id"),
                "turn_index": item.get("turn_index"),
                "max_score": item.get("max_score"),
                "objective": is_objective(item, bench),
            }
        )
    for turns in turns_by_benchmark.values():
        turns.sort(key=lambda row: (str(row.get("sequence_id") or ""), int(row.get("turn_index") or 0), str(row["turn_id"])))
    return by_turn, turns_by_benchmark


def model_display_map(model_meta: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        row["model_id"]: {
            "model_id": row["model_id"],
            "display": row.get("display") or row["model_id"],
            "provider": row.get("provider") or "",
            "release_date": row.get("release_date") or "",
            "release_confidence": row.get("confidence") or "",
        }
        for row in model_meta
    }


def benchmark_map(benchmark_meta: list[dict[str, Any]], turns_by_benchmark: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    source = {row["benchmark_id"]: row for row in benchmark_meta}
    out: dict[str, dict[str, Any]] = {}
    for benchmark_id in BENCHMARK_ORDER:
        row = source.get(benchmark_id, {})
        out[benchmark_id] = {
            "benchmark_id": benchmark_id,
            "name": BENCHMARK_NAMES.get(benchmark_id, benchmark_id),
            "discipline": row.get("discipline") or "",
            "release_date": row.get("release_date") or "",
            "report_scale": row.get("report_scale"),
            "max_score": row.get("max_score_sum"),
            "source_quality": row.get("source_quality") or "",
            "rubric_status": row.get("official_rubric_status") or "",
            "caveats": row.get("caveat_summary") or [],
            "turn_count": len(turns_by_benchmark.get(benchmark_id, [])),
            "turns": turns_by_benchmark.get(benchmark_id, []),
            "reference_cutoffs": REFERENCE_CUTOFFS.get(benchmark_id, {}),
        }
    return out


def add_overall_benchmarks(benchmarks: dict[str, dict[str, Any]]) -> None:
    for sheet in SHEET_DEFINITIONS:
        overall_id = sheet["benchmark_ids"][0]
        source_ids = sheet.get("score_benchmark_ids") or sheet["benchmark_ids"][1:]
        benchmarks[overall_id] = {
            "benchmark_id": overall_id,
            "name": "Overall",
            "discipline": "summary",
            "release_date": "",
            "report_scale": 100.0,
            "max_score": 100.0,
            "source_quality": "",
            "rubric_status": "",
            "caveats": [],
            "turn_count": len(source_ids),
            "turns": [],
            "reference_cutoffs": {},
            "overall": True,
            "source_benchmark_ids": source_ids,
        }


def score_rank(cells: list[dict[str, Any]]) -> None:
    by_bench: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for cell in cells:
        if cell["status"] == "ok" and cell.get("reported_score") is not None:
            by_bench.setdefault((cell.get("sheet_id") or "", cell["benchmark_id"]), []).append(cell)
    for bench_cells in by_bench.values():
        bench_cells.sort(key=lambda row: float(row["reported_score"]), reverse=True)
        prev_score: float | None = None
        rank = 0
        seen = 0
        for cell in bench_cells:
            seen += 1
            score = float(cell["reported_score"])
            if prev_score is None or score < prev_score - 1e-9:
                rank = seen
                prev_score = score
            cell["rank"] = rank if cell.get("overall") or rank <= 3 else None


def build_core_summary_cells(detail_keys: set[tuple[str, str]]) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for model_id in CORE_MODEL_IDS:
        scores = CORE_SUMMARY_SCORES.get(model_id, {})
        for benchmark_id in INTERNATIONAL_CORE:
            score = finite_float(scores.get(benchmark_id))
            benchmark_scale = REFERENCE_CUTOFFS.get(benchmark_id, {})
            report_scale = {
                "ibo2023": 453.0,
                "ipho2025": 30.0,
                "icho2025": 60.0,
            }[benchmark_id]
            pct = score / report_scale if score is not None and report_scale > 0 else None
            is_reference = model_id.startswith("human/")
            has_detail = (benchmark_id, model_id) in detail_keys
            cells.append(
                {
                    "sheet_id": "international_core",
                    "benchmark_id": benchmark_id,
                    "model": model_id,
                    "status": "ok" if score is not None else "missing",
                    "status_reasons": ["manual_detail_available"] if has_detail else ["official_human_reference" if is_reference else "summary_only"],
                    "score": score,
                    "max_score": report_scale,
                    "reported_score": score,
                    "report_scale": report_scale,
                    "pct": max(0.0, min(1.0, pct)) if pct is not None else None,
                    "turn_count": None,
                    "expected_turn_count": None,
                    "generation_error_count": 0,
                    "judge_error_count": 0,
                    "bad_finish_reason_count": 0,
                    "cost_cny": None,
                    "total_tokens": None,
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "contamination": "",
                    "detail_path": core_detail_rel(benchmark_id, model_id) if has_detail else "",
                    "rank": None,
                    "summary_only": not has_detail,
                    "reference_row": is_reference,
                    "reference_cutoffs": benchmark_scale if is_reference else {},
                }
            )
    return cells


def apply_public_score(record: dict[str, Any], final_scores: dict[tuple[str, str], float]) -> tuple[dict[str, Any], bool]:
    benchmark_id = str(record.get("benchmark_id") or "")
    model_id = str(record.get("model") or "")
    score = final_scores.get((model_id, benchmark_id))
    if score is None:
        return dict(record), False

    out = dict(record)
    report_scale = finite_float(out.get("report_scale"))
    if report_scale is None:
        report_scale = finite_float(out.get("max_score"))
    if benchmark_id == "ibo2023":
        report_scale = 453.0
    out.update(
        {
            "status": "ok",
            "status_reasons": [public_score_source(model_id, benchmark_id)],
            "score": score,
            "max_score": report_scale,
            "reported_score": score,
            "report_scale": report_scale,
            "generation_error_count": 0,
            "judge_error_count": 0,
            "bad_finish_reason_count": 0,
            "bad_finish_reason_turn_ids": [],
        }
    )
    if benchmark_id == "ibo2023":
        out["turn_count"] = 87
        out["expected_turn_count"] = 87
    elif out.get("expected_turn_count") is not None:
        out["turn_count"] = out.get("expected_turn_count")
    return out, True


def build_overall_cells(cells: list[dict[str, Any]], sheet: dict[str, Any]) -> list[dict[str, Any]]:
    sheet_id = sheet["sheet_id"]
    overall_id = sheet["benchmark_ids"][0]
    benchmark_ids = sheet.get("score_benchmark_ids") or sheet["benchmark_ids"][1:]
    explicit_model_ids = sheet.get("model_ids")
    if explicit_model_ids:
        model_ids = list(explicit_model_ids)
    else:
        model_ids = sorted(
            {
                cell["model"]
                for cell in cells
                if cell.get("sheet_id") == sheet_id and cell["benchmark_id"] in benchmark_ids
            }
        )
    cell_index = {
        (cell.get("sheet_id"), cell["benchmark_id"], cell["model"]): cell
        for cell in cells
    }
    out: list[dict[str, Any]] = []
    for model_id in model_ids:
        normalized_values: list[float] = []
        valid_count = 0
        for benchmark_id in benchmark_ids:
            cell = cell_index.get((sheet_id, benchmark_id, model_id))
            if cell and cell.get("status") == "ok" and cell.get("pct") is not None:
                normalized_values.append(max(0.0, min(1.0, float(cell["pct"]))))
                valid_count += 1
            else:
                normalized_values.append(0.0)
        if not normalized_values:
            continue
        normalized_score = 100.0 * sum(normalized_values) / len(normalized_values)
        out.append(
            {
                "sheet_id": sheet_id,
                "benchmark_id": overall_id,
                "model": model_id,
                "status": "ok",
                "status_reasons": ["overall_mean_score"],
                "score": normalized_score,
                "max_score": 100.0,
                "reported_score": normalized_score,
                "report_scale": 100.0,
                "pct": normalized_score / 100.0,
                "turn_count": valid_count,
                "expected_turn_count": len(benchmark_ids),
                "generation_error_count": 0,
                "judge_error_count": 0,
                "bad_finish_reason_count": 0,
                "cost_cny": None,
                "total_tokens": None,
                "prompt_tokens": None,
                "completion_tokens": None,
                "contamination": "",
                "detail_path": "",
                "rank": None,
                "overall": True,
                "source_benchmark_ids": benchmark_ids,
            }
        )
    return out


def score_class(pct: Any, status: str | None) -> str:
    if status != "ok" or pct is None:
        return "invalid"
    try:
        p = float(pct)
    except (TypeError, ValueError):
        return "invalid"
    if p >= 0.78:
        return "high"
    if p >= 0.48:
        return "mid"
    return "low"


def fallback_html(manifest: dict[str, Any]) -> str:
    cells = {
        (cell.get("sheet_id") or "", cell["benchmark_id"], cell["model"]): cell
        for cell in manifest["cells"]
    }
    parts = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
        "<title>Science Arena Static Scores</title>",
        "<style>",
        "body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#f6f7f4;color:#1d2522}",
        ".fallback-note{padding:14px 16px;background:#fff;border-bottom:1px solid #d9ded8}",
        ".fallback-note h1{font-size:20px;margin:0 0 4px}.fallback-note p{margin:0;color:#65736f}",
        ".fallback-section{padding:16px}.fallback-section h2{font-size:17px;margin:0 0 10px}",
        ".fallback-section p{margin:0 0 10px;color:#65736f;font-size:13px}",
        ".fallback-table-wrap{overflow:auto;border:1px solid #d9ded8;background:white;border-radius:8px}",
        ".fallback-table{border-collapse:collapse;min-width:760px;width:100%}",
        ".fallback-table th,.fallback-table td{border:1px solid #d9ded8;padding:8px;text-align:left;font-size:13px}",
        ".fallback-table th{background:#f0f4f1}.fallback-table span{color:#65736f;font-size:12px}",
        ".fallback-table .high{background:#ddefe5}.fallback-table .mid{background:#fff1c9}",
        ".fallback-table .low{background:#f5d7d7}.fallback-table .invalid{background:#ecefed;color:#65736f}",
        "</style></head><body>",
        '<div class="fallback-note"><h1>Science Arena</h1><p>Static score fallback. If the interactive dashboard does not appear, these tables confirm the deployed content is present.</p></div>',
    ]
    for sheet in manifest["sheets"]:
        sheet_id = sheet["sheet_id"]
        bench_ids = sheet["benchmark_ids"]
        sheet_model_ids = {
            cell["model"]
            for cell in manifest["cells"]
            if cell.get("sheet_id") == sheet_id
            if cell["benchmark_id"] in bench_ids and cell.get("status") == "ok"
        }
        model_lookup = {model["model_id"]: model for model in manifest["models"]}
        if sheet.get("model_ids"):
            sheet_models = [
                model_lookup[model_id]
                for model_id in sheet["model_ids"]
                if model_id in sheet_model_ids and model_id in model_lookup
            ]
        else:
            sheet_models = [model for model in manifest["models"] if model["model_id"] in sheet_model_ids]
        parts.append(f'<section class="fallback-section"><h2>{html.escape(sheet["name"])}</h2>')
        parts.append(f'<p>{html.escape(sheet.get("description") or "")}</p>')
        parts.append('<div class="fallback-table-wrap"><table class="fallback-table"><thead><tr><th>Model</th>')
        for benchmark_id in bench_ids:
            bench = manifest["benchmarks"][benchmark_id]
            parts.append(f'<th>{html.escape(bench["name"])}<br><span>/{html.escape(fmtNumber_py(bench.get("report_scale")))}</span></th>')
        parts.append("</tr></thead><tbody>")
        for model in sheet_models:
            parts.append(
                f'<tr><td><strong>{html.escape(model.get("display") or model["model_id"])}</strong><br><span>{html.escape(model.get("release_date") or "")}</span></td>'
            )
            for benchmark_id in bench_ids:
                cell = cells.get((sheet_id, benchmark_id, model["model_id"]))
                if not cell or cell.get("status") != "ok" or cell.get("reported_score") is None:
                    parts.append('<td class="invalid">--</td>')
                    continue
                cls = score_class(cell.get("pct"), cell.get("status"))
                parts.append(f'<td class="{cls}">{html.escape(fmtNumber_py(cell.get("reported_score")))}</td>')
            parts.append("</tr>")
        parts.append("</tbody></table></div></section>")
    parts.append("</body></html>")
    return "".join(parts)


def fmtNumber_py(value: Any, digits: int = 2) -> str:
    number = finite_float(value)
    if number is None:
        return "--"
    if abs(number - round(number)) < 1e-9:
        return str(round(number))
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def build_details(
    record: dict[str, Any],
    turn_rows: list[dict[str, Any]],
    usage: dict[str, Any],
    dataset_by_turn: dict[str, dict[str, Any]],
    model_meta: dict[str, dict[str, Any]],
    benchmarks: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    benchmark_id = record["benchmark_id"]
    model_id = record["model"]
    turns: list[dict[str, Any]] = []
    for row in turn_rows:
        turn_id = str(row.get("turn_id") or "")
        item = dataset_by_turn.get(turn_id, {})
        objective = is_objective(item, benchmark_id)
        has_error = bool(row.get("generation_error") or row.get("judge_error"))
        score_value = row.get("score")
        max_score_value = row.get("max_score") if row.get("max_score") is not None else item.get("max_score")
        row_verdict = (
            partial_credit_verdict(score_value, max_score_value, has_error)
            if benchmark_id == "ibo2023"
            else verdict(score_value, max_score_value, objective, has_error)
        )
        turns.append(
            {
                "turn_id": turn_id,
                "label": compact_label(turn_id, benchmark_id),
                "sequence_id": row.get("sequence_id") or item.get("sequence_id"),
                "turn_index": row.get("turn_index") if row.get("turn_index") is not None else item.get("turn_index"),
                "score": score_value,
                "max_score": max_score_value,
                "ratio": ratio(score_value, max_score_value),
                "verdict": row_verdict,
                "objective": objective,
                "question": sanitize_public_text(item.get("prompt") or item.get("question_text_staticized") or item.get("original_prompt") or ""),
                "question_images": public_question_images(item),
                "official_answer": sanitize_public_text(item.get("official_answer_staticized") or item.get("official_answer") or ""),
                "official_rubric": sanitize_public_text(item.get("official_rubric_staticized") or item.get("official_rubric") or ""),
                "candidate_answer": sanitize_public_text(row.get("candidate_answer") or ""),
                "judge_model": row.get("judge_model") or "",
                "judge_result": sanitize_public_text(simplify_judge(row.get("judge_result"))),
                "generation_finish_reason": row.get("generation_finish_reason") or "",
                "judge_finish_reason": row.get("judge_finish_reason") or "",
                "generation_error": sanitize_public_text(row.get("generation_error") or ""),
                "judge_error": sanitize_public_text(row.get("judge_error") or ""),
                "caveats": sanitize_public_text(item.get("caveats") or []),
                "source_quality": item.get("source_quality") or benchmarks.get(benchmark_id, {}).get("source_quality") or "",
            }
        )
    turns.sort(key=lambda row: (str(row.get("sequence_id") or ""), int(row.get("turn_index") or 0), str(row.get("turn_id") or "")))
    return {
        "benchmark": {
            key: value
            for key, value in benchmarks.get(benchmark_id, {}).items()
            if key not in {"turns"}
        },
        "model": model_meta.get(model_id, {"model_id": model_id, "display": model_id}),
        "cell": {
            "benchmark_id": benchmark_id,
            "model": model_id,
            "status": record.get("status"),
            "status_reasons": record.get("status_reasons") or [],
            "score": record.get("score"),
            "max_score": record.get("max_score"),
            "reported_score": record.get("reported_score"),
            "report_scale": record.get("report_scale"),
            "turn_count": record.get("turn_count"),
            "expected_turn_count": record.get("expected_turn_count"),
            "generation_error_count": record.get("generation_error_count"),
            "judge_error_count": record.get("judge_error_count"),
            "bad_finish_reason_count": record.get("bad_finish_reason_count"),
            "cost_cny": record.get("cost_cny") if finite_float(record.get("cost_cny")) is not None else usage.get("cost_cny_from_turns"),
            "total_tokens": usage.get("total_tokens"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        },
        "turns": turns,
    }


def main() -> None:
    records = load_json(RECORDS_PATH, [])
    final_scores = load_final_paper_scores()
    ibo_public_scores = load_json(IBO_OBJECTIVE_SCORES_PATH, {})
    ibo_scoring_key = load_json(IBO_SCORING_KEY_PATH, [])
    benchmark_meta = load_json(BENCHMARK_META_PATH, [])
    raw_model_meta = load_json(MODEL_META_PATH, [])
    contamination = load_json(CONTAMINATION_PATH, {})
    dataset_by_turn, turns_by_benchmark = build_dataset_index()
    model_meta = model_display_map(raw_model_meta)
    model_meta.update(ibo_human_model_meta())
    model_meta.update(human_reference_model_meta())
    benchmarks = benchmark_map(benchmark_meta, turns_by_benchmark)
    add_overall_benchmarks(benchmarks)

    model_ids = sorted(
        {row["model"] for row in records}
        | set(CORE_MODEL_IDS),
        key=lambda model: (model_meta.get(model, {}).get("release_date") or "9999-99-99", model_meta.get(model, {}).get("display") or model),
    )
    models = [model_meta.get(model_id, {"model_id": model_id, "display": model_id}) for model_id in model_ids]

    if DETAIL_ROOT.exists():
        shutil.rmtree(DETAIL_ROOT)
    if ASSET_ROOT.exists():
        shutil.rmtree(ASSET_ROOT)
    DETAIL_ROOT.mkdir(parents=True, exist_ok=True)
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    cells: list[dict[str, Any]] = []
    detail_count = 0
    core_detail_keys = build_core_detail_files(dataset_by_turn, turns_by_benchmark, model_meta, benchmarks, ibo_scoring_key)
    detail_count += len(core_detail_keys)
    for record in sorted(records, key=lambda row: (row["benchmark_id"], row["model"])):
        record, public_score_applied = apply_public_score(record, final_scores)
        benchmark_id = record["benchmark_id"]
        model_id = record["model"]
        if benchmark_id not in benchmarks:
            continue
        detail_rel = f"static/data/details/{slug(benchmark_id)}/{slug(model_id)}.json"
        detail_path = SITE_ROOT / detail_rel
        turn_rows = public_turn_rows(
            record,
            read_turn_file(record),
            turns_by_benchmark,
            dataset_by_turn,
            public_score_applied,
            ibo_public_scores,
            ibo_scoring_key,
        )
        usage = aggregate_turn_usage(turn_rows)
        if turn_rows:
            detail_path.parent.mkdir(parents=True, exist_ok=True)
            detail = build_details(record, turn_rows, usage, dataset_by_turn, model_meta, benchmarks)
            detail_path.write_text(json.dumps(detail, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            detail_count += 1
        else:
            detail_rel = ""

        reported_score = finite_float(record.get("reported_score"))
        report_scale = finite_float(record.get("report_scale"))
        pct = reported_score / report_scale if reported_score is not None and report_scale and report_scale > 0 else None
        cells.append(
            {
                "sheet_id": "extended_suite",
                "benchmark_id": benchmark_id,
                "model": model_id,
                "status": record.get("status") or "missing",
                "status_reasons": record.get("status_reasons") or [],
                "score": record.get("score"),
                "max_score": record.get("max_score"),
                "reported_score": reported_score,
                "report_scale": report_scale,
                "pct": max(0.0, min(1.0, pct)) if pct is not None else None,
                "turn_count": record.get("turn_count"),
                "expected_turn_count": record.get("expected_turn_count"),
                "generation_error_count": record.get("generation_error_count"),
                "judge_error_count": record.get("judge_error_count"),
                "bad_finish_reason_count": record.get("bad_finish_reason_count"),
                "cost_cny": record.get("cost_cny") if finite_float(record.get("cost_cny")) is not None else usage.get("cost_cny_from_turns"),
                "total_tokens": usage.get("total_tokens"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "contamination": (contamination.get(model_id) or {}).get(benchmark_id, ""),
                "detail_path": detail_rel,
                "rank": None,
            }
        )

    score_rank(cells)
    cells.extend(build_core_summary_cells(core_detail_keys))
    for sheet in SHEET_DEFINITIONS:
        cells.extend(build_overall_cells(cells, sheet))
    score_rank(cells)
    for cell in cells:
        if cell.get("reference_row"):
            cell["rank"] = None

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "title": "Science Arena",
        "anonymous": True,
        "protocol": {
            "name": "mixed_staticized_and_saved_objective_key_v1",
            "note": "IBO 2023 uses saved official objective-key scoring.",
            "objective_note": "Objective-key items use red/green correctness. Rubric-scored items can show partial credit.",
        },
        "sources": {
            "records": "artifacts/runs/text_interleaved_eval/current_table_live_20260526_rebuild_after_taildiag/records.json",
            "final_paper_table": "emnlp-version/latex/acl_latex.tex",
            "ibo_objective_scores": "emnlp-version/analysis/ibo_objective_scores_latest.json",
            "ibo_saved_scores": "results/llm_human_evaluation/IBO 23/all_score_list.json",
            "ibo_saved_details": "results/llm_human_evaluation/IBO 23/*.json",
            "ipho_expert_ground_truth": "experiments/judge_pipeline_v2/ground_truth/ipho2025_expert_ground_truth.json",
            "icho_expert_ground_truth": "experiments/judge_pipeline_v2/ground_truth/icho2025_expert_ground_truth.json",
            "ipho_archived_judge_feedback": "experiments/judge_pipeline_v2/runs/merged_ipho_gemini35_v6/judge_results.json",
            "icho_archived_judge_feedback": "experiments/judge_pipeline_v2/runs/merged_icho_gemini35_v8_reparsed/judge_results.json",
            "ipho_old_model_solutions": "artifacts/model_outputs/ipho2025/old_model_solutions/",
            "icho_old_model_solutions": "artifacts/model_outputs/icho2025/old_model_solutions_and_judges/",
            "dataset": "datasets/science_arena_text_interleaved_v1/benchmark_items.jsonl",
            "benchmark_metadata": "emnlp-version/analysis/benchmark_release_metadata.json",
            "model_metadata": "emnlp-version/analysis/model_release_metadata.json",
            "contamination": "emnlp-version/analysis/contamination_matrix.json",
        },
        "sheets": SHEET_DEFINITIONS,
        "benchmark_order": BENCHMARK_ORDER,
        "benchmarks": benchmarks,
        "models": [model for model in models if model["model_id"] in {cell["model"] for cell in cells}],
        "cells": cells,
    }
    (DATA_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_ROOT / "fallback.html").write_text(fallback_html(manifest), encoding="utf-8")
    print(json.dumps({"cells": len(cells), "detail_files": detail_count, "manifest": str(DATA_ROOT / "manifest.json")}, indent=2))


if __name__ == "__main__":
    main()
