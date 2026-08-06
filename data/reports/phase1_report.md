# Phase 1 Report — Baseline

Sinh lúc: `2026-08-06T09:26:32.121386+00:00`

Mọi số liệu trong báo cáo này được đọc trực tiếp từ artifact JSON do pipeline ghi ra.

---

## 1. Nguồn dữ liệu và run context

| Mục | Giá trị |
|---|---|
| Nguồn | Crossref REST API |
| Query | agentic retrieval augmented generation large language model |
| Filter | from-pub-date:2026-02-07,has-abstract:true |
| max_results | 48 |
| run_date | 2026-08-06T09:25:13.243798+00:00 |
| Đã fetch lại nguồn | ✅ có |
| Raw records vào | 48 |
| Clean rows ra | 48 |

## 2. Evaluation metrics

| Metric | Giá trị |
|---|---|
| Số sample | 14 |
| Retrieval hit rate | 1.0000 |
| Mean token F1 | 1.0000 |
| Judge accuracy | 1.0000 |
| Mean judge score | 5 |

### 2.1. Độ tin cậy của judge

> ⚠️ Không đo được. Pipeline chưa gọi `enrich_metrics(bundle.summary, bundle.answers)` trước khi sinh report, nên không biết `judge_accuracy` đến từ LLM hay từ heuristic.

### 2.2. Metric theo loại câu hỏi

*(không có dữ liệu — pipeline chưa gọi `enrich_metrics`)*

### 2.3. Ví dụ hit và miss

*(không có dữ liệu — pipeline chưa gọi `enrich_metrics`)*

## 3. Data quality

| Mục | Giá trị |
|---|---|
| Report | `baseline_quality` |
| Số row | 48 |
| Kết luận | ✅ PASS |
| Hard check fail | – |
| Warning | categories_present_ratio |

| Check | Mức | Kết quả | Quan sát | Kỳ vọng |
|---|---|---|---|---|
| `required_columns_present` | hard | ✅ | – | no missing column |
| `row_count_min` | hard | ✅ | 48 | >= 10 rows |
| `paper_id_not_null` | hard | ✅ | 0 | 0 empty paper_id |
| `paper_id_unique` | hard | ✅ | 0 | 0 duplicate paper_id |
| `title_not_empty` | hard | ✅ | 0 | 0 empty title |
| `text_for_embedding_not_empty` | hard | ✅ | 0 | 0 empty text_for_embedding |
| `summary_usable_ratio` | hard | ✅ | 1.0000 | >= 0.9 |
| `title_min_length` | warn | ✅ | 0 | 0 title shorter than 15 chars |
| `authors_present_ratio` | warn | ✅ | 1.0000 | >= 0.9 |
| `categories_present_ratio` | warn | ❌ | 0.0000 | >= 0.8 |
| `published_iso_format` | warn | ✅ | 0 | 0 value outside YYYY-MM-DD |
| `freshness_stale_ratio` | warn | ✅ | 0.0000 | <= 0.2 |

## 4. Freshness

| Mục | Giá trị |
|---|---|
| Ngưỡng (ngày) | 180 |
| Tổng row | 48 |
| Paper mới nhất | 2026-12-01 |
| Paper cũ nhất | 2026-02-12 |
| Row quá hạn | 0 |
| Tỉ lệ quá hạn | 0.0000 |
| age_days nhỏ nhất | -117.0000 |
| age_days trung vị | 66.5000 |
| age_days lớn nhất | 175.0000 |
| Kết luận | ✅ tươi |

## 5. Ragas

Bỏ qua: Set RUN_RAGAS=1 to enable the slower Ragas pass.

## 6. Giới hạn của kết luận

- `token_f1` so hai tập token tách theo whitespace sau khi lowercase, nên nó mù với paraphrase và từ đồng nghĩa. Câu trả lời đúng ý nhưng khác chữ vẫn bị chấm thấp.
- `retrieval_hit_rate` chỉ kiểm tra document kỳ vọng có nằm trong top-k hay không, không đo thứ hạng. Hạng 1 và hạng 4 được tính như nhau.
- `qa.py` trả lời bằng cách lấy thẳng một trường metadata, không sinh văn bản tự do. Vì vậy các metric ở đây đo chất lượng **dữ liệu và retrieval**, không đo khả năng diễn đạt của LLM.
