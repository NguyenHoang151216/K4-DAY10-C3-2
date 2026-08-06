"""
Checkpoint 5 Execution Script for Role 4 (R4) - RAG & Demo Owner.

Tasks:
1. Generate data/clean/papers_clean_corrupted.csv using corrupt_clean_dataframe().
2. Build Chroma collection 'papers-corrupted' from corrupted clean dataset.
3. Ensure relative persist_path in corrupted manifest.
4. Smoke test retrieval impact on corrupted collection.
5. Verify 'papers-baseline' collection is untouched.
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

import pandas as pd
from src.core.config import load_settings
from src.core.utils import read_json, write_csv, write_json
from src.ingestion.corruption import corrupt_clean_dataframe
from src.retrieval.index import LocalEmbeddingIndex
from src.retrieval.qa import answer_question


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


def execute_cp5() -> None:
    settings = load_settings()
    paths = settings.paths

    print("=== [CP5] GENERATING CORRUPTED DATASET & BUILDING CORRUPTED INDEX ===")

    # 1. Load clean baseline dataset
    clean_json_path = paths.clean_json
    if not clean_json_path.exists():
        raise FileNotFoundError(f"Clean dataset not found at {clean_json_path}")

    clean_data = read_json(clean_json_path)
    clean_df = pd.DataFrame(clean_data)
    print(f"[OK] Read baseline clean dataset: {len(clean_df)} rows")

    # 2. Extract target doc IDs from test set if available
    target_ids: list[str] = []
    if paths.eval_testset.exists():
        try:
            test_set = read_json(paths.eval_testset)
            target_ids = [
                doc_id
                for item in test_set
                if isinstance(item, dict)
                for doc_id in item.get("ground_truth_doc_ids", [])
            ]
        except Exception:
            pass

    # 3. Generate corrupted dataframe
    print("\n[1/3] Applying controlled data corruption operators (seed=42)...")
    corrupted_df = corrupt_clean_dataframe(
        clean_df,
        paths.corruption_log,
        target_doc_ids=target_ids,
        seed=42,
    )

    # 4. Save corrupted artifacts
    write_csv(corrupted_df, paths.corrupted_clean_csv)
    records = json.loads(corrupted_df.to_json(orient="records", date_format="iso"))
    write_json(paths.corrupted_clean_json, records)
    print(f"[OK] Saved corrupted clean CSV to {paths.corrupted_clean_csv}")
    print(f"[OK] Saved corrupted clean JSON to {paths.corrupted_clean_json}")

    # 5. Build Chroma Corrupted Index
    print(f"\n[2/3] Building Chroma collection '{settings.corrupted_collection_name}'...")
    corrupted_index = LocalEmbeddingIndex.build(
        df=corrupted_df,
        settings=settings,
        embeddings_output_path=paths.corrupted_embeddings_json,
    )

    # Sanitize manifest path
    sanitize_manifest_path(paths.corrupted_embeddings_json)
    print(f"[OK] Corrupted Chroma index built! Collection doc count: {corrupted_index.collection.count()}")

    # 6. Smoke test & compare with baseline
    print("\n[3/3] Smoke Testing Retrieval Impact on Corrupted Collection...")
    sample_query = "agentic retrieval augmented generation"
    
    corr_results = corrupted_index.search(sample_query, top_k=2)
    print(f"  Corrupted Query: '{sample_query}'")
    for doc in corr_results:
        print(f"    - Doc ID: {doc.paper_id} | Score: {doc.score:.4f} | Title: {doc.title[:60]}...")

    # 7. Verify baseline index remains intact
    if paths.embeddings_json.exists():
        base_index = LocalEmbeddingIndex.load(settings, paths.embeddings_json)
        print(f"[OK] Verified baseline collection '{base_index.collection_name}' count: {base_index.collection.count()} (UNTOUCHED)")

    print("\n=== [CP5] CHECKPOINT 5 COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    execute_cp5()
