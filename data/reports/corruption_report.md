# Corruption Report — Baseline vs Corrupted vs Repaired

Sinh lúc: `2026-08-06T13:16:28.711430+00:00`

Ba trạng thái được đánh giá trên **cùng một test set**, cùng embedding model, cùng `top_k` và cùng judge. Chỉ trạng thái dataset thay đổi — đây là điều kiện để phép so sánh có nghĩa.

---

## 1. Bảng so sánh ba trạng thái

| Metric | Baseline | Corrupted | Repaired | corruption_delta | repair_gap | recovery |
|---|---|---|---|---|---|---|
| `retrieval_hit_rate` | 1.0000 | 0.8571 | 1.0000 | -0.1429 | +0.0000 | +0.1429 |
| `mean_token_f1` | 1.0000 | 0.7174 | 1.0000 | -0.2826 | +0.0000 | +0.2826 |
| `judge_accuracy` | 1.0000 | 0.7143 | 1.0000 | -0.2857 | +0.0000 | +0.2857 |
| `mean_judge_score` | 5 | 3.8571 | 5 | -1.1429 | +0.0000 | +1.1429 |

- `corruption_delta = corrupted − baseline` — corruption làm hỏng bao nhiêu
- `repair_gap = repaired − baseline` — sau khi sửa **còn lệch baseline** bao nhiêu
- `recovery = repaired − corrupted` — bước repair kéo lại được bao nhiêu

Cả ba trạng thái được đo trên **14 sample giống hệt nhau**.

## 2. Độ tin cậy của judge

| Trạng thái | judge_mode | Số sample fallback | Tỉ lệ fallback |
|---|---|---|---|
| baseline | heuristic | 14 | 1.0000 |
| corrupted | heuristic | 14 | 1.0000 |
| repaired | heuristic | 14 | 1.0000 |

> ⚠️ **Toàn bộ sample ở cả ba trạng thái đều rơi về heuristic judge.** `judge_accuracy` và `mean_judge_score` trong bảng mục 1 **không phải LLM-as-a-judge** — chúng là ngưỡng đặt trên `token_f1`, nên không mang thêm thông tin độc lập so với `mean_token_f1`. Đọc kết luận dựa vào `retrieval_hit_rate` và `mean_token_f1`.

## 3. Phân tích theo `question_type`

| question_type | Metric | n | Baseline | Corrupted | Repaired | corruption_delta |
|---|---|---|---|---|---|---|
| `authors` | `retrieval_hit_rate` | 3 | 1.0000 | 0.6667 | 1.0000 | -0.3333 |
| `authors` | `mean_token_f1` | 3 | 1.0000 | 0.6667 | 1.0000 | -0.3333 |
| `date` | `retrieval_hit_rate` | 3 | 1.0000 | 1.0000 | 1.0000 | +0.0000 |
| `date` | `mean_token_f1` | 3 | 1.0000 | 1.0000 | 1.0000 | +0.0000 |
| `summary` | `retrieval_hit_rate` | 8 | 1.0000 | 0.8750 | 1.0000 | -0.1250 |
| `summary` | `mean_token_f1` | 8 | 1.0000 | 0.6304 | 1.0000 | -0.3696 |

Loại câu hỏi nào tụt mạnh nhất cho biết corruption chạm vào **trường dữ liệu nào**: `summary` tụt → blank/noise trên abstract; `date` tụt → stale date; `retrieval_hit_rate` tụt ở mọi loại → drop document hoặc truncate title phá exact lookup.

## 4. Data quality: corrupted vs repaired

| Check | Corrupted | Repaired |
|---|---|---|
| `authors_present_ratio` | ✅ có | ✅ có |
| `categories_present_ratio` | ❌ không | ❌ không |
| `freshness_no_stale_rows` | ❌ không | ✅ có |
| `no_future_published` | ✅ có | ❌ không |
| `paper_id_not_null` | ✅ có | ✅ có |
| `paper_id_unique` | ❌ không | ✅ có |
| `published_iso_format` | ✅ có | ✅ có |
| `required_columns_present` | ✅ có | ✅ có |
| `row_count_min` | ✅ có | ✅ có |
| `summary_all_usable` | ❌ không | ✅ có |
| `text_for_embedding_not_empty` | ✅ có | ✅ có |
| `title_min_length` | ❌ không | ✅ có |
| `title_not_empty` | ✅ có | ✅ có |

> Sau repair vẫn còn fail: categories_present_ratio, no_future_published. Cần đối chiếu với kết quả baseline: check nào **fail y hệt ở baseline** là giới hạn của nguồn dữ liệu, **không phải** hệ quả của corruption và cũng không phải repair làm chưa tới.

## 5. Freshness: corrupted vs repaired

| Tín hiệu | Corrupted | Repaired |
|---|---|---|
| `latest_published` | 2026-08-01 | 2026-12-01 |
| `oldest_published` | 2020-04-01 | 2026-02-12 |
| `min_age_days` | 5.0000 | -117.0000 |
| `max_age_days` | 2318.0000 | 175.0000 |
| `stale_rows` | 2 | 0 |
| `stale_ratio` | 0.0408 | 0.0000 |
| `future_rows` | 0 | 1 |
| `is_fresh` | ❌ không | ✅ có |
| `total_rows` | 49 | 48 |

## 6. Kết luận

**Corruption → agent metric.** Metric giảm so với baseline: `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`.

**Repair → phục hồi hoàn toàn.** Mọi metric so sánh đều trở về đúng giá trị baseline (`repair_gap = 0`). Điều này chỉ đạt được khi raw snapshot bất biến còn nguyên và cleaning được replay bằng đúng `run_date` của lần chạy baseline.

**Data quality sau repair.** Check còn fail: categories_present_ratio, no_future_published.

### Giới hạn của kết luận

- Corruption ở quy mô 1–3 dòng trên tập ~48 dòng thường **không vượt được các check dạng tỉ lệ**. Check không fail không có nghĩa dữ liệu còn sạch — nó có thể chỉ là ngưỡng quá lỏng so với quy mô lỗi.
- Noise injection **không có check cấu trúc nào bắt được**: nội dung vẫn đúng kiểu, đúng độ dài, đúng schema. Nó chỉ lộ ra qua RAG metric. Đây là lý do quality check dạng rule không thay thế được semantic monitoring.
- `token_f1` mù với paraphrase, và `retrieval_hit_rate` không đo thứ hạng trong top-k.
