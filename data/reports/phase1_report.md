# Phase 1 Report — Baseline

Sinh lúc: `2026-08-06T13:15:57.871288+00:00`

Mọi số liệu trong báo cáo này được đọc trực tiếp từ artifact JSON do pipeline ghi ra.

---

## 1. Nguồn dữ liệu và run context

| Mục | Giá trị |
|---|---|
| Nguồn | Crossref REST API |
| Query | agentic retrieval augmented generation large language model |
| Filter | from-pub-date:2026-02-07,has-abstract:true |
| max_results | 48 |
| run_date | 2026-08-06T13:15:35.322351+00:00 |
| Đã fetch lại nguồn | ❌ không |
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

| Mục | Giá trị |
|---|---|
| Chế độ judge | `heuristic` |
| Số sample rơi về heuristic | 14 |
| Tỉ lệ fallback | 1.0000 |

> ⚠️ **Toàn bộ sample rơi về heuristic judge.** `judge_accuracy` và `mean_judge_score` ở trên **không phải LLM-as-a-judge** — chúng chỉ là ngưỡng đặt trên `token_f1`. Nguyên nhân: `_judge_answer` tạo client LLM mới cho từng sample, số lần gọi vượt rate limit của provider, và `except Exception` nuốt lỗi nên pipeline vẫn báo thành công.

### 2.2. Metric theo loại câu hỏi

| Loại | Samples | Retrieval hit | Token F1 | Judge acc |
|---|---|---|---|---|
| `authors` | 3 | 1.0000 | 1.0000 | 1.0000 |
| `date` | 3 | 1.0000 | 1.0000 | 1.0000 |
| `summary` | 8 | 1.0000 | 1.0000 | 1.0000 |

### 2.3. Ví dụ hit và miss

**Hit tốt nhất** — `summary-01` (summary)

| Trường | Nội dung |
|---|---|
| Câu hỏi | Summarize the paper 'Reliable retrieval-augmented feature generation with large language model reasoning'. |
| Ground truth | Abstract Feature generation can significantly enhance learning outcomes, particularly for tasks with limited data. |
| Agent trả lời | Abstract Feature generation can significantly enhance learning outcomes, particularly for tasks with limited data. |
| Doc ID kỳ vọng | 10.1007/s10115-026-02792-4 |
| Doc ID retrieve được | 10.1007/s10115-026-02792-4, 10.63503/j.ijaimd.2026.233, 10.55041/isjem07213, 10.36713/epra26155 |
| Retrieval hit | ✅ có |
| Token F1 | 1.0000 |
| Judge score | 5 |

**Miss loại 1 — retrieval lấy nhầm document:** không có sample nào.

**Miss loại 2 — retrieval đúng nhưng trả lời lệch:** không có sample nào.

## 3. Data quality

| Mục | Giá trị |
|---|---|
| Report | `baseline_quality` |
| Số row | 48 |
| Kết luận | ✅ PASS |
| Hard check fail | – |
| Warning | categories_present_ratio, no_future_published |

| Check | Mức | Kết quả | Quan sát | Kỳ vọng |
|---|---|---|---|---|
| `required_columns_present` | hard | ✅ | – | no missing column |
| `row_count_min` | hard | ✅ | 48 | >= 10 rows |
| `paper_id_not_null` | hard | ✅ | 0 | 0 empty paper_id |
| `paper_id_unique` | hard | ✅ | 0 | 0 duplicate paper_id |
| `title_not_empty` | hard | ✅ | 0 | 0 empty title |
| `text_for_embedding_not_empty` | hard | ✅ | 0 | 0 empty text_for_embedding |
| `summary_all_usable` | hard | ✅ | 0 | 0 row |
| `title_min_length` | warn | ✅ | 0 | 0 title shorter than 15 chars |
| `authors_present_ratio` | warn | ✅ | 1.0000 | >= 0.9 |
| `categories_present_ratio` | warn | ❌ | 0.0000 | >= 0.8 |
| `published_iso_format` | warn | ✅ | 0 | 0 value outside YYYY-MM-DD |
| `no_future_published` | warn | ❌ | 1 | 0 row |
| `freshness_no_stale_rows` | warn | ✅ | 0 | 0 row |

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
