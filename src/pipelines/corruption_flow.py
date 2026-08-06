from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json, write_csv, write_json


TOTAL_STEPS = 8
CORE_METRICS = (
    "retrieval_hit_rate",
    "mean_token_f1",
    "judge_accuracy",
    "mean_judge_score",
)


def _log_step(number: int, message: str) -> None:
    if not 1 <= number <= TOTAL_STEPS:
        raise ValueError(f"Step number must be between 1 and {TOTAL_STEPS}.")
    print(f"[{number}/{TOTAL_STEPS}] {message}", flush=True)


def _baseline_artifacts(settings: Settings) -> list[Path]:
    return [
        settings.paths.raw_api_response,
        settings.paths.raw_records_json,
        settings.paths.clean_csv,
        settings.paths.clean_json,
        settings.paths.embeddings_json,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
        settings.paths.quality_dir / "baseline_quality.json",
        settings.paths.freshness_report,
        settings.paths.baseline_report,
        settings.paths.run_context,
    ]


def _require_baseline(settings: Settings) -> list[Path]:
    """Fail clearly instead of silently generating a new baseline."""

    artifacts = _baseline_artifacts(settings)
    missing = [str(path) for path in artifacts if not path.is_file()]
    if not settings.paths.chroma_dir.is_dir():
        missing.append(str(settings.paths.chroma_dir))
    if missing:
        formatted = "\n  - ".join(missing)
        raise RuntimeError(
            "Baseline artifacts are missing; corruption must not create a baseline "
            "implicitly. Run Phase 1 first:\n"
            "  uv run python script/run_phase1.py\n"
            f"Missing:\n  - {formatted}"
        )
    return artifacts


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _snapshot_hashes(paths: list[Path]) -> dict[Path, str]:
    return {path: _file_sha256(path) for path in paths}


def _verify_hashes_unchanged(before: dict[Path, str]) -> None:
    changed = [str(path) for path, digest in before.items() if _file_sha256(path) != digest]
    if changed:
        raise RuntimeError(
            "Corruption flow mutated immutable baseline artifacts:\n  - "
            + "\n  - ".join(changed)
        )


def _load_clean_json(path: Path) -> pd.DataFrame:
    payload = read_json(path)
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"Expected a non-empty JSON list in {path}.")
    df = pd.DataFrame(payload)
    for column in ("authors", "categories"):
        if column not in df.columns or not df[column].map(lambda value: isinstance(value, list)).all():
            raise ValueError(
                f"{path} must preserve list-valued `{column}`; do not load baseline from CSV."
            )
    return df


def _save_dataframe(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    write_json(json_path, records)


def _ground_truth_doc_ids(test_set: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(paper_id).lower()
            for sample in test_set
            for paper_id in sample.get("ground_truth_doc_ids", [])
        }
    )


def _metric_declines(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for key in CORE_METRICS:
        if key in baseline and key in corrupted:
            deltas[key] = round(float(corrupted[key]) - float(baseline[key]), 6)
    return {key: value for key, value in deltas.items() if value < 0.0}


def main() -> None:
    """Run CP5: corrupt baseline data, measure impact, and preserve baseline."""

    _log_step(1, "Load settings and verify baseline artifacts")
    settings = load_settings()
    baseline_paths = _require_baseline(settings)
    baseline_hashes = _snapshot_hashes(baseline_paths)

    import chromadb

    client = chromadb.PersistentClient(path=str(settings.paths.chroma_dir))
    try:
        baseline_collection = client.get_collection(settings.baseline_collection_name)
    except Exception as exc:
        raise RuntimeError(
            "The baseline Chroma collection is missing. Run Phase 1 first: "
            "uv run python script/run_phase1.py"
        ) from exc
    baseline_collection_count = baseline_collection.count()

    _log_step(2, "Load clean baseline and frozen evaluation targets")
    baseline_df = _load_clean_json(settings.paths.clean_json)
    test_set = read_json(settings.paths.eval_testset)
    if not isinstance(test_set, list) or not test_set:
        raise ValueError(f"Expected a non-empty test set in {settings.paths.eval_testset}.")
    target_doc_ids = _ground_truth_doc_ids(test_set)
    if not target_doc_ids:
        raise ValueError("The frozen test set contains no ground_truth_doc_ids.")

    _log_step(3, "Apply six deterministic corruption operators")
    from ingestion.corruption import corrupt_clean_dataframe

    corrupted_df = corrupt_clean_dataframe(
        baseline_df,
        settings.paths.corruption_log,
        target_doc_ids=target_doc_ids,
        seed=settings.random_seed,
    )

    _log_step(4, "Write corrupted clean CSV and JSON")
    _save_dataframe(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )

    _log_step(5, "Build isolated corrupted Chroma collection")
    from retrieval.index import LocalEmbeddingIndex

    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        settings.paths.corrupted_embeddings_json,
    )
    if corrupted_index.collection_name != settings.corrupted_collection_name:
        raise RuntimeError(
            f"Expected collection {settings.corrupted_collection_name!r}, got "
            f"{corrupted_index.collection_name!r}."
        )
    if corrupted_index.collection.count() != len(corrupted_df):
        raise RuntimeError("Corrupted Chroma count does not match corrupted dataframe rows.")

    _log_step(6, "Evaluate corrupted data with the frozen test set")
    from evaluation.metrics import evaluate_pipeline
    from observability.reporting import enrich_metrics

    bundle = evaluate_pipeline(
        settings,
        corrupted_index,
        settings.paths.eval_testset,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers,
    )
    corrupted_metrics = enrich_metrics(bundle.summary, bundle.answers)
    write_json(settings.paths.corrupted_metrics, corrupted_metrics)

    _log_step(7, "Run corrupted quality/freshness and write impact report")
    from observability.quality import build_freshness_report, run_data_quality_checks
    from observability.reporting import summarize_corruption_impact

    corrupted_quality = run_data_quality_checks(
        corrupted_df,
        settings,
        "corrupted_quality",
    )
    corrupted_freshness_path = settings.paths.quality_dir / "freshness_report_corrupted.json"
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        corrupted_freshness_path,
    )
    baseline_quality = read_json(settings.paths.quality_dir / "baseline_quality.json")
    baseline_freshness = read_json(settings.paths.freshness_report)
    corruption_log = read_json(settings.paths.corruption_log)
    impact = summarize_corruption_impact(
        corruption_log,
        baseline_quality,
        corrupted_quality,
        baseline_freshness,
        corrupted_freshness,
    )
    write_json(settings.paths.quality_dir / "corruption_impact.json", impact)

    _log_step(8, "Validate measurable impact and baseline immutability")
    operator_types = {item.get("type") for item in corruption_log.get("operations", [])}
    expected_operators = {
        "drop_latest",
        "blank_summary",
        "inject_noise",
        "truncate_title",
        "stale_date",
        "duplicate_rows",
    }
    if operator_types != expected_operators:
        raise RuntimeError(
            f"Corruption log operators mismatch: expected {sorted(expected_operators)}, "
            f"got {sorted(str(item) for item in operator_types)}."
        )

    failed_quality_checks = list(corrupted_quality.get("failed_checks", []))
    if len(failed_quality_checks) < 2:
        raise RuntimeError(
            "Corruption must make at least two hard quality checks fail; got "
            f"{failed_quality_checks}."
        )

    baseline_metrics = read_json(settings.paths.baseline_metrics)
    declines = _metric_declines(baseline_metrics, corrupted_metrics)
    if not declines:
        raise RuntimeError(
            "Corruption did not reduce any core metric. Check target IDs, rebuilt "
            "text_for_embedding, collection name, and frozen test set."
        )

    _verify_hashes_unchanged(baseline_hashes)
    if client.get_collection(settings.baseline_collection_name).count() != baseline_collection_count:
        raise RuntimeError("The papers-baseline collection was mutated during CP5.")

    print(
        "CP5 completed: "
        f"rows={len(baseline_df)}->{len(corrupted_df)}, "
        f"quality_failures={failed_quality_checks}, metric_declines={declines}",
        flush=True,
    )
