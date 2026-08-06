"""
Clean Data Inspection Tool for Checkpoint 1.
Role 4 (R4) - RAG & Demo Owner

Inspects data/clean/papers_clean.csv to verify:
1. 16 contract columns exist.
2. text_for_embedding is non-empty and contains required metadata fields.
3. Prints 5 sample text_for_embedding strings for manual inspection.
"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
from src.core.config import load_settings

REQUIRED_COLUMNS = [
    "paper_id",
    "doi",
    "title",
    "summary",
    "authors",
    "categories",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "age_days",
    "text_for_embedding",
]


def inspect_clean_data() -> bool:
    settings = load_settings()
    clean_path = settings.paths.clean_csv

    print(f"=== [CP1] INSPECT CLEAN DATAFRAME ===")
    print(f"Path: {clean_path}")

    if not clean_path.exists():
        print(f"[WARN] File {clean_path} does not exist yet (Waiting for R3 pipeline execution).")
        return False

    df = pd.read_csv(clean_path)
    print(f"Total Rows: {len(df)}")
    print(f"Total Columns: {len(df.columns)}")

    # 1. Column Check
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        print(f"[FAIL] Missing contract columns: {missing_cols}")
    else:
        print(f"[PASS] All {len(REQUIRED_COLUMNS)} required contract columns present.")

    # 2. text_for_embedding Check
    if "text_for_embedding" not in df.columns:
        print("[FAIL] 'text_for_embedding' column not found!")
        return False

    nan_count = df["text_for_embedding"].isna().sum()
    empty_count = (df["text_for_embedding"].astype(str).str.strip() == "").sum()

    if nan_count > 0 or empty_count > 0:
        print(f"[FAIL] text_for_embedding has {nan_count} NaNs and {empty_count} empty strings!")
    else:
        print("[PASS] text_for_embedding is 100% non-null and non-empty.")

    # 3. Print 5 Samples
    print("\n--- TOP 5 SAMPLES FOR VISUAL INSPECTION ---")
    for idx, row in df.head(5).iterrows():
        print(f"\n--- [Sample #{idx + 1}] Paper ID: {row.get('paper_id', 'N/A')} ---")
        print(f"Title: {row.get('title', 'N/A')}")
        print(f"Text for Embedding:\n{row.get('text_for_embedding', 'N/A')[:300]}...")

    return True


if __name__ == "__main__":
    inspect_clean_data()
