from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import html
import json
import re
from typing import Any

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

# Contract cot clean DataFrame - chot chung voi R2 o CP0, dong bang tu CP1.
# 11 cot dau den thang tu PaperRecord; 5 cot cuoi do cleaning sinh ra.
# Doi ten mot cot o day se pha dong thoi index.py, qa.py, quality.py va test set.
CLEAN_COLUMNS: list[str] = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "age_days",
    "text_for_embedding",
]

# Cot string phai la "" thay vi NaN: index.py day thang metadata vao Chroma,
# ma Chroma chi nhan str/int/float/bool.
_STRING_COLUMNS: list[str] = [
    "paper_id",
    "title",
    "summary",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "text_for_embedding",
]

_LIST_COLUMNS: list[str] = ["authors", "categories"]

# Cot mang noi dung that - dung de hash so sanh baseline / corrupted / repaired.
CORE_CONTENT_COLUMNS: list[str] = [
    "paper_id",
    "title",
    "summary",
    "published",
    "authors_joined",
    "categories_joined",
]

# Nguong abstract dung duoc. Ha xuong 40 neu ket qua duoi MIN_ROWS, va ghi ro
# vao cleaning_stats de report khong ke nham la da dung nguong 80.
SUMMARY_MIN_CHARS = 80
SUMMARY_MIN_CHARS_RELAXED = 40
MIN_ROWS = 24

_MARKUP_RE = re.compile(r"<[^>]+>")
_DROP_REASONS = ("missing_paper_id", "missing_title", "missing_published", "summary_too_short")


def _strip_markup(value: Any) -> str:
    """Go markup con sot va giai ma HTML entity, roi chuan hoa whitespace.

    R2 da strip JATS o tang parse bang HTMLParser. Day la lop phong thu thu hai:
    idempotent nen vo hai, va can thiet vi build_clean_dataframe con duoc goi lai
    o CP6 de repair tu raw snapshot.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = html.unescape(str(value))
    text = _MARKUP_RE.sub(" ", text)
    return normalize_whitespace(text)


def _clean_string_list(value: Any) -> list[str]:
    """Normalize tung phan tu, bo rong, dedupe nhung giu nguyen thu tu goc."""
    if value is None or not isinstance(value, (list, tuple)):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        text = _strip_markup(item)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _to_utc_datetime(series: pd.Series) -> pd.Series:
    """Parse cot ngay thanh datetime UTC, khong parse duoc thi NaT.

    format="mixed" la bat buoc: du lieu that co ca "2026-06-15" (date thuan)
    lan "2026-06-17T08:52:47Z" (timestamp ISO8601) trong cung mot dataset.
    """
    return pd.to_datetime(series, errors="coerce", utc=True, format="mixed")


def _iso_date_string(series: pd.Series) -> pd.Series:
    """Datetime -> chuoi ISO YYYY-MM-DD, NaT -> "" (Chroma khong nhan datetime)."""
    formatted = series.dt.strftime("%Y-%m-%d")
    return formatted.where(series.notna(), "").astype(str)


def build_text_for_embedding(row: pd.Series | dict[str, Any]) -> str:
    """Ghep 5 nhan co dinh, giu nguyen nhan ca khi gia tri rong.

    Format bat bien la co y: CP5 phai rebuild cot nay sau khi corrupt, va R4
    verify bang mot phep `in` don gian. Bo dong rong se lam ca hai viec do
    tro nen phu thuoc du lieu.

    Public vi `corruption.py` phai rebuild cot nay bang DUNG mot ham: baseline
    va corrupted khac format thi phep so sanh mat cong bang.
    """
    return (
        f"Title: {row['title']}\n"
        f"Authors: {row['authors_joined']}\n"
        f"Categories: {row['categories_joined']}\n"
        f"Published: {row['published']}\n"
        f"Abstract: {row['summary']}"
    )


def row_content_hash(row: pd.Series | dict[str, Any]) -> str:
    """Hash noi dung cot loi cua mot row.

    Chi lay cot mang noi dung, KHONG lay cot dan xuat (`summary_chars`,
    `age_days`, `text_for_embedding`) - cac cot do la ham cua cot loi nen dua
    vao chi lam hash nhay cam voi loi lam tron ma khong them thong tin.
    """
    payload = json.dumps(
        {column: str(row[column]) for column in CORE_CONTENT_COLUMNS},
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def core_content_hash(df: pd.DataFrame) -> str:
    """Hash toan dataset, khong phu thuoc thu tu row.

    R1 dung o CP6 de sinh `repair_validation.json`: repaired dung bang baseline
    thi hai hash nay bang nhau (`core_content_hash_equal: true`). Sort truoc khi
    hash de thu tu row khong lam sai ket luan, nhung row trung lap VAN lam doi
    hash - dung y muon, vi duplicate la mot dang corruption.
    """
    row_hashes = sorted(row_content_hash(row) for _, row in df.iterrows())
    return hashlib.sha256("".join(row_hashes).encode("utf-8")).hexdigest()[:16]


def _normalize_records(records: list[PaperRecord]) -> pd.DataFrame:
    """PaperRecord -> DataFrame da normalize text, kem 2 cot datetime phu."""
    df = pd.DataFrame([asdict(record) for record in records])

    # Phong ho truong hop raw snapshot cu thieu field: dam bao du 11 cot goc.
    for column in CLEAN_COLUMNS[:11]:
        if column not in df.columns:
            df[column] = "" if column not in _LIST_COLUMNS else [[] for _ in range(len(df))]

    for column in ("title", "summary", "comment", "abs_url", "pdf_url", "primary_category"):
        df[column] = df[column].map(_strip_markup)
    df["paper_id"] = df["paper_id"].map(_strip_markup).str.lower()

    for column in _LIST_COLUMNS:
        df[column] = df[column].map(_clean_string_list)

    # primary_category rong -> lay category dau tien neu co.
    missing_primary = df["primary_category"] == ""
    df.loc[missing_primary, "primary_category"] = df.loc[missing_primary, "categories"].map(
        lambda items: items[0] if items else ""
    )

    df["_published_dt"] = _to_utc_datetime(df["published"])
    df["_updated_dt"] = _to_utc_datetime(df["updated"])
    df["published"] = _iso_date_string(df["_published_dt"])
    df["updated"] = _iso_date_string(df["_updated_dt"])

    df["authors_joined"] = df["authors"].map(compact_join)
    df["categories_joined"] = df["categories"].map(compact_join)
    df["summary_chars"] = df["summary"].str.len().astype(int)
    return df


def _apply_filters(df: pd.DataFrame, summary_min_chars: int) -> tuple[pd.DataFrame, dict[str, int]]:
    """Loai row khong dung duoc, tra ve DataFrame moi kem so luong theo tung ly do."""
    dropped = dict.fromkeys(_DROP_REASONS, 0)

    masks = {
        "missing_paper_id": df["paper_id"] == "",
        "missing_title": df["title"] == "",
        # Drop row khong co ngay la co y: qa.py tra thang metadata["published"]
        # cho cau hoi ngay thang, giu row rong se de ra ground truth rong cho R5.
        "missing_published": df["_published_dt"].isna(),
        "summary_too_short": df["summary_chars"] < summary_min_chars,
    }

    keep = pd.Series(True, index=df.index)
    for reason in _DROP_REASONS:
        # Chi tinh row bi loai lan dau theo ly do nay, tranh dem trung mot row
        # vao nhieu ly do -> tong drop moi cong dung voi input_records.
        newly_dropped = keep & masks[reason]
        dropped[reason] = int(newly_dropped.sum())
        keep &= ~masks[reason]

    return df.loc[keep].copy(), dropped


def _dedupe(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Dedupe theo paper_id: giu summary dai hon, hoa thi `updated` moi hon."""
    before = len(df)
    # NaT trong khoa sort la nguon thu tu bat dinh -> thay bang moc thoi gian nho nhat.
    epoch = pd.Timestamp("1677-09-22", tz="UTC")
    df = df.copy()
    df["_updated_sort"] = df["_updated_dt"].fillna(epoch)
    df = df.sort_values(
        ["summary_chars", "_updated_sort"],
        ascending=[False, False],
        kind="mergesort",  # stable sort -> ket qua deterministic
    )
    df = df.drop_duplicates(subset="paper_id", keep="first")
    return df.drop(columns=["_updated_sort"]), before - len(df)


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed.

    Tra ve DataFrame dung 16 cot theo `CLEAN_COLUMNS`, khong con NaN, khong con
    cot datetime (Chroma chi nhan scalar). So lieu loai bo/dedupe duoc gan vao
    `df.attrs["cleaning_stats"]` de pipeline log lai ma khong phai doi chu ky ham.
    """
    if not records:
        raise ValueError(
            "build_clean_dataframe received 0 records. "
            "Kiem tra data/raw/crossref_records.json va buoc fetch cua ingestion."
        )

    # run_date naive -> gan UTC, neu khong se TypeError khi tru datetime tz-aware.
    run_date_utc = run_date if run_date.tzinfo is not None else run_date.replace(tzinfo=UTC)
    run_timestamp = pd.Timestamp(run_date_utc)

    normalized = _normalize_records(records)

    summary_min_chars = SUMMARY_MIN_CHARS
    threshold_relaxed = False
    df, dropped = _apply_filters(normalized, summary_min_chars)
    if len(df) < MIN_ROWS:
        relaxed_df, relaxed_dropped = _apply_filters(normalized, SUMMARY_MIN_CHARS_RELAXED)
        # Chi ghi nhan la "da ha nguong" khi viec do THUC SU cuu duoc them row.
        # Bao ha nguong ma ket qua khong doi se lam report noi sai ve du lieu.
        if len(relaxed_df) > len(df):
            summary_min_chars = SUMMARY_MIN_CHARS_RELAXED
            df, dropped = relaxed_df, relaxed_dropped
            threshold_relaxed = True

    df, duplicates_removed = _dedupe(df)

    if df.empty:
        raise ValueError(
            f"Cleaning loai het {len(records)} record (nguong summary_chars="
            f"{summary_min_chars}). Chi tiet: {dropped}."
        )

    df["age_days"] = (run_timestamp - df["_published_dt"]).dt.days.astype(int)
    df["text_for_embedding"] = df.apply(build_text_for_embedding, axis=1)

    df = df.sort_values(["_published_dt", "paper_id"], ascending=[False, True], kind="mergesort")

    # Drop cot datetime phu TRUOC khi ghi CSV/JSON va truoc khi build index.
    df = df.drop(columns=["_published_dt", "_updated_dt"]).reset_index(drop=True)
    for column in _STRING_COLUMNS:
        df[column] = df[column].fillna("").astype(str)
    df = df[CLEAN_COLUMNS]

    df.attrs["cleaning_stats"] = {
        "input_records": len(records),
        "output_rows": len(df),
        "dropped": dropped,
        "duplicates_removed": duplicates_removed,
        "summary_min_chars_used": summary_min_chars,
        "threshold_relaxed": threshold_relaxed,
        "rows_without_categories": int((df["categories_joined"] == "").sum()),
        "run_date": run_date_utc.isoformat(),
    }
    print(
        f"[cleaning] {len(records)} records -> {len(df)} rows | "
        f"dropped={dropped} | duplicates_removed={duplicates_removed} | "
        f"summary_min_chars={summary_min_chars}"
        + (" (RELAXED)" if threshold_relaxed else "")
    )
    return df
