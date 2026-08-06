from __future__ import annotations

from pathlib import Path
from typing import Any

from core.utils import now_utc, write_text

# `_judge_answer` trong metrics.py nuot moi Exception va roi ve heuristic voi dung
# chuoi nay. Do la dau vet DUY NHAT con lai de biet judge LLM co that su chay hay khong.
FALLBACK_JUDGE_PREFIX = "Fallback heuristic judge"

# 4 metric chinh, dung chung cho phase1 report va comparison report o CP6.
METRIC_KEYS = ["retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"]

_METRIC_LABELS = {
    "samples": "Số sample",
    "retrieval_hit_rate": "Retrieval hit rate",
    "mean_token_f1": "Mean token F1",
    "judge_accuracy": "Judge accuracy",
    "mean_judge_score": "Mean judge score",
}

_SOURCE_LABELS = {
    "source_api": "Nguồn",
    "source_query": "Query",
    "source_filter": "Filter",
    "max_results": "max_results",
    "run_date": "run_date",
    "source_refreshed": "Đã fetch lại nguồn",
    "raw_record_count": "Raw records vào",
    "clean_record_count": "Clean rows ra",
    "input_records": "Raw records vào",
    "output_rows": "Clean rows ra",
    "duplicates_removed": "Bị dedupe",
    "summary_min_chars_used": "Ngưỡng summary_chars",
    "threshold_relaxed": "Đã hạ ngưỡng",
    "rows_without_categories": "Row thiếu categories",
    "embedding_model": "Embedding model",
    "collection_name": "Collection",
    "top_k": "top_k",
}


# --------------------------------------------------------------------------- format


def _fmt(value: Any) -> str:
    """Format mot gia tri de dat vao o bang markdown."""
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "✅ có" if value else "❌ không"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value) if value else "–"
    if isinstance(value, dict):
        return ", ".join(f"{key}={val}" for key, val in value.items()) if value else "–"
    text = str(value)
    return text if text.strip() else "–"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return ["*(không có dữ liệu)*", ""]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    lines.extend("| " + " | ".join(cells) + " |" for cells in rows)
    lines.append("")
    return lines


def _truncate(text: str, limit: int = 220) -> str:
    """Cat ngan va bo xuong dong / dau gach dung de khong pha cau truc bang markdown."""
    flat = " ".join(str(text).split()).replace("|", "\\|")
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


# --------------------------------------------------------------------------- helpers cho R1


def summarize_judge_reliability(answers: list[dict[str, Any]]) -> dict[str, Any]:
    """Do xem judge LLM co that su chay khong.

    `_judge_answer` tao client LLM moi cho tung sample va bat `except Exception` tran,
    nen rate limit lam judge chet ma pipeline van xanh va metric van dep. Khong dem
    o day thi report se goi ket qua heuristic la "LLM-as-a-judge".
    """
    total = len(answers)
    fallback = sum(
        1
        for item in answers
        if str(item.get("judge", {}).get("reasoning", "")).startswith(FALLBACK_JUDGE_PREFIX)
    )
    rate = round(fallback / total, 4) if total else 0.0
    if rate == 0.0:
        mode = "llm"
    elif rate == 1.0:
        mode = "heuristic"
    else:
        mode = "mixed"
    return {"judge_fallback_count": fallback, "judge_fallback_rate": rate, "judge_mode": mode}


def summarize_by_question_type(answers: list[dict[str, Any]]) -> dict[str, Any]:
    """Tach metric theo loai cau hoi.

    Can thiet vi cac corruption operator tac dong khong deu: blank summary ha
    token_f1 cua cau summary nhung khong dung den cau date. Nhin metric tong the
    se khong thay dieu do.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in answers:
        grouped.setdefault(str(item.get("question_type", "unknown")), []).append(item)

    result: dict[str, Any] = {}
    for question_type, items in sorted(grouped.items()):
        count = len(items)
        result[question_type] = {
            "samples": count,
            "retrieval_hit_rate": round(sum(1 for i in items if i.get("retrieval_hit")) / count, 4),
            "mean_token_f1": round(sum(float(i.get("token_f1", 0.0)) for i in items) / count, 4),
            "judge_accuracy": round(
                sum(1 for i in items if i.get("judge", {}).get("correct")) / count, 4
            ),
        }
    return result


def _example(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id", ""),
        "question_type": item.get("question_type", ""),
        "question": item.get("question", ""),
        "ground_truth": item.get("ground_truth", ""),
        "answer": item.get("answer", ""),
        "ground_truth_doc_ids": list(item.get("ground_truth_doc_ids", [])),
        "retrieved_doc_ids": list(item.get("retrieved_doc_ids", [])),
        "retrieval_hit": bool(item.get("retrieval_hit")),
        "token_f1": round(float(item.get("token_f1", 0.0)), 4),
        "judge_score": item.get("judge", {}).get("score"),
    }


def summarize_retrieval_examples(answers: list[dict[str, Any]]) -> dict[str, Any]:
    """Chon sample dai dien cho tung che do hong, khong gop lam mot "worst case".

    Hai che do hong den tu hai nguyen nhan khac han va can hai cach sua khac nhau:

    - `retrieval_miss`: lay nham document. Loi nam o index hoac o exact-title lookup.
    - `answer_miss`: lay dung document nhung noi dung tra loi van lech. Loi nam o
      du lieu trong metadata hoac o ground truth.

    Gop chung lai roi chon theo token_f1 thap nhat se giau mat che do con lai: mot
    retrieval miss van co the co token_f1 cao khi hai document co noi dung gan giong.
    """
    if not answers:
        return {}

    def score(item: dict[str, Any]) -> float:
        return float(item.get("token_f1", 0.0))

    hits = [item for item in answers if item.get("retrieval_hit")]
    misses = [item for item in answers if not item.get("retrieval_hit")]

    examples: dict[str, Any] = {}
    if hits:
        examples["best_hit"] = _example(max(hits, key=score))
        worst_hit = min(hits, key=score)
        # Chi bao la answer_miss khi cau tra loi thuc su lech ground truth.
        if score(worst_hit) < 1.0:
            examples["answer_miss"] = _example(worst_hit)
    if misses:
        examples["retrieval_miss"] = _example(min(misses, key=score))
    return examples


def enrich_metrics(summary: dict[str, Any], answers: list[dict[str, Any]]) -> dict[str, Any]:
    """Bo sung cho `bundle.summary` nhung thong tin chi co trong `bundle.answers`.

    Goi ham nay trong phase1.py va corruption_flow.py truoc khi goi report:

        metrics = enrich_metrics(bundle.summary, bundle.answers)

    Lam vay de khong phai doi chu ky cua cac ham report (contract dong bang), va de
    file metrics ghi ra dia cung mang theo do tin cay cua judge.
    """
    return {
        **summary,
        **summarize_judge_reliability(answers),
        "by_question_type": summarize_by_question_type(answers),
        "examples": summarize_retrieval_examples(answers),
    }


# --------------------------------------------------------------------------- corruption impact

# Anh xa tung corruption operator sang signal duoc KY VONG bat duoc no, kem moi de
# doa that ma no mo phong. `inject_noise` co danh sach rong la CO Y, khong phai
# thieu sot: khong mot schema check nao bat duoc data poisoning.
CORRUPTION_EXPECTATIONS: dict[str, dict[str, Any]] = {
    "drop_latest": {
        "checks": [],
        "signals": [],
        "freshness": ["latest_published", "min_age_days"],
        "threat": "Knowledge base stale — agent trả lời theo thông tin cũ",
    },
    "blank_summary": {
        "checks": ["summary_all_usable"],
        "signals": ["unusable_summaries"],
        "freshness": [],
        "threat": "Mất knowledge context — agent không còn nội dung để trả lời",
    },
    "inject_noise": {
        "checks": [],
        "signals": [],
        "freshness": [],
        "threat": "Data poisoning — prompt injection nằm trong chính corpus",
    },
    "truncate_title": {
        "checks": ["title_min_length"],
        "signals": ["short_titles"],
        "freshness": [],
        "threat": "Entity/document resolution failure — hỏng exact-title lookup",
    },
    "stale_date": {
        "checks": ["freshness_no_stale_rows"],
        "signals": ["stale_rows"],
        "freshness": ["is_fresh", "max_age_days", "oldest_published"],
        "threat": "Temporal reasoning sai — agent tưởng tài liệu cũ hơn thực tế",
    },
    "duplicate_rows": {
        "checks": ["paper_id_unique"],
        "signals": ["duplicate_paper_ids"],
        "freshness": [],
        "threat": "Retrieval bias — top-k kém đa dạng vì lặp cùng một document",
    },
}

_FRESHNESS_WATCHED = (
    "latest_published",
    "oldest_published",
    "min_age_days",
    "max_age_days",
    "stale_rows",
    "stale_ratio",
    "future_rows",
    "is_fresh",
    "total_rows",
)


def _check_status(quality: dict[str, Any]) -> dict[str, bool]:
    return {str(check["name"]): bool(check["passed"]) for check in quality.get("checks", [])}


def summarize_corruption_impact(
    corruption_log: dict[str, Any],
    baseline_quality: dict[str, Any],
    corrupted_quality: dict[str, Any],
    baseline_freshness: dict[str, Any],
    corrupted_freshness: dict[str, Any],
) -> dict[str, Any]:
    """Noi tung operator trong corruption log voi signal that su doi.

    Tra ve ca hai chieu:
    - `detected`: operator nao bi bat, bat boi check/signal nao
    - `undetected_operators`: operator nao KHONG signal cau truc nao bat duoc

    Chieu thu hai moi la ket luan quan trong. Bao cao chi liet ke nhung thu bi bat
    se ngam ngam goi y rang he thong quality phat hien duoc moi loai loi du lieu -
    trong khi thuc te co it nhat mot loai no khong the thay.
    """
    baseline_checks = _check_status(baseline_quality)
    corrupted_checks = _check_status(corrupted_quality)
    baseline_signals = baseline_quality.get("signals", {}) or {}
    corrupted_signals = corrupted_quality.get("signals", {}) or {}

    newly_failing = {
        name
        for name, passed in corrupted_checks.items()
        if not passed and baseline_checks.get(name, True)
    }
    moved_signals = {
        name
        for name, value in corrupted_signals.items()
        if name in baseline_signals and value != baseline_signals[name]
    }
    changed_freshness = {
        key
        for key in _FRESHNESS_WATCHED
        if key in baseline_freshness and baseline_freshness.get(key) != corrupted_freshness.get(key)
    }

    operators: list[dict[str, Any]] = []
    for operation in corruption_log.get("operations", []):
        op_type = str(operation.get("type", ""))
        expectation = CORRUPTION_EXPECTATIONS.get(op_type, {})
        fired_checks = sorted(set(expectation.get("checks", [])) & newly_failing)
        fired_signals = sorted(set(expectation.get("signals", [])) & moved_signals)
        fired_freshness = sorted(set(expectation.get("freshness", [])) & changed_freshness)
        operators.append(
            {
                "type": op_type,
                "count": int(operation.get("count", 0)),
                "paper_ids": list(operation.get("paper_ids", [])),
                "threat": expectation.get("threat", ""),
                "expected_checks": list(expectation.get("checks", [])),
                "checks_fired": fired_checks,
                "signals_moved": fired_signals,
                "freshness_changed": fired_freshness,
                "detected": bool(fired_checks or fired_signals or fired_freshness),
                "detectable_by_design": bool(
                    expectation.get("checks") or expectation.get("signals") or expectation.get("freshness")
                ),
            }
        )

    undetected = [item["type"] for item in operators if not item["detected"]]
    unexplained = sorted(
        newly_failing - {name for item in operators for name in item["checks_fired"]}
    )

    return {
        "seed": corruption_log.get("seed"),
        "row_count_before": corruption_log.get("row_count_before"),
        "row_count_after": corruption_log.get("row_count_after"),
        "rows_changed_verified": corruption_log.get("rows_changed_verified"),
        "operators": operators,
        "checks_newly_failing": sorted(newly_failing),
        "checks_still_passing": sorted(
            name for name, passed in corrupted_checks.items() if passed
        ),
        "checks_unexplained": unexplained,
        "signal_deltas": {
            name: {"baseline": baseline_signals.get(name), "corrupted": value}
            for name, value in corrupted_signals.items()
            if name in baseline_signals
        },
        "freshness_deltas": {
            key: {"baseline": baseline_freshness.get(key), "corrupted": corrupted_freshness.get(key)}
            for key in _FRESHNESS_WATCHED
            if key in baseline_freshness
        },
        "undetected_operators": undetected,
        "detection_rate": round(
            sum(1 for item in operators if item["detected"]) / len(operators), 4
        )
        if operators
        else 0.0,
    }


# --------------------------------------------------------------------------- section


def _section_source(source_summary: dict[str, Any]) -> list[str]:
    lines = ["## 1. Nguồn dữ liệu và run context", ""]
    if not source_summary:
        return lines + ["*(pipeline không truyền source summary)*", ""]

    known = [
        [_SOURCE_LABELS[key], _fmt(source_summary[key])]
        for key in _SOURCE_LABELS
        if key in source_summary
    ]
    extra = [
        [f"`{key}`", _fmt(value)]
        for key, value in source_summary.items()
        if key not in _SOURCE_LABELS
    ]
    return lines + _table(["Mục", "Giá trị"], known + extra)


def _section_metrics(metrics: dict[str, Any]) -> list[str]:
    rows = [
        [_METRIC_LABELS.get(key, key), _fmt(metrics[key])]
        for key in ["samples", *METRIC_KEYS]
        if key in metrics
    ]
    return ["## 2. Evaluation metrics", ""] + _table(["Metric", "Giá trị"], rows)


def _section_judge(metrics: dict[str, Any]) -> list[str]:
    lines = ["### 2.1. Độ tin cậy của judge", ""]
    if "judge_mode" not in metrics:
        return lines + [
            "> ⚠️ Không đo được. Pipeline chưa gọi `enrich_metrics(bundle.summary, bundle.answers)` "
            "trước khi sinh report, nên không biết `judge_accuracy` đến từ LLM hay từ heuristic.",
            "",
        ]

    mode = metrics["judge_mode"]
    lines += _table(
        ["Mục", "Giá trị"],
        [
            ["Chế độ judge", f"`{mode}`"],
            ["Số sample rơi về heuristic", _fmt(metrics.get("judge_fallback_count"))],
            ["Tỉ lệ fallback", _fmt(metrics.get("judge_fallback_rate"))],
        ],
    )

    if mode == "heuristic":
        lines += [
            "> ⚠️ **Toàn bộ sample rơi về heuristic judge.** `judge_accuracy` và "
            "`mean_judge_score` ở trên **không phải LLM-as-a-judge** — chúng chỉ là ngưỡng đặt "
            "trên `token_f1`. Nguyên nhân: `_judge_answer` tạo client LLM mới cho từng sample, "
            "số lần gọi vượt rate limit của provider, và `except Exception` nuốt lỗi nên "
            "pipeline vẫn báo thành công.",
            "",
        ]
    elif mode == "mixed":
        lines += [
            "> ⚠️ Một phần sample dùng LLM, phần còn lại rơi về heuristic. Hai nhóm này "
            "**không cùng thang đo**, nên không được so sánh trực tiếp giữa các trạng thái "
            "nếu tỉ lệ fallback khác nhau.",
            "",
        ]
    return lines


def _section_by_type(metrics: dict[str, Any]) -> list[str]:
    by_type = metrics.get("by_question_type") or {}
    lines = ["### 2.2. Metric theo loại câu hỏi", ""]
    if not by_type:
        return lines + ["*(không có dữ liệu — pipeline chưa gọi `enrich_metrics`)*", ""]

    rows = [
        [
            f"`{question_type}`",
            _fmt(values.get("samples")),
            _fmt(values.get("retrieval_hit_rate")),
            _fmt(values.get("mean_token_f1")),
            _fmt(values.get("judge_accuracy")),
        ]
        for question_type, values in by_type.items()
    ]
    return lines + _table(
        ["Loại", "Samples", "Retrieval hit", "Token F1", "Judge acc"], rows
    )


def _render_example(title: str, example: dict[str, Any], note: str = "") -> list[str]:
    lines = [f"**{title}** — `{example.get('id', '')}` ({example.get('question_type', '')})", ""]
    if note:
        lines += [note, ""]
    lines += _table(
        ["Trường", "Nội dung"],
        [
            ["Câu hỏi", _truncate(example.get("question", ""))],
            ["Ground truth", _truncate(example.get("ground_truth", ""))],
            ["Agent trả lời", _truncate(example.get("answer", ""))],
            ["Doc ID kỳ vọng", _fmt(example.get("ground_truth_doc_ids"))],
            ["Doc ID retrieve được", _fmt(example.get("retrieved_doc_ids"))],
            ["Retrieval hit", _fmt(example.get("retrieval_hit"))],
            ["Token F1", _fmt(example.get("token_f1"))],
            ["Judge score", _fmt(example.get("judge_score"))],
        ],
    )
    return lines


def _section_examples(metrics: dict[str, Any]) -> list[str]:
    examples = metrics.get("examples") or {}
    lines = ["### 2.3. Ví dụ hit và miss", ""]
    if not examples:
        return lines + ["*(không có dữ liệu — pipeline chưa gọi `enrich_metrics`)*", ""]

    if "best_hit" in examples:
        lines += _render_example("Hit tốt nhất", examples["best_hit"])
    else:
        lines += ["**Hit** — không có sample nào retrieval trúng document kỳ vọng.", ""]

    if "retrieval_miss" in examples:
        lines += _render_example(
            "Miss loại 1 — retrieval lấy nhầm document",
            examples["retrieval_miss"],
            "> Document chứa câu trả lời **không** nằm trong top-k. Nguyên nhân ở khâu index "
            "hoặc ở exact-title lookup của `qa.py`, không phải ở khâu sinh câu trả lời. "
            "Lưu ý `token_f1` của sample này vẫn có thể cao nếu document lấy nhầm có nội dung "
            "gần giống — đó là lý do không được dùng `token_f1` một mình để kết luận.",
        )
    else:
        lines += ["**Miss loại 1 — retrieval lấy nhầm document:** không có sample nào.", ""]

    if "answer_miss" in examples:
        lines += _render_example(
            "Miss loại 2 — retrieval đúng nhưng trả lời lệch",
            examples["answer_miss"],
            "> Retrieval lấy **đúng** document nhưng câu trả lời vẫn lệch ground truth. "
            "Nguyên nhân nằm ở dữ liệu trong metadata hoặc ở ground truth, không phải ở retrieval.",
        )
    else:
        lines += ["**Miss loại 2 — retrieval đúng nhưng trả lời lệch:** không có sample nào.", ""]

    return lines


def _section_quality(quality: dict[str, Any]) -> list[str]:
    lines = ["## 3. Data quality", ""]
    if not quality:
        return lines + ["*(pipeline không truyền quality report)*", ""]

    checks = quality.get("checks", [])
    failed = quality.get("failed_checks", [])
    warned = quality.get("warning_checks", [])
    lines += _table(
        ["Mục", "Giá trị"],
        [
            ["Report", f"`{quality.get('report_name', 'n/a')}`"],
            ["Số row", _fmt(quality.get("row_count"))],
            ["Kết luận", "✅ PASS" if quality.get("passed") else "❌ FAIL"],
            ["Hard check fail", _fmt(failed)],
            ["Warning", _fmt(warned)],
        ],
    )
    lines += _table(
        ["Check", "Mức", "Kết quả", "Quan sát", "Kỳ vọng"],
        [
            [
                f"`{check.get('name', '')}`",
                check.get("level", ""),
                "✅" if check.get("passed") else "❌",
                _fmt(check.get("observed")),
                _fmt(check.get("expected")),
            ]
            for check in checks
        ],
    )
    return lines


def _section_freshness(freshness: dict[str, Any]) -> list[str]:
    lines = ["## 4. Freshness", ""]
    if not freshness:
        return lines + ["*(pipeline không truyền freshness report)*", ""]

    return lines + _table(
        ["Mục", "Giá trị"],
        [
            ["Ngưỡng (ngày)", _fmt(freshness.get("threshold_days"))],
            ["Tổng row", _fmt(freshness.get("total_rows"))],
            ["Paper mới nhất", _fmt(freshness.get("latest_published"))],
            ["Paper cũ nhất", _fmt(freshness.get("oldest_published"))],
            ["Row quá hạn", _fmt(freshness.get("stale_rows"))],
            ["Tỉ lệ quá hạn", _fmt(freshness.get("stale_ratio"))],
            ["age_days nhỏ nhất", _fmt(freshness.get("min_age_days"))],
            ["age_days trung vị", _fmt(freshness.get("median_age_days"))],
            ["age_days lớn nhất", _fmt(freshness.get("max_age_days"))],
            ["Kết luận", "✅ tươi" if freshness.get("is_fresh") else "❌ không đạt"],
        ],
    )


def _section_ragas(metrics: dict[str, Any]) -> list[str]:
    ragas = metrics.get("ragas")
    lines = ["## 5. Ragas", ""]
    if not isinstance(ragas, dict) or not ragas:
        return lines + ["*(không chạy)*", ""]
    if "skipped" in ragas:
        return lines + [f"Bỏ qua: {ragas['skipped']}", ""]
    if "error" in ragas:
        return lines + [f"⚠️ Lỗi: {ragas['error']}", ""]
    return lines + _table(
        ["Metric", "Giá trị"], [[f"`{key}`", _fmt(value)] for key, value in ragas.items()]
    )


# --------------------------------------------------------------------------- report


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase.

    Moi so trong report deu lay tu dict duoc truyen vao, khong tinh lai va khong
    hard-code, de `.md` luon khop voi `.json` tren dia. Phan nao thieu du lieu thi
    ghi ro la thieu thay vi bo qua im lang.
    """
    source_summary = source_summary or {}
    metrics = metrics or {}
    quality = quality or {}
    freshness = freshness or {}

    lines: list[str] = [
        "# Phase 1 Report — Baseline",
        "",
        f"Sinh lúc: `{now_utc().isoformat()}`",
        "",
        "Mọi số liệu trong báo cáo này được đọc trực tiếp từ artifact JSON do pipeline ghi ra.",
        "",
        "---",
        "",
    ]
    lines += _section_source(source_summary)
    lines += _section_metrics(metrics)
    lines += _section_judge(metrics)
    lines += _section_by_type(metrics)
    lines += _section_examples(metrics)
    lines += _section_quality(quality)
    lines += _section_freshness(freshness)
    lines += _section_ragas(metrics)

    lines += [
        "## 6. Giới hạn của kết luận",
        "",
        "- `token_f1` so hai tập token tách theo whitespace sau khi lowercase, nên nó mù với "
        "paraphrase và từ đồng nghĩa. Câu trả lời đúng ý nhưng khác chữ vẫn bị chấm thấp.",
        "- `retrieval_hit_rate` chỉ kiểm tra document kỳ vọng có nằm trong top-k hay không, "
        "không đo thứ hạng. Hạng 1 và hạng 4 được tính như nhau.",
        "- `qa.py` trả lời bằng cách lấy thẳng một trường metadata, không sinh văn bản tự do. "
        "Vì vậy các metric ở đây đo chất lượng **dữ liệu và retrieval**, không đo khả năng "
        "diễn đạt của LLM.",
        "",
    ]

    write_text(Path(report_path), "\n".join(lines).rstrip() + "\n")
    print(f"[report] phase1 -> {report_path}")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """TODO(student): viet markdown report so sanh baseline/corrupted/repaired."""
    raise NotImplementedError("Student task: implement corruption comparison report.")
