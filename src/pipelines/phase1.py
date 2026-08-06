from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import TYPE_CHECKING, Any

from core.config import Settings, load_settings
from core.utils import read_json, write_csv, write_json

if TYPE_CHECKING:
    from retrieval.index import LocalEmbeddingIndex


TOTAL_STEPS = 13


def _log_step(number: int, message: str) -> None:
    """Print a consistent progress marker for the baseline pipeline."""

    if not 1 <= number <= TOTAL_STEPS:
        raise ValueError(f"Step number must be between 1 and {TOTAL_STEPS}.")
    print(f"[{number}/{TOTAL_STEPS}] {message}", flush=True)


def write_run_context(
    settings: Settings,
    run_date: datetime | None = None,
) -> datetime:
    """Persist the values that must remain fixed across the experiment.

    The corruption/repair process runs in a separate Python process. Persisting
    ``run_date`` prevents ``age_days`` from changing when repaired data is
    rebuilt from the immutable raw snapshot.
    """

    effective_run_date = run_date or datetime.now(UTC)
    if effective_run_date.tzinfo is None:
        effective_run_date = effective_run_date.replace(tzinfo=UTC)
    else:
        effective_run_date = effective_run_date.astimezone(UTC)

    write_json(
        settings.paths.run_context,
        {
            "run_date": effective_run_date.isoformat(),
            "source_query": settings.source_query,
            "source_filter": settings.source_filter,
            "max_results": settings.max_results,
            "embedding_model": settings.embedding_model,
            "top_k": settings.top_k,
            "freshness_threshold_days": settings.freshness_threshold_days,
        },
    )
    return effective_run_date


def _load_or_fetch_records(settings: Settings):
    from ingestion import fetch_source_records, load_raw_records

    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        return fetch_source_records(settings), True
    return load_raw_records(settings.paths.raw_records_json), False


def _save_clean_artifacts(df, settings: Settings) -> None:
    write_csv(df, settings.paths.clean_csv)
    # Round-tripping through pandas' JSON serializer converts numpy/pandas
    # scalar values to regular Python values accepted by ``write_json``.
    records = json.loads(df.to_json(orient="records", date_format="iso"))
    write_json(settings.paths.clean_json, records)


def _load_or_build_test_set(df, settings: Settings) -> list[dict[str, Any]]:
    from evaluation.testset import build_test_set

    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        return build_test_set(df, settings.paths.eval_testset)
    payload = read_json(settings.paths.eval_testset)
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list in {settings.paths.eval_testset}.")
    return payload


def _run_agent_smoke_test(
    settings: Settings,
    index: LocalEmbeddingIndex,
    test_set: list[dict[str, Any]],
) -> None:
    """Run one real agent question without making credentials a hard failure."""

    from retrieval.agent import build_agent, run_agent_question

    if not test_set:
        write_json(
            settings.paths.demo_answers,
            {"status": "skipped", "reason": "The evaluation test set is empty."},
        )
        return

    question = str(test_set[0]["question"])
    try:
        agent = build_agent(settings, index)
        answer = run_agent_question(agent, question)
        write_json(
            settings.paths.demo_answers,
            {"status": "completed", "question": question, "answer": answer},
        )
    except Exception as exc:
        write_json(
            settings.paths.demo_answers,
            {
                "status": "skipped",
                "question": question,
                # Do not persist provider exception text because it may contain
                # request details that do not belong in committed artifacts.
                "reason": f"Agent unavailable: {type(exc).__name__}",
            },
        )


def main() -> None:
    """Run the 13-step baseline data and RAG pipeline."""

    _log_step(1, "Load settings")
    settings = load_settings()

    _log_step(2, "Persist run context")
    run_date = write_run_context(settings)

    _log_step(3, "Load or fetch immutable raw records")
    records, source_refreshed = _load_or_fetch_records(settings)

    _log_step(4, "Build clean dataframe")
    from ingestion import build_clean_dataframe

    clean_df = build_clean_dataframe(records, run_date)

    _log_step(5, "Write clean CSV and JSON artifacts")
    _save_clean_artifacts(clean_df, settings)

    _log_step(6, "Run baseline data-quality checks")
    from observability.quality import run_data_quality_checks

    quality = run_data_quality_checks(clean_df, settings, "baseline_quality")

    _log_step(7, "Build baseline freshness report")
    from observability.quality import build_freshness_report

    freshness = build_freshness_report(
        clean_df,
        settings,
        settings.paths.freshness_report,
    )

    _log_step(8, "Build baseline Chroma collection")
    from retrieval.index import LocalEmbeddingIndex

    index = LocalEmbeddingIndex.build(
        clean_df,
        settings,
        settings.paths.embeddings_json,
    )

    _log_step(9, "Load or build deterministic evaluation set")
    test_set = _load_or_build_test_set(clean_df, settings)

    _log_step(10, "Evaluate the baseline pipeline")
    from evaluation.metrics import evaluate_pipeline

    evaluation = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )

    _log_step(11, "Run agent smoke test")
    _run_agent_smoke_test(settings, index, test_set)

    _log_step(12, "Generate baseline report")
    from observability.reporting import generate_phase1_report

    generate_phase1_report(
        settings.paths.baseline_report,
        {
            "source_api": settings.source_api,
            "source_query": settings.source_query,
            "source_filter": settings.source_filter,
            "max_results": settings.max_results,
            "raw_record_count": len(records),
            "clean_record_count": len(clean_df),
            "source_refreshed": source_refreshed,
            "run_date": run_date.isoformat(),
        },
        evaluation.summary,
        quality,
        freshness,
    )

    _log_step(13, "Baseline pipeline completed")
    print(f"Baseline report: {settings.paths.baseline_report}", flush=True)
