"""
Interactive CLI Compare Demo for Day 10 Lab.
Role 4 (R4) - RAG & Demo Owner

Queries 3 Chroma collections (baseline, corrupted, repaired) simultaneously
and displays retrieved contexts and answers side-by-side.
"""

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.config import load_settings
from src.retrieval.index import LocalEmbeddingIndex
from src.retrieval.qa import answer_question


def run_comparison(question: str) -> None:
    settings = load_settings()
    paths = settings.paths

    print(f"\n================================================================================")
    print(f"[QUERY] CAU HOI: {question}")
    print(f"================================================================================\n")

    # 1. Baseline
    print("--------------------------------------------------------------------------------")
    print("--> [1/3] TRANG THAI BASELINE (papers-baseline)")
    print("--------------------------------------------------------------------------------")
    if paths.embeddings_json.exists():
        try:
            index_base = LocalEmbeddingIndex.load(paths.embeddings_json, settings)
            res_base = answer_question(question, settings=settings, index=index_base)
            print(f"[Answer] {res_base.answer}")
            print(f"[Docs]   {res_base.retrieved_doc_ids}")
        except Exception as e:
            print(f"[WARN] Loi truy van Baseline: {e}")
    else:
        print("[WARN] Chua co baseline embedding manifest (Chua chay script/run_phase1.py).")

    # 2. Corrupted
    print("\n--------------------------------------------------------------------------------")
    print("--> [2/3] TRANG THAI CORRUPTED (papers-corrupted)")
    print("--------------------------------------------------------------------------------")
    if paths.corrupted_embeddings_json.exists():
        try:
            index_corr = LocalEmbeddingIndex.load(paths.corrupted_embeddings_json, settings)
            res_corr = answer_question(question, settings=settings, index=index_corr)
            print(f"[Answer] {res_corr.answer}")
            print(f"[Docs]   {res_corr.retrieved_doc_ids}")
        except Exception as e:
            print(f"[WARN] Loi truy van Corrupted: {e}")
    else:
        print("[WARN] Chua co corrupted embedding manifest (Chua chay script/run_corruption_flow.py).")

    # 3. Repaired
    print("\n--------------------------------------------------------------------------------")
    print("--> [3/3] TRANG THAI REPAIRED (papers-repaired)")
    print("--------------------------------------------------------------------------------")
    if paths.repaired_embeddings_json.exists():
        try:
            index_rep = LocalEmbeddingIndex.load(paths.repaired_embeddings_json, settings)
            res_rep = answer_question(question, settings=settings, index=index_rep)
            print(f"[Answer] {res_rep.answer}")
            print(f"[Docs]   {res_rep.retrieved_doc_ids}")
        except Exception as e:
            print(f"[WARN] Loi truy van Repaired: {e}")
    else:
        print("[WARN] Chua co repaired embedding manifest (Chua hoan tat corruption flow).")

    print("\n================================================================================\n")


def main() -> None:
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        run_comparison(question)
    else:
        sample_questions = [
            "Summarize the paper on agentic retrieval augmented generation.",
            "What categories are associated with LLM data observability?",
            "Who authored the paper on RAG pipeline evaluation?",
        ]
        print("=== DEMO SO SÁNH CÂU TRẢ LỜI RAG NÓNG (3 TRẠNG THÁI) ===")
        print("Chọn câu hỏi hoặc tự nhập câu hỏi của bạn:\n")
        for i, q in enumerate(sample_questions, 1):
            print(f"  [{i}] {q}")
        print("  [0] Tự nhập câu hỏi khác...")

        choice = input("\nNhập lựa chọn (0-3) [Default: 1]: ").strip()
        if choice == "2":
            query = sample_questions[1]
        elif choice == "3":
            query = sample_questions[2]
        elif choice == "0":
            query = input("Nhập câu hỏi của bạn: ").strip()
        else:
            query = sample_questions[0]

        if query:
            run_comparison(query)


if __name__ == "__main__":
    main()
