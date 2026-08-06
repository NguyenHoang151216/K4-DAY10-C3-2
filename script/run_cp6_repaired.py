"""
Checkpoint 6 Execution Script for Role 4 (R4) - RAG & Demo Owner.

Tasks:
1. Generate data/clean/papers_clean_repaired.csv by replaying raw records snapshot.
2. Build Chroma collection 'papers-repaired'.
3. Ensure relative persist_path in repaired manifest.
4. Update final Dashboard HTML.
5. Verify all 3 collections (baseline, corrupted, repaired) are operational for CLI Compare Demo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# UTF-8 encoding fix for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from datetime import datetime, timezone
import pandas as pd

from src.core.config import load_settings
from src.core.utils import read_json, write_csv, write_json
from src.ingestion.crossref import load_raw_records
from src.ingestion.cleaning import build_clean_dataframe
from src.presentation.dashboard import generate_dashboard_html
from src.retrieval.index import LocalEmbeddingIndex


def sanitize_manifest_path(manifest_path: Path) -> None:
    """Ensure manifest persist_path is portable relative path 'data/chroma'."""
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["persist_path"] = "data/chroma"
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARN] Failed to sanitize manifest path: {e}")


def execute_cp6() -> None:
    settings = load_settings()
    paths = settings.paths

    print("=== [CP6] GENERATING REPAIRED DATASET & BUILDING REPAIRED INDEX ===")

    # 1. Load run_context date if available
    run_date = datetime.now(timezone.utc)
    if paths.run_context.exists():
        try:
            ctx = read_json(paths.run_context)
            if "run_date" in ctx:
                run_date = datetime.fromisoformat(ctx["run_date"])
        except Exception:
            pass

    # 2. Replay raw ingestion records to repair
    if not paths.raw_records_json.exists():
        raise FileNotFoundError(f"Raw records JSON not found at {paths.raw_records_json}")

    raw_records = load_raw_records(paths.raw_records_json)
    print(f"[OK] Replaying {len(raw_records)} raw records from {paths.raw_records_json.name}")

    repaired_df = build_clean_dataframe(raw_records, run_date)

    # 3. Save repaired artifacts
    write_csv(repaired_df, paths.repaired_clean_csv)
    records = json.loads(repaired_df.to_json(orient="records", date_format="iso"))
    write_json(paths.repaired_clean_json, records)
    print(f"[OK] Saved repaired clean CSV to {paths.repaired_clean_csv}")
    print(f"[OK] Saved repaired clean JSON to {paths.repaired_clean_json}")

    # 4. Build Chroma Repaired Index
    print(f"\n[1/3] Building Chroma collection '{settings.repaired_collection_name}'...")
    repaired_index = LocalEmbeddingIndex.build(
        df=repaired_df,
        settings=settings,
        embeddings_output_path=paths.repaired_embeddings_json,
    )

    # Sanitize manifest path
    sanitize_manifest_path(paths.repaired_embeddings_json)
    print(f"[OK] Repaired Chroma index built! Collection doc count: {repaired_index.collection.count()}")

    # 5. Update Final HTML Dashboard
    print("\n[2/3] Updating Final HTML Dashboard UI...")
    out_html = generate_dashboard_html(settings)
    print(f"[OK] Final Dashboard UI generated at: {out_html}")

    # 6. Verify 3 Collections Readiness
    print("\n[3/3] Verifying 3-State Chroma Collections Status...")
    c_base = LocalEmbeddingIndex.load(settings, paths.embeddings_json).collection.count()
    c_corr = LocalEmbeddingIndex.load(settings, paths.corrupted_embeddings_json).collection.count()
    c_rep = LocalEmbeddingIndex.load(settings, paths.repaired_embeddings_json).collection.count()

    print(f"  [1] Baseline Collection ('{settings.baseline_collection_name}'): {c_base} docs")
    print(f"  [2] Corrupted Collection ('{settings.corrupted_collection_name}'): {c_corr} docs")
    print(f"  [3] Repaired Collection ('{settings.repaired_collection_name}'): {c_rep} docs")

    print("\n=== [CP6] CHECKPOINT 6 COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    execute_cp6()
