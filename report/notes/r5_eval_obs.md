# R5 — Evaluation & Observability · Ghi chú thi công

> Sở hữu: `src/evaluation/testset.py`, `src/observability/quality.py`, `src/observability/reporting.py`
> Ngày: 2026-08-06

---

## CP0 · 00:00–00:30 — Đọc code, chốt contract

### 0.1. Môi trường (đã verify)

| Hạng mục | Trạng thái |
|---|---|
| Python | 3.11.9 (yêu cầu `>=3.11,<3.14`) ✓ |
| Virtualenv | `.venv` có sẵn, `pip install -e .` đã chạy — `import core.config` OK |
| pandas | **3.0.5** → Copy-on-Write là mặc định (xem Bẫy 1) |
| Deps | `pandas`, `chromadb`, `sentence_transformers`, `langchain`, `requests`, `pydantic`, `dotenv` import OK |
| `.env` | tồn tại, `LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-2.5-flash`, `GOOGLE_API_KEY` đã set |
| MiniLM-L6-v2 | warm-up (cache chỉ có `paraphrase-multilingual-MiniLM-L12-v2`, không phải model lab dùng) |

`uv` **không có** trên máy này → mọi lệnh chạy bằng `.venv\Scripts\python.exe`, bỏ tiền tố `uv run`.

Giá trị settings quan sát được (`load_settings()`):

```
freshness_threshold_days = 180
top_k                    = 4
max_results              = 24
quality_dir              = data/quality
freshness_report         = data/quality/freshness_report.json
```

### 0.2. Ba ràng buộc từ code có sẵn (không được sửa)

**(a) `qa.py` không dùng LLM để trả lời — nó bốc thẳng một trường metadata.**
`_extract_answer` ([qa.py:20-29](../../src/retrieval/qa.py#L20-L29)) nhận diện intent bằng chuỗi con trong câu hỏi
đã lowercase, rồi trả về đúng một trường. Ground truth của test set phải bằng đúng
trường đó, nếu không `token_f1` sập dù mọi thứ khác đúng.

**(b) Exact lookup bắt title bằng regex nháy đơn.**
`re.search(r"'([^']+)'", question)` ([qa.py:33](../../src/retrieval/qa.py#L33)), rồi `index.lookup()` khớp
`title.lower()` **chính xác tuyệt đối** ([index.py:168-174](../../src/retrieval/index.py#L168-L174)).
→ câu hỏi bắt buộc bọc title trong `'...'`; title chứa `'` bị regex cắt giữa chừng → loại khỏi test set.

**(c) Judge LLM chết âm thầm.**
`_judge_answer` ([metrics.py:61-70](../../src/evaluation/metrics.py#L61-L70)) tạo client LLM **mới cho từng sample**
và bọc `except Exception` trần. 16 câu × 3 trạng thái = **48 lần gọi API**. Gemini free tier ~10 RPM
→ `429` → rơi về heuristic mà pipeline vẫn xanh.
→ Phải tự đếm `judge_fallback_rate` qua `judge.reasoning.startswith("Fallback heuristic judge")`.

**(d) Metadata Chroma chỉ có 8 khóa.** `_build_documents` ([index.py:44-66](../../src/retrieval/index.py#L44-L66))
đọc 9 cột từ DataFrame và đẩy 8 khóa vào metadata:
`paper_id, title, published, authors_joined, categories_joined, summary, abs_url, pdf_url`.
Test set chỉ được dựa trên các trường này.

### 0.3. CHỐT — 4 template câu hỏi và quy tắc ground truth

Dán vào channel nhóm. Không đổi chữ, vì mỗi chuỗi khớp một nhánh `if` trong `_extract_answer`.

| `question_type` | Template | Nhánh khớp | Ground truth |
|---|---|---|---|
| `summary` | `Summarize the paper '<title>'.` | *(fallback)* | `first_sentence(row["summary"])` |
| `authors` | `Who authored '<title>'?` | `"who authored"` | `row["authors_joined"]` |
| `date` | `When was '<title>' published?` | `"when was"` | `row["published"]` |
| `categories` | `What categories are associated with '<title>'?` | `"what categories"` | `row["categories_joined"]` |

Ba luật kèm theo:

1. **Câu summary lấy `first_sentence(summary)`, KHÔNG phải cả abstract** — và phải dùng đúng
   `first_sentence` từ `core.utils`, không tự viết lại.
2. **`ground_truth_doc_ids` lấy nguyên văn `row["paper_id"]`** — không `.lower()`, không strip.
   `metrics.py:116` so nó với `metadata["paper_id"]` giữ nguyên hoa thường.
3. **Loại mọi title chứa `'`** khỏi tập paper được chọn.

### 0.4. CHỐT — thiết kế quality checks (7 hard-fail + 5 warning)

Nguyên tắc: mỗi corruption operator của R4 phải làm **ít nhất một** signal đổi.
Signal nào không đổi cũng phải ghi lại — đó là phần phân tích ăn điểm.

**7 hard-fail** (fail = dataset không dùng được):

| # | Check | Ngưỡng |
|---|---|---|
| 1 | `required_columns_present` | đủ 11 cột bắt buộc |
| 2 | `row_count_min` | `>= 10` |
| 3 | `paper_id_not_null` | 0 rỗng |
| 4 | `paper_id_unique` | 0 trùng |
| 5 | `title_not_empty` | 0 rỗng |
| 6 | `text_for_embedding_not_empty` | 0 rỗng |
| 7 | `summary_usable_ratio` | `>= 0.90` với `summary_chars >= 80` |

**5 warning** (dataset còn dùng được nhưng chất lượng giảm):

| # | Check | Ngưỡng |
|---|---|---|
| 8 | `title_min_length` | 0 title `< 15` ký tự |
| 9 | `authors_present_ratio` | `>= 0.90` |
| 10 | `categories_present_ratio` | `>= 0.80` |
| 11 | `published_iso_format` | 0 giá trị `< 10` ký tự |
| 12 | `freshness_stale_ratio` | `<= 0.20` với `age_days > 180` |

**Ánh xạ corruption → signal dự kiến bắt được:**

| Corruption (R4) | Check dự kiến đổi |
|---|---|
| Drop latest records | `row_count_min`, `latest_published`, `min_age_days` |
| Blank summary | `summary_usable_ratio` |
| Truncate title | `title_min_length` |
| Stale published date | `freshness_stale_ratio`, `stale_rows`, `is_fresh` |
| Duplicate rows | `paper_id_unique` |
| **Inject noise** | **KHÔNG check nào bắt được** → chỉ lộ qua RAG metric |

Dòng cuối là luận điểm trung tâm của phần observability: rule-based validation
không phát hiện được data poisoning; cần semantic monitoring.

### 0.5. CHỐT — freshness payload và 3 đường dẫn

`is_fresh` gồm **hai** điều kiện, vì một điều kiện chỉ bắt được một nửa số corruption:

```
is_fresh = (stale_rows == 0) AND (min_age_days <= 180)
```

- `stale_rows == 0` → bắt operator "stale published date"
- `min_age_days <= 180` → bắt operator "drop paper mới nhất"

`config.py` chỉ định nghĩa **một** `freshness_report`. R5 derive thêm 2 path anh em trong `quality_dir`:

```
data/quality/freshness_report.json             # baseline
data/quality/freshness_report_corrupted.json   # corrupted
data/quality/freshness_report_repaired.json    # repaired
```

Ba `report_name` cho quality: `baseline_quality`, `corrupted_quality`, `repaired_quality`
→ `data/quality/<report_name>.json`.

### 0.6. Yêu cầu contract gửi các vai khác

**Gửi R1 (integrator).** `bundle.summary` từ `metrics.py:133-140` chỉ có 5 khóa và
**không** chứa `judge_fallback_rate` lẫn phân tích theo `question_type` — cả hai nằm trong
`bundle.answers` mà hàm report không nhận. Không đổi chữ ký hàm (contract đóng băng).
Thay vào đó R5 cung cấp helper, R1 merge trước khi gọi report:

```python
from observability.reporting import summarize_judge_reliability, summarize_by_question_type
metrics = {**bundle.summary,
           **summarize_judge_reliability(bundle.answers),
           "by_question_type": summarize_by_question_type(bundle.answers)}
```

Áp dụng cho cả 3 trạng thái trong `phase1.py` và `corruption_flow.py`.

Ngoài ra: `generate_corruption_report` nhận `corrupted_quality` và `repaired_quality`
nhưng **không** nhận `baseline_quality`. Cần chốt với R1 ở CP5 — hoặc truyền thêm,
hoặc chấp nhận bảng quality không có cột baseline và trỏ sang `phase1_report.md`.

**Gửi R3 (cleaning).** R5 cần đúng các kiểu này, nếu không quality check đọc sai:

- `published` là **chuỗi ISO `YYYY-MM-DD`** (rỗng thì `""`, không phải `NaN`) — so sánh
  lexicographic để tìm latest/oldest phụ thuộc điều này
- `age_days` là **số**
- `summary_chars` là **số**
- `text_for_embedding` không rỗng

**Gửi R2 (ingestion).** Giữ `paper_id` ổn định giữa raw → clean → index. R5 dùng nó làm
`ground_truth_doc_ids`; đổi cách sinh ID giữa chừng là test set mất hiệu lực.

### 0.7. Rủi ro đã nhận diện

- **Bẫy 1 · pandas 3.0.5 Copy-on-Write.** `df[mask]['col'] = x` im lặng không làm gì.
  R5 chỉ đọc df nên rủi ro thấp, nhưng nếu CP5 metrics không đổi thì kiểm điều này **trước tiên**.
- **Bẫy JSON.** `write_json` dùng `json.dumps`; `numpy.int64` / `numpy.bool_` không serialize được.
  Mọi kết quả pandas phải ép `int()` / `float()` / `bool()`.
- **`max_results = 24`** (mặc định trong `config.py`) → nếu Crossref trả ít record,
  `row_count_min >= 10` có thể fail ngay ở baseline. Theo dõi khi R2 fetch xong.
- **Chuỗi phụ thuộc R2 → R3 → R5.** Đối sách: test `quality.py` bằng DataFrame giả,
  không chờ dữ liệu thật.

---

## CP1 · 00:30–01:05 — `quality.py`

### 1.1. Đã hoàn thành

- `run_data_quality_checks(df, settings, report_name) -> dict` — 12 check theo thiết kế §0.4,
  ghi `data/quality/<report_name>.json`
- `build_freshness_report(df, settings, report_path) -> dict` — payload theo §0.5,
  ghi ra `report_path` truyền vào

Giữ nguyên chữ ký theo contract đóng băng. Không sửa file của vai khác.

### 1.2. Cách xác minh (không cần chờ R2/R3)

`_smoke_r5.py` ở gốc repo dựng DataFrame giả đúng 16 cột contract, chạy cả 2 hàm trên
3 kịch bản: clean · corrupted · thiếu cột. **File này không commit.**

```powershell
.\.venv\Scripts\python.exe _smoke_r5.py
```

### 1.3. Kết quả smoke test

Chạy 2026-08-06, không exception, JSON ghi được (không dính lỗi numpy serialization):

| Kịch bản | rows | passed | Hard fail | Warning | `is_fresh` |
|---|---|---|---|---|---|
| Baseline sạch | 12 | `True` | – | – | `True` (stale 0/12, latest `2026-07-27`, min_age 10.0) |
| Corrupted | 12 | `False` | `paper_id_unique`, `summary_usable_ratio` | `title_min_length`, `freshness_stale_ratio` | `False` (stale 3/12, latest `2026-06-29`, min_age 38.0) |
| Thiếu cột | 12 | `False` | `required_columns_present`, `text_for_embedding_not_empty` | – | `False` (min_age `None`) |

Ba điều đã chứng minh được:

1. **Corruption làm ≥2 hard check fail** — đạt yêu cầu Definition of Done.
2. **Drop paper mới nhất bị phát hiện qua freshness**, không qua quality check:
   `latest_published` lùi từ `2026-07-27` → `2026-06-29` và `min_age_days` 10 → 38.
   Đây là lý do `is_fresh` phải gồm hai điều kiện.
3. **Thiếu cột không làm crash** — `required_columns_present` fail và báo cáo vẫn ghi ra được,
   nên `phase1.py` của R1 sẽ nhận được lỗi có ngữ cảnh thay vì `KeyError` trần.

Chi tiết `summary_usable_ratio = 0.6667` ở kịch bản corrupted: 2 row bị blank summary,
sau đó thao tác duplicate nhân đôi luôn 2 row đó → 4/12 row không dùng được.
Đúng hành vi mong đợi: các corruption operator **chồng lấn nhau**, nên khi đọc số ở CP5
phải đối chiếu `corruption_log.json` chứ không suy diễn từ tham số của từng operator.

Artifact giả (`data/quality/smoke_*.json`) đã xóa sau khi verify.

### 1.4. Việc còn lại

- [ ] CP2 — `build_test_set` (chờ `cleaning.py` của R3 để đổi từ df giả sang `papers_clean.csv`)
- [ ] CP3 — `generate_phase1_report` + `summarize_judge_reliability`
- [ ] CP5 — chạy quality/freshness trên corrupted, nối corruption log với signal
- [ ] CP6 — `generate_corruption_report`
