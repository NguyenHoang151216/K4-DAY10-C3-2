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
| 7 | `summary_usable_ratio` | `>= 0.90` với `summary_chars >= 40` |

> Ngưỡng `MIN_SUMMARY_CHARS` để **40**, không phải 80. Lý do: `cleaning.py` hạ ngưỡng
> xuống `SUMMARY_MIN_CHARS_RELAXED = 40` khi số row không đủ `MIN_ROWS = 24`. Nếu quality
> check giữ 80 trong khi cleaning đã dùng 40, `summary_usable_ratio` sẽ fail trên một
> dataset hợp lệ và cả nhóm đi tìm lỗi ở nhầm chỗ.

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
- ~~**`max_results = 24`**~~ → R1 đã nâng lên **48** ở `config.py`, và `run_context.json`
  đã được ghi. Rủi ro `row_count_min >= 10` fail ở baseline giảm đáng kể, nhưng vẫn
  theo dõi khi R2 fetch dataset đầy đủ.
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

### 3.6. Việc còn lại

- [ ] CP5 — chạy quality/freshness trên corrupted, nối corruption log với signal
- [ ] CP6 — `generate_corruption_report` (helper `enrich_metrics` và `METRIC_KEYS` dùng lại được)
- [ ] Đọc 1 hit + 1 miss **trên dữ liệu thật** khi R1 chạy được `phase1.py`

**Blocker:** `phase1.py` và `corruption_flow.py` vẫn còn `NotImplementedError`. Không chạy
được end-to-end thì chưa có `baseline_metrics.json` thật để đối chiếu. Toàn bộ phần R5
đã sẵn sàng nhận input.
