"""
Checkpoint 2 Execution Script for Role 4 (R4) - RAG & Demo Owner.

Tasks:
1. Build Chroma collection 'papers-baseline' from data/clean/papers_clean.csv.
2. Smoke test semantic search & exact title lookup.
3. Run RAG Agent demo and export data/results/agent_demo_answers.json.
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
from src.retrieval.index import LocalEmbeddingIndex
from src.retrieval.qa import answer_question
from src.retrieval.agent import build_agent, run_agent_question


def execute_cp2() -> None:
    settings = load_settings()
    paths = settings.paths

    print("=== [CP2] RUNNING RAG BASELINE INDEX & SMOKE TESTS ===")

    # 1. Check clean CSV
    if not paths.clean_csv.exists():
        raise FileNotFoundError(f"Clean CSV not found at {paths.clean_csv}")

    clean_df = pd.read_csv(paths.clean_csv)
    print(f"[OK] Read clean dataset: {len(clean_df)} rows from {paths.clean_csv.name}")

    # 2. Build Chroma Baseline Index
    print(f"\n[1/3] Building Chroma collection '{settings.baseline_collection_name}'...")
    index = LocalEmbeddingIndex.build(
        df=clean_df,
        settings=settings,
        embeddings_output_path=paths.embeddings_json,
    )
    print(f"[OK] Chroma index built successfully! Collection doc count: {index.collection.count()}")

    # 3. Smoke Test Retrieval & Lookup
    print("\n[2/3] Smoke Testing Semantic Search & Exact Lookup...")
    sample_query = "agentic retrieval augmented generation"
    results = index.search(sample_query, top_k=2)
    print(f"  Query: '{sample_query}'")
    print(f"  Retrieved {len(results)} docs:")
    for doc in results:
        print(f"    - Doc ID: {doc.paper_id} | Score: {doc.score:.4f} | Title: {doc.title[:60]}...")

    qa_res = answer_question(sample_query, settings=settings, index=index)
    print(f"  Exact/RAG QA Answer snippet: {qa_res.answer[:120]}...")

    # 4. Agent Demo Execution
    print("\n[3/3] Running RAG Agent Demo & Exporting Answers...")
    agent_questions = [
        "Summarize the paper on autonomous agents.",
        "What categories are associated with RAG models?",
        "Who authored the paper on deep retrieval augmented generation?",
    ]

    answers_list: list[dict[str, str]] = []
    agent = None
    try:
        agent = build_agent(settings=settings, index=index)
    except Exception as e:
        print(f"  [WARN] Failed to initialize agent (e.g. LLM API Key required): {e}")

    for q in agent_questions:
        if agent is not None:
            try:
                ans = run_agent_question(agent, q)
                answers_list.append({"question": q, "answer": ans, "status": "success"})
                print(f"  Q: {q}\n  A: {ans[:120]}...\n")
            except Exception as e:
                fallback_ans = f"Agent execution fallback: {e}"
                answers_list.append({"question": q, "answer": fallback_ans, "status": "fallback"})
                print(f"  Q: {q}\n  A (Fallback): {fallback_ans}\n")
        else:
            fallback_ans = "Agent offline (LLM key not configured)"
            answers_list.append({"question": q, "answer": fallback_ans, "status": "offline"})
            print(f"  Q: {q}\n  A (Offline): {fallback_ans}\n")

    # Export agent_demo_answers.json
    paths.demo_answers.parent.mkdir(parents=True, exist_ok=True)
    with open(paths.demo_answers, "w", encoding="utf-8") as f:
        json.dump(answers_list, f, indent=2, ensure_ascii=False)
    print(f"[OK] Exported agent demo answers to {paths.demo_answers}")

    print("\n=== [CP2] CHECKPOINT 2 COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    execute_cp2()
