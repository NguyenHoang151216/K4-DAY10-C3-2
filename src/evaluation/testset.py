from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

MIN_DOCUMENTS = 8
MIN_SAMPLES = 4
TARGET_PAPERS = 8
MIN_GROUND_TRUTH_CHARS = 20

# Moi template khop DUNG mot nhanh cua `_extract_answer` trong retrieval/qa.py.
# Doi chu o day la doi truong metadata ma agent tra ve -> ground truth lech ->
# token_f1 sap ma khong co dau hieu nao chi ra nguyen nhan.
TEMPLATES: dict[str, str] = {
    "summary": "Summarize the paper '{title}'.",
    "authors": "Who authored '{title}'?",
    "date": "When was '{title}' published?",
    "categories": "What categories are associated with '{title}'?",
}

# (question_type, offset trong danh sach paper da chon, so cau muon tao).
# Offset lech nhau de 4 loai cau hoi trai deu tren 8 paper thay vi don vao 3 paper dau.
QUESTION_PLAN: list[tuple[str, int, int]] = [
    ("summary", 0, 8),
    ("authors", 0, 3),
    ("date", 3, 3),
    ("categories", 6, 2),
]

# Cac cum tu `_extract_answer` dung de nhan dien intent. Title chua chung se bi
# nhung vao cau hoi va be nhanh sang truong metadata khac - vi du paper ten
# "When Was BERT Trained?" lam cau summary tra ve `published`.
_INTENT_KEYWORDS = (
    "who authored",
    "list the authors",
    "when was",
    "publication date",
    "published on",
    "what categories",
)


def _text_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([""] * len(df), dtype="object")
    return df[column].fillna("").astype(str).str.strip()


def _ground_truth(question_type: str, row: dict[str, Any]) -> str:
    """Tra ve dung gia tri ma `_extract_answer` se tra cho cau hoi loai nay."""
    if question_type == "authors":
        return str(row.get("authors_joined", "")).strip()
    if question_type == "date":
        return str(row.get("published", "")).strip()
    if question_type == "categories":
        return str(row.get("categories_joined", "")).strip()
    # Nhanh fallback cua qa.py: first_sentence(summary), KHONG phai ca abstract.
    return first_sentence(str(row.get("summary", "")))


def _eligible_papers(df: pd.DataFrame) -> pd.DataFrame:
    """Loc paper dung duoc lam cau hoi.

    Hai dieu kien dau lien quan truc tiep den `qa.py`:
    - title chua dau nhay don bi regex `r"'([^']+)'"` cat giua chung -> exact lookup fail
    - title chua tu khoa intent lam cau hoi bi nhan dien sai loai
    """
    title = _text_column(df, "title")
    summary = _text_column(df, "summary")
    lowered_title = title.str.lower()

    has_intent_keyword = pd.Series(False, index=df.index)
    for keyword in _INTENT_KEYWORDS:
        has_intent_keyword |= lowered_title.str.contains(keyword, regex=False)

    usable = (
        title.ne("")
        & ~title.str.contains("'", regex=False)
        & ~has_intent_keyword
        & summary.ne("")
        & summary.map(first_sentence).str.len().ge(MIN_GROUND_TRUTH_CHARS)
    )
    return df.loc[usable].copy()


def _select_papers(df: pd.DataFrame, k: int = TARGET_PAPERS) -> pd.DataFrame:
    """Chon paper dai dien mot cach deterministic.

    Khong dung random: test set phai giong het nhau o ca ba trang thai baseline /
    corrupted / repaired, neu khong phep so sanh mat y nghia. Moi khoa sort deu
    co tie-break bang `paper_id` de ket qua on dinh ke ca khi gia tri chinh trung nhau.
    """
    eligible = _eligible_papers(df)
    if eligible.empty:
        raise ValueError(
            "Khong co paper nao dung duoc cho test set. Kiem tra title rong, "
            "title chua dau nhay don, hoac summary qua ngan trong cleaned dataframe."
        )

    by_date = eligible.sort_values(["published", "paper_id"], ascending=[False, True], kind="mergesort")
    by_length = eligible.sort_values(["summary_chars", "paper_id"], ascending=[False, True], kind="mergesort")
    middle = max(0, len(by_date) // 2 - 1)

    picked = pd.concat(
        [
            by_date.head(2),                        # 2 paper moi nhat
            by_date.tail(2),                        # 2 paper cu nhat
            by_length.head(2),                      # 2 abstract dai nhat
            by_date.iloc[middle:middle + 2],        # 2 paper o giua timeline
        ]
    ).drop_duplicates(subset="paper_id")

    # Bon tang tren chong lan nhau la chuyen binh thuong: paper moi nhat cung co
    # the la paper co abstract dai nhat. Khong bu them thi so paper tut xuong va
    # keo theo so cau hoi, lam test set yeu di ma khong co canh bao nao.
    if len(picked) < k:
        remaining = by_date[~by_date["paper_id"].isin(picked["paper_id"])]
        picked = pd.concat([picked, remaining.head(k - len(picked))])

    return picked.head(k)


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao evaluation set co dinh tu cleaned dataframe va ghi ra output_path.

    Moi sample gom id, question_type, question, ground_truth va ground_truth_doc_ids -
    dung 5 truong ma `evaluate_pipeline` doc. Cau hoi khong co ground truth (vi du
    paper thieu categories) bi bo qua thay vi tao ground truth rong, vi ground truth
    rong lam `token_f1` bang 0 va keo metric xuong ma khong phai loi cua retrieval.
    """
    if len(df) < MIN_DOCUMENTS:
        raise ValueError(
            f"Can it nhat {MIN_DOCUMENTS} document de tao test set, chi co {len(df)}. "
            "Kiem tra buoc cleaning va so record fetch tu Crossref."
        )

    papers = _select_papers(df).to_dict(orient="records")
    rows: list[dict[str, Any]] = []
    shortfall: list[str] = []

    for question_type, offset, count in QUESTION_PLAN:
        taken = 0
        for step in range(len(papers)):
            if taken >= count:
                break
            row = papers[(offset + step) % len(papers)]
            ground_truth = _ground_truth(question_type, row)
            if not ground_truth:
                continue
            taken += 1
            rows.append(
                {
                    "id": f"{question_type}-{taken:02d}",
                    "question_type": question_type,
                    "question": TEMPLATES[question_type].format(title=row["title"]),
                    "ground_truth": ground_truth,
                    # Nguyen van tu dataframe: metrics.py so no voi metadata["paper_id"],
                    # doi hoa thuong o day la retrieval_hit_rate ve 0.
                    "ground_truth_doc_ids": [row["paper_id"]],
                }
            )

        if taken < count:
            shortfall.append(f"{question_type} {taken}/{count}")

    if len(rows) < MIN_SAMPLES:
        raise ValueError(
            f"Test set chi co {len(rows)} sample, can it nhat {MIN_SAMPLES}. "
            "statistics.mean() trong metrics.py se khong on dinh voi so sample nay."
        )

    write_json(Path(output_path), rows)
    print(f"[testset] {len(papers)} papers -> {len(rows)} questions | {output_path}")
    if shortfall:
        # Thuong gap: Crossref khong tra field `subject` nen `categories_joined` rong
        # va loai cau hoi categories bien mat. Bao ra thay vi im lang, de report
        # khong ke nham la da danh gia du 4 loai cau hoi.
        print(f"[testset] THIEU so voi ke hoach: {', '.join(shortfall)} - ghi ro trong report")
    return rows
