from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

REQUIRED_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "published",
    "authors_joined",
    "categories_joined",
    "abs_url",
    "pdf_url",
    "summary_chars",
    "age_days",
    "text_for_embedding",
]

MIN_ROWS = 10
MIN_SUMMARY_CHARS = 80
MIN_TITLE_CHARS = 15
MIN_SUMMARY_USABLE_RATIO = 0.90
MIN_AUTHORS_PRESENT_RATIO = 0.90
MIN_CATEGORIES_PRESENT_RATIO = 0.80
MAX_STALE_RATIO = 0.20

ISO_DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}"

HARD = "hard"
WARN = "warn"


def _text_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([""] * len(df), dtype="object")
    return df[column].fillna("").astype(str).str.strip()


def _numeric_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([float("nan")] * len(df), dtype="float64")
    return pd.to_numeric(df[column], errors="coerce")


def _ratio(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _check(
    name: str,
    level: str,
    passed: bool,
    observed: Any,
    expected: str,
    detail: str = "",
) -> dict[str, Any]:
    return {
        "name": name,
        "level": level,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "detail": detail,
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Run 7 hard-fail and 5 warning checks, then persist them to data/quality/<report_name>.json.

    Every check is designed so that at least one corruption operator moves it. The one
    deliberate exception is noise injection: no structural check can detect it, which is
    the point the comparison report has to make.
    """
    total = int(len(df))
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in df.columns]

    paper_id = _text_column(df, "paper_id")
    title = _text_column(df, "title")
    text_for_embedding = _text_column(df, "text_for_embedding")
    authors_joined = _text_column(df, "authors_joined")
    categories_joined = _text_column(df, "categories_joined")
    published = _text_column(df, "published")
    summary_chars = _numeric_column(df, "summary_chars")
    age_days = _numeric_column(df, "age_days")

    # Every count below is cast to a Python scalar: json.dumps cannot serialise numpy types.
    empty_paper_ids = int(paper_id.eq("").sum())
    duplicate_paper_ids = total - int(paper_id.nunique()) if total else 0
    empty_titles = int(title.eq("").sum())
    empty_text_for_embedding = int(text_for_embedding.eq("").sum())
    usable_summaries = int((summary_chars >= MIN_SUMMARY_CHARS).sum())
    short_titles = int(title.str.len().lt(MIN_TITLE_CHARS).sum())
    with_authors = int(authors_joined.ne("").sum())
    with_categories = int(categories_joined.ne("").sum())
    invalid_published = int((~published.str.match(ISO_DATE_PATTERN, na=False)).sum())
    stale_rows = int((age_days > settings.freshness_threshold_days).sum())

    summary_usable_ratio = _ratio(usable_summaries, total)
    authors_present_ratio = _ratio(with_authors, total)
    categories_present_ratio = _ratio(with_categories, total)
    stale_ratio = _ratio(stale_rows, total)

    checks = [
        _check(
            "required_columns_present",
            HARD,
            not missing_columns,
            missing_columns,
            "no missing column",
            f"{len(REQUIRED_COLUMNS)} columns required by index.py and the test set",
        ),
        _check(
            "row_count_min",
            HARD,
            total >= MIN_ROWS,
            total,
            f">= {MIN_ROWS} rows",
            "too few documents makes retrieval metrics unstable",
        ),
        _check(
            "paper_id_not_null",
            HARD,
            empty_paper_ids == 0,
            empty_paper_ids,
            "0 empty paper_id",
            "paper_id is the join key across raw, clean, index and test set",
        ),
        _check(
            "paper_id_unique",
            HARD,
            duplicate_paper_ids == 0,
            duplicate_paper_ids,
            "0 duplicate paper_id",
            "duplicates bias top-k retrieval towards the repeated document",
        ),
        _check(
            "title_not_empty",
            HARD,
            empty_titles == 0,
            empty_titles,
            "0 empty title",
            "exact-title lookup in qa.py fails without a title",
        ),
        _check(
            "text_for_embedding_not_empty",
            HARD,
            empty_text_for_embedding == 0,
            empty_text_for_embedding,
            "0 empty text_for_embedding",
            "an empty document still gets embedded and pollutes the collection",
        ),
        _check(
            "summary_usable_ratio",
            HARD,
            summary_usable_ratio >= MIN_SUMMARY_USABLE_RATIO,
            summary_usable_ratio,
            f">= {MIN_SUMMARY_USABLE_RATIO}",
            f"share of rows with summary_chars >= {MIN_SUMMARY_CHARS}",
        ),
        _check(
            "title_min_length",
            WARN,
            short_titles == 0,
            short_titles,
            f"0 title shorter than {MIN_TITLE_CHARS} chars",
            "detects truncated titles, which break entity resolution",
        ),
        _check(
            "authors_present_ratio",
            WARN,
            authors_present_ratio >= MIN_AUTHORS_PRESENT_RATIO,
            authors_present_ratio,
            f">= {MIN_AUTHORS_PRESENT_RATIO}",
            "ground truth of author questions comes from this column",
        ),
        _check(
            "categories_present_ratio",
            WARN,
            categories_present_ratio >= MIN_CATEGORIES_PRESENT_RATIO,
            categories_present_ratio,
            f">= {MIN_CATEGORIES_PRESENT_RATIO}",
            "ground truth of category questions comes from this column",
        ),
        _check(
            "published_iso_format",
            WARN,
            invalid_published == 0,
            invalid_published,
            "0 value outside YYYY-MM-DD",
            "published is stored as a string; freshness compares it lexicographically",
        ),
        _check(
            "freshness_stale_ratio",
            WARN,
            stale_ratio <= MAX_STALE_RATIO,
            stale_ratio,
            f"<= {MAX_STALE_RATIO}",
            f"share of rows with age_days > {settings.freshness_threshold_days}",
        ),
    ]

    failed_checks = [check["name"] for check in checks if check["level"] == HARD and not check["passed"]]
    warning_checks = [check["name"] for check in checks if check["level"] == WARN and not check["passed"]]

    payload = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "row_count": total,
        "thresholds": {
            "min_rows": MIN_ROWS,
            "min_summary_chars": MIN_SUMMARY_CHARS,
            "min_title_chars": MIN_TITLE_CHARS,
            "min_summary_usable_ratio": MIN_SUMMARY_USABLE_RATIO,
            "max_stale_ratio": MAX_STALE_RATIO,
            "freshness_threshold_days": int(settings.freshness_threshold_days),
        },
        "checks": checks,
        "hard_checks_total": sum(1 for check in checks if check["level"] == HARD),
        "warning_checks_total": sum(1 for check in checks if check["level"] == WARN),
        "failed_checks": failed_checks,
        "warning_checks": warning_checks,
        "passed": not failed_checks,
    }

    write_json(Path(settings.paths.quality_dir) / f"{report_name}.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Summarise how current the corpus is and persist the payload to report_path.

    is_fresh deliberately combines two conditions. stale_rows catches back-dated records,
    min_age_days catches the case where the newest documents were dropped; either one
    alone would miss half of the corruption operators.
    """
    threshold = int(settings.freshness_threshold_days)
    total = int(len(df))

    published = _text_column(df, "published")
    age_days = _numeric_column(df, "age_days")

    # published is an ISO string, so lexicographic min/max is the chronological min/max.
    valid_published = sorted(published[published.str.match(ISO_DATE_PATTERN, na=False)].tolist())
    has_age = bool(age_days.notna().any())
    stale_rows = int((age_days > threshold).sum())

    payload = {
        "generated_at": now_utc().isoformat(),
        "threshold_days": threshold,
        "total_rows": total,
        "latest_published": valid_published[-1] if valid_published else "",
        "oldest_published": valid_published[0] if valid_published else "",
        "missing_published_rows": total - len(valid_published),
        "stale_rows": stale_rows,
        "stale_ratio": _ratio(stale_rows, total),
        "min_age_days": float(age_days.min()) if has_age else None,
        "max_age_days": float(age_days.max()) if has_age else None,
        "median_age_days": float(age_days.median()) if has_age else None,
        "is_fresh": bool(stale_rows == 0 and has_age and float(age_days.min()) <= threshold),
    }

    write_json(Path(report_path), payload)
    return payload
