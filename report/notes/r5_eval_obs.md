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

Nguyên tắc: mỗi corruption operator của R3 phải làm **ít nhất một** signal đổi.
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
| 7 | `summary_all_usable` | **0 row** có `summary_chars < 40` |

> Ngưỡng `MIN_SUMMARY_CHARS` để **40**, không phải 80. Lý do: `cleaning.py` hạ ngưỡng
> xuống `SUMMARY_MIN_CHARS_RELAXED = 40` khi số row không đủ `MIN_ROWS = 24`. Nếu quality
> check giữ 80 trong khi cleaning đã dùng 40, check sẽ fail trên một dataset hợp lệ
> và cả nhóm đi tìm lỗi ở nhầm chỗ.
>
> Check này ban đầu là tỉ lệ `>= 0.90`, đã đổi thành ngưỡng tuyệt đối ở CP4 — lý do ở §4.3.

**5 warning** (dataset còn dùng được nhưng chất lượng giảm):

| # | Check | Ngưỡng |
|---|---|---|
| 8 | `title_min_length` | 0 title `< 15` ký tự |
| 9 | `authors_present_ratio` | `>= 0.90` |
| 10 | `categories_present_ratio` | `>= 0.80` |
| 11 | `published_iso_format` | 0 giá trị `< 10` ký tự |
| 12 | `freshness_no_stale_rows` | **0 row** có `age_days > 180` (đổi ở CP4, §4.3) |

**Ánh xạ corruption → signal dự kiến bắt được:**

| Corruption (R3) | Check dự kiến đổi |
|---|---|
| Drop latest records | `row_count_min`, `latest_published`, `min_age_days` |
| Blank summary | `summary_all_usable` |
| Truncate title | `title_min_length` |
| Stale published date | `freshness_no_stale_rows`, `stale_rows`, `is_fresh` |
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
- ~~**`max_results = 24`**~~ → R1 đã nâng lên **48** ở `config.py`, và `run_context.json`
  đã được ghi. Rủi ro `row_count_min >= 10` fail ở baseline giảm đáng kể, nhưng vẫn
  theo dõi khi R2 fetch dataset đầy đủ.
- **Chuỗi phụ thuộc R2 → R3 → R5.** Đối sách: test `quality.py` bằng DataFrame giả,
  không chờ dữ liệu thật.

---

## CP1 · 00:30–01:05 — `quality.py`

### 1.1. Đã hoàn thành

- `run_data_quality_checks(df, settings, report_name) -> dict` — 13 check theo thiết kế §0.4,
  ghi `data/quality/<report_name>.json`
- `build_freshness_report(df, settings, report_path) -> dict` — payload theo §0.5,
  ghi ra `report_path` truyền vào
- `quality_report_name(state)` và `freshness_report_path(settings, state)` — hai helper
  chốt tên artifact cho `baseline` / `corrupted` / `repaired`

Hai helper cuối bổ sung ở CP5, đóng nốt yêu cầu *"Derive 3 path freshness trong
`quality_dir`"* của dòng 481 phân công. Trước đó 3 path chỉ nằm trong note, nên mỗi
người gọi có thể tự đặt tên khác nhau — lệch một chữ là bảng so sánh 3 trạng thái ở CP6
thiếu mất một cột. R1 gọi:

```python
from observability.quality import freshness_report_path, quality_report_name

quality = run_data_quality_checks(df, settings, quality_report_name("corrupted"))
freshness = build_freshness_report(df, settings, freshness_report_path(settings, "corrupted"))
```

Giữ nguyên chữ ký theo contract đóng băng. Không sửa file của vai khác.

### 1.2. Cách xác minh (không cần chờ R2/R3)

`_smoke_r5.py` ở gốc repo dựng DataFrame giả đúng 16 cột contract, chạy cả 2 hàm trên
3 kịch bản: clean · corrupted · thiếu cột. **File này không commit.**

```powershell
.\.venv\Scripts\python.exe _smoke_r5.py
```

### 1.3. Kết quả smoke test

Chạy 2026-08-06, không exception, JSON ghi được (không dính lỗi numpy serialization).

> 📌 Bảng dưới là bản ghi lịch sử của lần chạy CP1, dùng tên check **cũ**:
> `summary_usable_ratio` và `freshness_stale_ratio`. Hai check này đã đổi thành
> `summary_all_usable` và `freshness_no_stale_rows` ở CP4 — lý do ở §4.3. Kết quả
> kiểm chứng mới nhất, trên corruption thật và dataset cỡ thật, nằm ở §4.4.

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

---

## CP2 · 01:05–01:35 — `build_test_set`

### 2.1. Đã hoàn thành

`build_test_set(df, output_path) -> list[dict]` trong `src/evaluation/testset.py`.
Chọn deterministic 8 paper (2 mới nhất · 2 cũ nhất · 2 abstract dài nhất · 2 ở giữa timeline),
sinh 16 câu theo `QUESTION_PLAN` 8 summary / 3 authors / 3 date / 2 categories,
ghi `data/eval/test_set.json` với đúng 5 trường contract.

Từ CP2 trở đi test được trên schema **thật**: `cleaning.py` của R3 đã merge, nên smoke test
dựng `PaperRecord` giả rồi cho chạy qua `build_clean_dataframe()` thay vì tự bịa DataFrame.
Khác biệt quan trọng — nó bắt được các chi tiết mà DataFrame tự dựng bỏ sót,
ví dụ `paper_id` bị hạ lowercase ở `cleaning.py:177`.

### 2.2. Bốn quyết định thiết kế

**(a) Loại thêm một nhóm title mà tài liệu contract chưa nêu.** Bẫy 5 chỉ nói về dấu `'`.
Nhưng title được **nhúng vào mọi câu hỏi**, nên title chứa cụm từ khóa intent của
`_extract_answer` sẽ bẻ nhánh sang trường metadata sai. Ví dụ paper tên
*"When Was BERT Actually Trained"*: câu summary sinh ra chứa `when was` → agent trả về
`published` thay vì `first_sentence(summary)` → `token_f1` bằng 0 mà không có dấu hiệu
nào chỉ ra nguyên nhân. Đã loại cả 6 cụm: `who authored`, `list the authors`, `when was`,
`publication date`, `published on`, `what categories`.

**(b) Bù paper khi 4 tầng chồng lấn.** Paper mới nhất hoàn toàn có thể cũng là paper
abstract dài nhất. Không bù thì `drop_duplicates` cắt xuống 6 paper → 14 câu, và
không có cảnh báo nào. Đã thêm bước top-up từ `by_date` cho đủ 8.

**(c) Không sinh câu hỏi khi ground truth rỗng.** Ground truth rỗng làm `token_f1` bằng 0
và kéo metric xuống vì lý do không liên quan đến retrieval.

**(d) Báo shortfall ra stdout.** Nếu một loại câu hỏi không đủ số lượng kế hoạch,
`build_test_set` in rõ `THIEU so voi ke hoach: categories 0/2`. Im lặng ở đây sẽ khiến
report kể nhầm là đã đánh giá đủ 4 loại câu hỏi.

### 2.3. Phát hiện trên dữ liệu Crossref thật

Chạy trên `data/raw/crossref_records.json` (3 record — smoke test `rows=3` của R2 ở CP0):

| Quan sát | Ý nghĩa |
|---|---|
| `build_clean_dataframe` ra đúng 16 cột | contract khớp |
| **Cả 3 paper có `categories_joined` rỗng** | Crossref thường không trả field `subject` |
| `age_days` 37 / 52 / 154, `is_fresh=True` | freshness đọc đúng ngày thật |
| Title #2 là tiếng Nga (Cyrillic) | không có title nào dính `'` hay từ khóa intent |
| `row_count_min` fail, `categories_present_ratio` warn | quality check phản ứng đúng |
| `build_test_set` raise với 3 document | guard hoạt động |

> ⚠️ **Cảnh báo gửi cả nhóm:** nếu dữ liệu đầy đủ vẫn không có `subject`, loại câu hỏi
> `categories` sẽ biến mất và test set còn **14 câu thay vì 16**. Không phải lỗi —
> nhưng report bắt buộc phải ghi rõ, và số lần gọi LLM judge giảm còn 14 × 3 = 42.

### 2.4. Kết quả smoke test — 16/16 PASS

Kiểm tra mạnh nhất là **contract test cho Bẫy 6**: với mỗi câu hỏi sinh ra, dựng
`SearchResult` bằng đúng 8 khóa metadata mà `index.py:54-63` đẩy vào Chroma, rồi gọi
`_extract_answer` thật của `qa.py` và so với `ground_truth`. Cả 16 câu khớp tuyệt đối.
Đây là bằng chứng ground truth đúng, không phải suy luận từ việc đọc code.

| Nhóm | Kiểm tra |
|---|---|
| Schema | đúng 5 trường contract · id duy nhất · ≥ 4 sample |
| Bẫy 6 | `_extract_answer` trả về đúng `ground_truth` cho cả 16 câu |
| Bẫy 5 | mọi câu có title trong `'...'` · title trích xuất khớp nguyên vẹn · paper có `'` bị loại · paper có từ khóa intent bị loại |
| Doc id | tồn tại trong dataframe · lowercase khớp `paper_id` · không có ground truth rỗng |
| Deterministic | chạy lại giống hệt · **xáo trộn thứ tự row đầu vào vẫn giống hệt** |
| Guard | raise khi < 8 document |
| Suy giảm | toàn bộ paper thiếu categories → 14 câu + cảnh báo shortfall, không crash |

`data/eval/test_set.json` **không** bị smoke test ghi đè — smoke ghi ra
`data/eval/smoke_test_set.json` rồi xóa. Nếu ghi đè, `phase1.py` sẽ load test set giả
khi `REFRESH_TEST_SET` tắt và chạy câu hỏi giả trên dữ liệu thật.

---

## CP3 · 01:35–02:00 — `generate_phase1_report`

### 3.1. Đã hoàn thành

`generate_phase1_report` trong `src/observability/reporting.py`, cùng 4 helper mà pipeline
cần gọi. Report gồm 6 mục: nguồn/run context · evaluation metrics · độ tin cậy judge ·
metric theo loại câu hỏi · ví dụ hit/miss · data quality · freshness · Ragas · giới hạn kết luận.

### 3.2. Một dòng duy nhất R1 phải thêm

`bundle.summary` chỉ có 5 khóa và **không** chứa `judge_fallback_rate`, phân tích theo
`question_type`, hay ví dụ hit/miss — tất cả nằm trong `bundle.answers` mà hàm report
không nhận. Thay vì đổi chữ ký hàm (contract đóng băng), R5 cung cấp `enrich_metrics`:

```python
from observability.reporting import enrich_metrics

metrics = enrich_metrics(bundle.summary, bundle.answers)
generate_phase1_report(settings.paths.baseline_report, source_summary, metrics, quality, freshness)
```

Áp dụng cho cả 3 trạng thái trong `phase1.py` và `corruption_flow.py`. Ghi `metrics` đã
enrich xuống đĩa luôn thì file `*_metrics.json` cũng mang theo độ tin cậy của judge.

Nếu R1 quên gọi, report **vẫn sinh ra bình thường** nhưng ghi rõ ở mục 2.1 và 2.2 là
*"pipeline chưa gọi `enrich_metrics`"* — không im lặng bỏ qua, cũng không crash.

### 3.3. Bẫy 3 — judge chết âm thầm

`summarize_judge_reliability` đếm sample có `judge.reasoning` bắt đầu bằng
`"Fallback heuristic judge"` rồi phân loại `judge_mode` thành `llm` / `mixed` / `heuristic`.

Khi `judge_mode == "heuristic"`, report tự chèn cảnh báo:

> ⚠️ Toàn bộ sample rơi về heuristic judge. `judge_accuracy` và `mean_judge_score`
> **không phải LLM-as-a-judge** — chúng chỉ là ngưỡng đặt trên `token_f1`.

Khi `mixed`, cảnh báo rằng hai nhóm không cùng thang đo nên không so sánh trực tiếp
giữa các trạng thái nếu tỉ lệ fallback khác nhau. Đây là điểm dễ mất điểm nhất ở CP6:
nếu baseline chạy được LLM judge còn corrupted bị rate limit, phần chênh lệch metric
có thể đến từ judge chứ không từ corruption.

### 3.4. Sửa một lỗi thiết kế của chính mình

Bản đầu tôi gộp mọi thất bại thành một mục "trường hợp xấu nhất", chọn theo `token_f1`
thấp nhất **trong nhóm retrieval miss**. Đọc report sinh ra mới thấy nó hiển thị sample
`token_f1 = 0.90` và gọi đó là xấu nhất, trong khi tồn tại sample `token_f1 = 0.00` bị
giấu đi — vì sample đó retrieval **đúng**, chỉ nội dung sai.

Đã tách thành hai chế độ hỏng riêng biệt, vì chúng cần hai cách sửa khác nhau:

| Mục trong report | Nghĩa | Sửa ở đâu |
|---|---|---|
| Miss loại 1 — retrieval lấy nhầm document | doc kỳ vọng không nằm trong top-k | index hoặc exact-title lookup của `qa.py` |
| Miss loại 2 — retrieval đúng nhưng trả lời lệch | lấy đúng doc, nội dung vẫn sai | dữ liệu trong metadata hoặc ground truth |

Chi tiết đáng nhớ: retrieval miss trong ví dụ vẫn có `token_f1 = 0.90` vì document lấy
nhầm có nội dung gần giống. Report ghi thẳng nhận xét này — **không được dùng `token_f1`
một mình để kết luận về retrieval**. Đúng luận điểm phần 9 của `docs/KNOWLEDGE.md`.

### 3.5. Kết quả smoke test — 50/50 PASS

`answers` được dựng đúng schema `evaluate_pipeline` sinh ra (`metrics.py:117-131`),
với câu trả lời tính bằng `_extract_answer` thật và `token_f1` tính bằng `_token_f1` thật,
nên mọi con số trong report là số thật.

| Nhóm | Kiểm tra |
|---|---|
| Helper | `judge_mode` đúng · `by_question_type` phủ hết loại · examples tách đúng 3 trường hợp · `answer_miss` đúng là sample F1 thấp nhất trong nhóm hit |
| Cấu trúc | đủ 10 heading |
| **Số khớp artifact** | `retrieval_hit_rate` · `mean_token_f1` · `judge_accuracy` · `row_count` · `latest_published` · `samples` đều xuất hiện trong `.md` đúng như trong dict nguồn |
| Judge heuristic | `judge_mode = heuristic` → report chứa cảnh báo "không phải LLM-as-a-judge" |
| Không có retrieval miss | report ghi rõ "không có sample nào" thay vì bỏ trống mục |
| Mọi sample hoàn hảo | chỉ còn `best_hit`, không bịa ra miss |
| R1 quên `enrich_metrics` | report vẫn sinh, ghi rõ thiếu |
| Dict rỗng | không crash |

### 3.6. Việc còn lại (tính tại thời điểm kết thúc CP3)

- [ ] CP5 — chạy quality/freshness trên corrupted, nối corruption log với signal
- [ ] CP6 — `generate_corruption_report` (helper `enrich_metrics` và `METRIC_KEYS` dùng lại được)
- [ ] Đọc 1 hit + 1 miss **trên dữ liệu thật** khi R1 chạy được `phase1.py`

**Blocker:** `phase1.py` và `corruption_flow.py` vẫn còn `NotImplementedError`. Không chạy
được end-to-end thì chưa có `baseline_metrics.json` thật để đối chiếu. Toàn bộ phần R5
đã sẵn sàng nhận input.

---

## CP4 · 02:00–02:15 — Nghỉ, và dự báo signal

### 4.1. Ba dòng trước khi nghỉ

1. Bốn hàm của R5 đã xong và test được: `build_test_set`, `run_data_quality_checks`,
   `build_freshness_report`, `generate_phase1_report`. Còn `generate_corruption_report` (CP6).
2. `phase1.py` của R1 đã chạy được nhưng **truyền thẳng `evaluation.summary`**, chưa gọi
   `enrich_metrics` — chưa sửa thì report mất phần judge reliability và ví dụ hit/miss.
3. Chưa có `data/results/baseline_metrics.json`, nên chưa đọc được hit/miss trên dữ liệu thật.

### 4.2. Dự báo — làm TRƯỚC khi chạy corruption

Đọc `src/ingestion/corruption.py` để lấy tham số thật thay vì đoán:
`drop_latest` 1–2 row · `blank_summary` 2 · `inject_noise` 2–3 · `truncate_title` 1–2
(cắt còn 12 ký tự) · `stale_date` 2–3 (lùi 2190 ngày) · `duplicate_rows` 2.
Các operator **không chồng target lên nhau** (`_take` giữ một set `used`).

| Operator | Dự báo signal đổi | Check của tôi có kêu không |
|---|---|---|
| `drop_latest` | `latest_published` lùi, `min_age_days` tăng | không check nào — chỉ freshness thấy |
| `blank_summary` | `summary_chars` = 0 trên 2 row | `summary_all_usable` fail |
| `inject_noise` | `summary_chars` **tăng** | **không check nào bắt được** |
| `truncate_title` | title còn 12 ký tự | `title_min_length` warn |
| `stale_date` | `age_days` +2190 | `freshness_no_stale_rows` warn, `is_fresh` → False |
| `duplicate_rows` | 2 `paper_id` trùng | `paper_id_unique` fail |

**Dự báo ngược — cái gì KHÔNG đổi, quan trọng không kém:**

- `row_count_min` **không fail**. Số row sau corruption = `N − drop(1..2) + dup(2)`, tức là
  **N hoặc N+1** — tăng lên chứ không giảm. `duplicate_rows` che mất `drop_latest` trên
  chỉ số đếm row. Ai chỉ nhìn row count sẽ kết luận "không mất dữ liệu gì" trong khi
  paper mới nhất đã bị xoá.
- `inject_noise` không làm signal cấu trúc nào đổi. Đây là điểm phân tích trung tâm của
  phần observability: **rule-based validation không phát hiện được data poisoning.**

### 4.3. Dự báo làm lộ một lỗi hiệu chỉnh — đã sửa

Tính thử trên dataset thật (~41 row, `max_results=48`) thay vì 15 row của CP1:

| Check bản CP1 | Giá trị sau corruption | Kết quả |
|---|---|---|
| `summary_usable_ratio >= 0.90` | 40/42 = **0.952** | ✅ pass — **không kêu** |
| `freshness_stale_ratio <= 0.20` | 2/42 = **0.048** | ✅ pass — **không kêu** |

Hai ngưỡng tỉ lệ này được hiệu chỉnh trên dataset 15 row ở CP1. Trên dataset thật chúng
im lặng đúng lúc cần kêu nhất, và corruption chỉ còn **1 hard check fail** — dưới mức
Definition of Done yêu cầu ≥ 2.

**Cách sửa: thay ngưỡng tỉ lệ bằng chính bất biến mà upstream đã bảo đảm.**

| Check mới | Bất biến dựa vào |
|---|---|
| `summary_all_usable` — 0 row có `summary_chars < 40` | `cleaning.py::_apply_filters` drop mọi row dưới ngưỡng, nên dataset đã clean **phải** có 0 row như vậy |
| `freshness_no_stale_rows` — 0 row có `age_days > 180` | `source_filter` dùng `from-pub-date:{today−180}`, nên mọi paper fetch về đều trẻ hơn ngưỡng |

Đây không phải nới lỏng để corruption dễ bị bắt. Ngược lại: một dataset đã clean vi phạm
hai bất biến trên nghĩa là **có thứ gì đó đã sửa dữ liệu sau bước cleaning** — đúng định
nghĩa của thứ mà data quality check phải phát hiện. Ngưỡng tỉ lệ chỉ là phỏng đoán;
bất biến là hợp đồng.

Hai tỉ lệ cũ **không bị vứt đi** — chúng chuyển vào khối `signals` trong payload, cùng
`unusable_summaries`, `duplicate_paper_ids`, `short_titles`, `stale_rows`. Check trả lời
*"có đạt hợp đồng không"*; signals trả lời *"lệch bao nhiêu"* — cần cho bảng so sánh 3
trạng thái ở CP6, vì một check đã fail thì fail thêm nữa vẫn chỉ là fail.

`authors_present_ratio` và `categories_present_ratio` **giữ nguyên dạng tỉ lệ**: Crossref
thật sự thiếu `subject` ở nhiều paper (§2.3), nên đó là biến thiên hợp lệ của nguồn,
không phải bất biến.

### 4.4. Đối chiếu dự báo với corruption thật — 24/24 đúng

Chạy `corrupt_clean_dataframe(df, log, target_doc_ids=<từ test set>, seed=42)` thật trên
dataset 41 row:

```
[corruption] seed=42 | 41 -> 42 rows | 6 operators | rows_changed_verified=7

baseline : 41 row, passed=True,  is_fresh=True
corrupted: 42 row, passed=False, is_fresh=False
  hard fail: ['paper_id_unique', 'summary_all_usable']
  warning  : ['title_min_length', 'freshness_no_stale_rows']
```

| Dự báo | Thực tế |
|---|---|
| baseline sạch hoàn toàn | ✅ 0 fail, 0 warning, `is_fresh=True` |
| ≥ 2 hard check fail | ✅ đúng 2 |
| `latest_published` lùi | ✅ `2026-07-27` → `2026-07-23` |
| `min_age_days` tăng | ✅ `10.0` → `14.0` |
| `max_age_days` nhảy vọt | ✅ `170.0` → `2280.0` |
| row count **tăng** chứ không giảm | ✅ `41` → `42` |
| noise không bị check nào bắt | ✅ 2 row nhiễm, `summary_chars` đều > 80, `paper_id`/`title`/`published` nguyên vẹn |

Signals dịch chuyển: `unusable_summaries` 0→2 · `duplicate_paper_ids` 0→2 ·
`short_titles` 0→1 · `stale_rows` 0→2.

### 4.5. Mang gì trở lại sau giờ nghỉ

- **Test set đã khoá.** Dùng lại nguyên `data/eval/test_set.json`, tuyệt đối không để
  `REFRESH_TEST_SET` bật trong corruption flow. Tạo lại test set từ corrupted data là
  phép so sánh mất hiệu lực hoàn toàn.
- **Điểm phải kiểm ĐẦU TIÊN nếu metric không đổi ở CP5:** `corrupt_clean_dataframe` đã tự
  chặn Bẫy 1 bằng `_verify_corruption` (raise nếu số row đổi thật ≠ số log ghi), nên
  nguyên nhân nhiều khả năng nằm ở chỗ khác: doc bị corrupt không nằm trong
  `ground_truth_doc_ids`, hoặc đang query nhầm `papers-baseline`.
- **Phải so `judge_fallback_rate` giữa baseline và corrupted.** Nếu baseline chạy được LLM
  judge còn corrupted bị rate limit, phần chênh lệch `judge_accuracy` đến từ judge chứ
  không từ corruption. Không kiểm điều này thì kết luận ở CP6 sai mà vẫn trông hợp lý.

---

## CP5 · 02:15–03:15 — Đo impact trên dữ liệu thật

R2 đã fetch đủ 48 record và R1 đã chạy `phase1.py`, nên CP5 chạy được trên dữ liệu thật
mà không cần chờ `corruption_flow.py`: gọi thẳng `corrupt_clean_dataframe` rồi cho quality
và freshness chạy trên kết quả.

`run_date` lấy từ `run_context.json` (`2026-08-06T09:25:13Z`), **không** dùng
`datetime.now()` — nếu không `age_days` lệch và mọi so sánh mất công bằng (Bẫy 4).

### 5.1. Nối corruption → signal

Thêm `summarize_corruption_impact()` vào `reporting.py`: ánh xạ từng operator trong
`corruption_log.json` sang check/signal thật sự đổi, kèm mối đe dọa mà nó mô phỏng.
Hàm trả về **cả hai chiều** — operator nào bị bắt, và operator nào **không**.

```
detection_rate = 0.8333   (5/6 operator bị bắt)
row 48 -> 49              rows_changed_verified=7

operator          n   bắt?     bằng gì
drop_latest       1   có       latest_published, min_age_days
blank_summary     2   có       summary_all_usable, unusable_summaries
inject_noise      2   KHÔNG    (không gì)
truncate_title    1   có       title_min_length, short_titles
stale_date        2   có       freshness_no_stale_rows, stale_rows, is_fresh, max_age_days, oldest_published
duplicate_rows    2   có       paper_id_unique, duplicate_paper_ids
```

Baseline: 48 row, pass mọi hard check. Corrupted: 49 row, **2 hard fail**
(`paper_id_unique`, `summary_all_usable`) + 3 warning. Đạt Definition of Done.

### 5.2. Kết luận trung tâm — `inject_noise` không signal nào bắt được

`detection_rate = 0.8333` chứ không phải 1.0, và **con số đó là kết quả đúng, không phải
thiếu sót**. `inject_noise` chèn payload prompt-injection vào `summary`:

- `summary_chars` **tăng** chứ không giảm → `summary_all_usable` vẫn pass
- `paper_id`, `title`, `published` nguyên vẹn → không check cấu trúc nào động đến
- `published_iso_format`, `paper_id_unique`, `title_min_length` đều pass

Không một schema check nào có thể thấy nó. Data poisoning chỉ lộ qua RAG metric khi agent
trả lời theo nội dung đã bị đầu độc. Đây là ranh giới giữa **monitoring** (kiểm tập điều
kiện đã biết) và **observability** (đủ tín hiệu để điều tra lỗi chưa biết trước) —
rule-based validation không đủ, cần semantic monitoring.

### 5.3. Signal KHÔNG đổi — tránh kết luận quá mức

| Signal | Baseline → Corrupted | Vì sao không đổi |
|---|---|---|
| `row_count_min` | pass → pass | 48 → **49**, tăng lên: `duplicate_rows` (+2) che `drop_latest` (−1) |
| `authors_present_ratio` | 1.0 → 1.0 | không operator nào động vào `authors` |
| `categories_present_ratio` | 0.0 → 0.0 | đã bằng 0 từ baseline, không thể giảm thêm |
| `invalid_published` | 0 → 0 | `stale_date` vẫn ghi ISO hợp lệ, chỉ lùi 6 năm |

Dòng đầu là cái bẫy nguy hiểm nhất: **số row tăng sau khi mất dữ liệu.** Ai chỉ nhìn
row count sẽ kết luận "không mất gì" trong khi paper mới nhất đã bị xoá.

Và một chiều ngược đáng chú ý: `future_published_rows` đi **1 → 0**. `drop_latest` xoá
đúng paper có ngày tương lai (nó là "mới nhất" theo `published`), nên corruption vô tình
*sửa* một defect. Không phải mọi thay đổi signal đều theo hướng xấu — thêm một lý do
không được đếm số check fail rồi kết luận.

### 5.4. Phát hiện mới trên dữ liệu thật — ngày xuất bản trong TƯƠNG LAI

Baseline có `min_age_days = **−117**`: một paper ghi `published = 2026-12-01` trong khi
`run_date = 2026-08-06`. Crossref trả về issue date của số báo sắp phát hành.

Không check nào bắt được: `published_iso_format` pass vì vẫn đúng `YYYY-MM-DD`,
`freshness_no_stale_rows` chỉ chặn đầu trên. Freshness report in ra `age_days nhỏ nhất
= −117` kèm kết luận **"✅ tươi"** — vô nghĩa với người đọc.

Tác động thật: tầng *"2 paper mới nhất"* của `build_test_set` chọn đúng paper chưa xuất
bản này. 1/48 row, và nó **nằm trong test set**.

Đã thêm check `no_future_published` (mức **warn**, vì đây là hành vi hợp lệ của nguồn
chứ không phải corruption) và signal `future_published_rows` / `future_rows`.

### 5.5. Kết quả CP3 trên dữ liệu thật — và một blocker lớn của cả nhóm

`baseline_metrics.json` thật:

```json
{"samples": 14, "retrieval_hit_rate": 1.0, "mean_token_f1": 1.0,
 "judge_accuracy": 1.0, "mean_judge_score": 5}
```

Chạy `summarize_judge_reliability` trên `baseline_answers.json`:

```
judge_fallback_count: 14
judge_fallback_rate : 1.0
judge_mode          : heuristic
```

**Bẫy 3 đã xảy ra thật.** Toàn bộ 14 sample rơi về heuristic — `judge_accuracy = 1.0` và
`mean_judge_score = 5` trong artifact **không phải LLM-as-a-judge**. Cộng với
`agent_demo_answers.json` báo `"Agent unavailable: RuntimeError"`, cả hai chỉ về cùng một
nguyên nhân.

Chẩn đoán bằng một lần gọi API:

```
provider: gemini | model: gemini-2.5-flash | key hợp lệ
invoke FAIL: 404 NOT_FOUND
  "This model models/gemini-2.5-flash is no longer available to new users."
```

**API key không sai — tên model đã bị Google gỡ.** Thử 4 ứng viên theo đúng cách
`metrics.py` gọi (`with_structured_output(JudgeVerdict)`):

| Model | Kết quả |
|---|---|
| `gemini-flash-latest` | ✅ dùng được, tôn trọng `temperature=0.0` |
| `gemini-3.6-flash` | ✅ dùng được, nhưng **bỏ qua** `temperature` → judge kém tái lập |
| `gemini-3.5-flash` | ✅ dùng được |
| `gemini-2.0-flash` | ❌ 429 hết quota |

Đề xuất `LLM_MODEL=gemini-flash-latest` trong `.env`. Sửa xong thì: Rubric mục 5 (Agent,
10 điểm) chạy lại được, và judge trở thành LLM thật thay vì heuristic.

### 5.6. Baseline hoàn hảo — đọc con số cho đúng

`retrieval_hit_rate = 1.0`, `mean_token_f1 = 1.0`, mọi document ở **hạng 1/4**, không
sample nào có `token_f1 < 1.0`. Không có hit/miss nào để so sánh vì **không tồn tại miss
ở baseline** — `summarize_retrieval_examples` trả về đúng một `best_hit`, và report ghi
"không có sample nào" cho cả hai loại miss. Đó là kết quả trung thực, không phải thiếu dữ liệu.

Nhưng phải đọc cho đúng: con số 1.0 này **không chứng minh RAG tốt**. Nó là hệ quả của
thiết kế — `qa.py` lấy thẳng một trường metadata, ground truth của R5 chính là trường đó,
và exact-title lookup luôn tìm ra đúng document. Baseline hoàn hảo là **điều kiện lý
tưởng cho thí nghiệm corruption**: mọi sụt giảm ở CP5/CP6 đều quy được về corruption chứ
không lẫn với nhiễu nền.

### 5.7. Việc còn lại

- [ ] CP6 — `generate_corruption_report` (dùng `summarize_corruption_impact` + `METRIC_KEYS`)
- [ ] Chạy lại `phase1.py` sau khi sửa `LLM_MODEL`, để có judge thật và agent chạy
- [ ] Đọc lại hit/miss sau corruption — lúc đó mới có miss để phân tích

**Gửi R1 — ba việc, theo thứ tự ưu tiên:**

1. Sửa `.env`: `LLM_MODEL=gemini-flash-latest`. Đang mất Rubric mục 5 và judge là giả.
2. `phase1.py` dòng 196: gọi `enrich_metrics(evaluation.summary, evaluation.answers)`.
   Report hiện in *"Không đo được"* ở mục 2.1–2.3, tức mất pass criteria CP3.
3. `corruption_flow.py` dùng `quality_report_name(state)` và
   `freshness_report_path(settings, state)` thay vì tự đặt tên file.
