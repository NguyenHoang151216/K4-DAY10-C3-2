# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Kỳ Anh |
| MSSV | 2A202601558 |
| Khóa/Lớp | K4 |
| Tên nhóm | **C3_1** |
| Vai trò chính | Evaluation & Observability Owner |
| Repository | https://github.com/NguyenHoang151216/K4_Day10_Data-Pipeline-Data-Observability |
| Ngày hoàn thành | 2026-08-06 |

> **Ghi chú về cách đánh số vai trò.** Hai tài liệu đánh số khác nhau cho cùng một phạm vi
> công việc: `report/README.md` §5 gọi người sở hữu `quality.py` + `reporting.py` là
> **Thành viên 3 — Observability owner**, còn `PHAN-CONG-NHOM-5.md` của nhóm gọi là **R5 —
> Evaluation & Observability Owner** và gộp thêm `testset.py`. Báo cáo này dùng số **R3**
> theo cách đánh số của BTC trong tên file, nhưng phạm vi thực tế là bản R5 của nhóm:
> **3 file, 6 hàm chính**. Phần 2 liệt kê chính xác.

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Evaluation set | `src/evaluation/testset.py` → `build_test_set` | cleaned DataFrame (16 cột) từ R3 | `data/eval/test_set.json` — 14 câu trên 8 paper | Hoàn thành |
| Data quality checks | `src/observability/quality.py` → `run_data_quality_checks` | cleaned/corrupted/repaired DataFrame | `data/quality/{baseline,corrupted,repaired}_quality.json` — 7 hard + 6 warning | Hoàn thành |
| Freshness monitoring | `src/observability/quality.py` → `build_freshness_report` | DataFrame + `settings.freshness_threshold_days` | `data/quality/freshness_report{,_corrupted,_repaired}.json` | Hoàn thành |
| Chuẩn hoá tên artifact | `src/observability/quality.py` → `quality_report_name`, `freshness_report_path` | tên trạng thái | đường dẫn/tên chuẩn cho 3 trạng thái | Hoàn thành |
| Báo cáo baseline | `src/observability/reporting.py` → `generate_phase1_report` | source summary, metrics, quality, freshness | `data/reports/phase1_report.md` | Hoàn thành |
| Đo độ tin cậy metric | `src/observability/reporting.py` → `enrich_metrics`, `summarize_judge_reliability`, `summarize_by_question_type`, `summarize_retrieval_examples` | `bundle.answers` | `judge_fallback_rate`, breakdown theo `question_type`, ví dụ hit/miss | Hoàn thành, **pipeline chưa gọi** |
| Nối corruption → signal | `src/observability/reporting.py` → `summarize_corruption_impact` | `corruption_log.json` + 2 quality + 2 freshness | `data/quality/corruption_impact.json` | Hoàn thành |
| Báo cáo so sánh 3 trạng thái | `src/observability/reporting.py` → `generate_corruption_report` | metrics/quality/freshness của 3 trạng thái | `data/reports/corruption_report.md` | **Chưa hoàn thành** |

Không nhận ownership cho `crossref.py`, `cleaning.py`, `corruption.py`, `phase1.py`,
`corruption_flow.py` và toàn bộ `src/retrieval/`.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Chẩn đoán vì sao judge LLM và agent đều thất bại | R1 (`phase1.py`), R4 (agent) | Xác định 2 nguyên nhân gốc: model `gemini-2.5-flash` đã bị gỡ (404), và free tier giới hạn 20 request/ngày/model (429). Chi tiết ở mục 6. |
| Chỉ ra khoảng trống tích hợp trong `phase1.py` | R1 | `phase1.py:196` truyền `evaluation.summary` chưa enrich → report in *"Không đo được"* ở mục 2.1–2.3. Đã cung cấp `enrich_metrics()` và đoạn code cần thêm, không tự sửa file của R1. |
| Chốt contract kiểu dữ liệu cột clean | R3 (`cleaning.py`) | Yêu cầu `published` là chuỗi ISO (không `NaN`), `age_days`/`summary_chars` là số — điều kiện để quality check và freshness đọc đúng. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Test set cố định, deterministic | `testset.py`, `data/eval/test_set.json` | 14 câu / 8 paper: 8 summary, 3 authors, 3 date, 0 categories | Chạy lại 2 lần và xáo trộn thứ tự row đầu vào đều cho kết quả byte-identical |
| Quality checks baseline | `data/quality/baseline_quality.json` | 48 row, pass toàn bộ 7 hard check, 2 warning | `passed: true`, `failed_checks: []` |
| Quality checks corrupted | `data/quality/corrupted_quality.json` | 49 row, **2 hard fail**, 3 warning | `failed_checks: ["paper_id_unique", "summary_all_usable"]` |
| Freshness 2 trạng thái | `data/quality/freshness_report.json`, `freshness_report_corrupted.json` | `is_fresh` chuyển `true → false` | `stale_rows 0 → 2`, `max_age_days 175 → 2318` |
| Báo cáo baseline | `data/reports/phase1_report.md` | 9 mục, mọi số đọc thẳng từ dict truyền vào | Đối chiếu tay với `baseline_metrics.json` và `baseline_quality.json` |
| Đo impact corruption | `data/quality/corruption_impact.json` | `detection_rate = 0.8333`, `undetected_operators = ["inject_noise"]` | 6 operator trong `corruption_log.json` đều được quy về signal cụ thể |

### Một output cụ thể

`data/quality/corruption_impact.json` ánh xạ từng operator trong `corruption_log.json`
sang đúng những check/signal đã thay đổi:

```
detection_rate = 0.8333   (5/6 operator bị bắt)   |   row 48 → 49

operator          n   bắt?     bằng gì
drop_latest       1   có       latest_published, min_age_days
blank_summary     2   có       summary_all_usable, unusable_summaries
inject_noise      2   KHÔNG    (không gì)
truncate_title    1   có       title_min_length, short_titles
stale_date        2   có       freshness_no_stale_rows, stale_rows, is_fresh, max_age_days, oldest_published
duplicate_rows    2   có       paper_id_unique, duplicate_paper_ids
```

Con số `0.8333` là kết quả **đúng**, không phải thiếu sót — xem mục 8.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Ba vấn đề nối tiếp nhau:

1. **Đo cái gì.** Cần một bộ câu hỏi cố định để so sánh công bằng ba trạng thái dataset.
   Nếu test set thay đổi giữa các trạng thái thì mọi chênh lệch metric đều vô nghĩa.
2. **Phát hiện dữ liệu hỏng.** Cần tập tín hiệu đủ nhạy để mỗi dạng lỗi dữ liệu làm ít
   nhất một signal thay đổi — và đủ trung thực để nói rõ dạng nào **không** phát hiện được.
3. **Báo cáo không nói dối.** Metric có thể trông đẹp trong khi thành phần sinh ra nó đã
   chết âm thầm. Báo cáo phải tự khai báo độ tin cậy của chính nó.

### Cách triển khai

**Test set — chọn theo phân tầng, không random.** 8 paper được chọn từ 4 tầng: 2 mới nhất,
2 cũ nhất, 2 abstract dài nhất, 2 ở giữa timeline. Mọi khoá sort đều có tie-break bằng
`paper_id` để kết quả ổn định kể cả khi giá trị chính trùng nhau. Khi 4 tầng chồng lấn
(paper mới nhất cũng có thể là paper abstract dài nhất), có bước bù thêm cho đủ 8 —
không bù thì số câu hỏi tụt xuống mà không có cảnh báo nào.

Ground truth phải khớp **đúng** trường metadata mà `retrieval/qa.py::_extract_answer` trả
về, vì hàm đó nhận diện intent bằng chuỗi con trong câu hỏi rồi lấy thẳng một trường:

| Câu hỏi chứa | `_extract_answer` trả về | Ground truth |
| --- | --- | --- |
| `who authored` | `authors_joined` | `row["authors_joined"]` |
| `when was` | `published` | `row["published"]` |
| `what categories` | `categories_joined` | `row["categories_joined"]` |
| *(còn lại)* | `first_sentence(summary)` | `first_sentence(row["summary"])` |

Hai nhóm paper bị loại khỏi test set: title chứa dấu `'` (regex `r"'([^']+)'"` của `qa.py`
cắt sai → hỏng exact lookup) và **title chứa cụm từ khoá intent**. Nhóm thứ hai không có
trong tài liệu bẫy của nhóm: title được nhúng vào mọi câu hỏi, nên một paper tên
*"When Was BERT Actually Trained"* sẽ khiến câu summary chứa `when was` và bị bẻ nhánh
sang trả về `published`.

**Quality checks — khẳng định bất biến, không đặt ngưỡng tỉ lệ.** 7 hard + 6 warning.
Nguyên tắc thiết kế: mỗi corruption operator phải làm ít nhất một signal đổi. Ngoài
`checks` (pass/fail), payload còn có khối `signals` chứa giá trị liên tục — check trả lời
*"có đạt hợp đồng không"*, signals trả lời *"lệch bao nhiêu"*, cần cho bảng so sánh 3
trạng thái.

**Freshness — `is_fresh` gồm hai điều kiện.** `stale_rows == 0` bắt operator lùi ngày;
`min_age_days <= threshold` bắt operator xoá paper mới nhất. Chỉ một điều kiện thì mất
một nửa khả năng phát hiện.

**Báo cáo tự khai báo độ tin cậy.** `metrics.py::_judge_answer` tạo client LLM mới cho
từng sample và bọc `except Exception` trần, nên judge chết vì rate limit mà pipeline vẫn
xanh. `summarize_judge_reliability` đếm sample có `judge.reasoning` bắt đầu bằng
`"Fallback heuristic judge"` rồi phân loại `judge_mode` thành `llm`/`mixed`/`heuristic`.
Khi `heuristic`, report tự chèn cảnh báo rằng kết quả **không phải LLM-as-a-judge**.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | cleaned DataFrame 16 cột (`paper_id`, `title`, `summary`, `published`, `authors_joined`, `categories_joined`, `summary_chars`, `age_days`, `text_for_embedding`, …); `Settings`; `bundle.answers` từ `evaluate_pipeline` |
| Output | `test_set.json` (5 trường contract); quality JSON (`checks`, `signals`, `failed_checks`, `passed`); freshness JSON (`latest_published`, `stale_rows`, `future_rows`, `is_fresh`, …); `phase1_report.md` |
| Module phụ thuộc | `ingestion/cleaning.py` (schema), `core/config.py` (paths, ngưỡng), `core/utils.py` (`first_sentence`, `write_json`, `write_text`) |
| Module sử dụng output | `evaluation/metrics.py` (đọc test set), `pipelines/phase1.py`, `pipelines/corruption_flow.py` |
| Điều kiện lỗi cần xử lý | thiếu cột → báo thành check fail thay vì `KeyError`; `< 8` document → raise có thông điệp; ground truth rỗng → bỏ câu hỏi thay vì tạo sample `token_f1 = 0`; kiểu numpy → ép về scalar Python vì `json.dumps` không serialize được |

### Cách xác minh

```bash
# moi lenh chay bang .venv\Scripts\python.exe vi uv khong co tren may nay
python script/run_phase1.py

# doi chieu artifact
cat data/results/baseline_metrics.json
cat data/quality/baseline_quality.json
cat data/quality/corrupted_quality.json
cat data/quality/corruption_impact.json
```

- **Kết quả mong đợi:** baseline pass toàn bộ hard check; corrupted làm ≥ 2 hard check fail;
  mọi số trong `phase1_report.md` khớp JSON tương ứng.
- **Kết quả thực tế:** baseline 48 row `passed: true`; corrupted 49 row `failed_checks:
  ["paper_id_unique", "summary_all_usable"]`; `is_fresh` `true → false`. Đã đối chiếu tay
  `samples`, `retrieval_hit_rate`, `row_count`, `latest_published` giữa `.md` và `.json`.
- **Artifact/log:** `data/quality/`, `data/results/`, `data/reports/phase1_report.md`.
  Không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Bộ quality check ban đầu dùng ngưỡng tỉ lệ (`summary_usable_ratio >= 0.90`,
  `freshness_stale_ratio <= 0.20`), hiệu chỉnh trên dataset thử 15 row. Trước khi chạy
  corruption thật, tôi tính lại các ngưỡng này trên dataset thật.

- **Các phương án đã cân nhắc:**
  1. Giữ ngưỡng tỉ lệ, chấp nhận rằng corruption nhỏ không bị bắt trên dataset lớn.
  2. Siết ngưỡng tỉ lệ lên (ví dụ `>= 0.96`) cho nhạy hơn.
  3. Thay ngưỡng tỉ lệ bằng chính bất biến mà bước upstream đã bảo đảm.

- **Phương án đã chọn:** phương án 3.
  - `summary_usable_ratio >= 0.90` → `summary_all_usable`: **0 row** có `summary_chars`
    dưới ngưỡng cleaning.
  - `freshness_stale_ratio <= 0.20` → `freshness_no_stale_rows`: **0 row** có
    `age_days > 180`.

- **Lý do:** Trên 48 row, blank 2 summary cho tỉ lệ 40/42 = **0.952**, vẫn qua ngưỡng 0.90;
  2 row stale cho 2/42 = **0.048**, vẫn qua ngưỡng 0.20. Cả hai check im lặng đúng lúc cần
  kêu nhất, và corruption chỉ còn 1 hard fail. Phương án 2 chỉ đẩy vấn đề sang chỗ khác:
  ngưỡng nhạy hơn thì lại báo động giả khi nguồn biến động hợp lệ. Phương án 3 dựa trên
  điều đã đúng theo thiết kế: `cleaning.py::_apply_filters` drop mọi row có summary dưới
  ngưỡng, và `source_filter = from-pub-date:{today−180}` khiến mọi paper fetch về đều trẻ
  hơn ngưỡng. Một dataset đã clean vi phạm hai điều này nghĩa là **có thứ gì đó sửa dữ
  liệu sau bước cleaning** — đúng thứ mà data quality check sinh ra để phát hiện. Ngưỡng
  tỉ lệ là phỏng đoán; bất biến là hợp đồng.

  Hai tỉ lệ cũ không bị vứt đi mà chuyển vào khối `signals`, vẫn dùng được để so sánh mức
  độ lệch. `authors_present_ratio` và `categories_present_ratio` **giữ nguyên dạng tỉ lệ**,
  vì Crossref thật sự thiếu `subject` ở nhiều paper — đó là biến thiên hợp lệ của nguồn,
  không phải bất biến.

- **Bằng chứng quyết định phù hợp:** sau khi đổi, chạy `corrupt_clean_dataframe` thật
  (seed 42) trên 48 row cho **2 hard fail + 3 warning**, đạt yêu cầu "corruption làm ≥ 2
  quality check fail"; baseline vẫn `passed: true`, tức ngưỡng mới không tạo báo động giả.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `data/results/baseline_metrics.json` báo
  `judge_accuracy: 1.0` và `mean_judge_score: 5`, trông như judge LLM chấm điểm hoàn hảo.
  Nhưng `agent_demo_answers.json` lại ghi `"Agent unavailable: RuntimeError"`. Hai artifact
  mâu thuẫn nhau.

- **Lệnh hoặc bước tái hiện:** chạy `summarize_judge_reliability()` trên
  `data/results/baseline_answers.json`:

  ```
  judge_fallback_count: 14 / 14
  judge_fallback_rate : 1.0
  judge_mode          : heuristic
  ```

  Toàn bộ 14 sample có `judge.reasoning` bắt đầu bằng `"Fallback heuristic judge"`.

- **Nguyên nhân gốc:** hai nguyên nhân chồng lên nhau, cùng bị `except Exception` trong
  `_judge_answer` che đi.

  1. `LLM_MODEL=gemini-2.5-flash` đã bị nhà cung cấp gỡ. Gọi thử một lần trả về:
     `404 NOT_FOUND — "This model models/gemini-2.5-flash is no longer available to new users."`
     API key hoàn toàn hợp lệ; chỉ tên model sai.
  2. Sau khi nhóm đổi sang `gemini-3.6-flash`, artifact agent ghi lỗi mới:
     `429 RESOURCE_EXHAUSTED — quota limit: 20, model: gemini-3.6-flash`.
     Free tier cho **20 request/ngày/model**, trong khi bài lab cần 14 câu × 3 trạng thái
     = **42 lần gọi judge**, chưa kể agent.

- **Cách xử lý:** phần thuộc phạm vi của tôi là làm cho lỗi **không còn im lặng**, vì
  `metrics.py` là file dùng chung không được sửa. Đã thêm `summarize_judge_reliability`
  và cho `generate_phase1_report` tự chèn cảnh báo khi `judge_mode == "heuristic"`:

  > ⚠️ Toàn bộ sample rơi về heuristic judge. `judge_accuracy` và `mean_judge_score`
  > **không phải LLM-as-a-judge** — chúng chỉ là ngưỡng đặt trên `token_f1`.

  Đã thử 4 model theo đúng cách `metrics.py` gọi (`with_structured_output(JudgeVerdict)`):
  `gemini-flash-latest` ✅ (và tôn trọng `temperature=0.0`), `gemini-3.5-flash` ✅,
  `gemini-3.6-flash` ✅ nhưng bỏ qua `temperature` → judge kém tái lập,
  `gemini-2.0-flash` ❌ 429.

- **Cách xác minh sau khi sửa:** với `judge_mode = "heuristic"`, report sinh ra chứa đúng
  cảnh báo trên; với `judge_mode = "llm"` thì không. Đã kiểm cả hai nhánh.

- **Điều học được:** **metric phải tự khai báo độ tin cậy của chính nó.** Một `try/except`
  quá rộng biến lỗi hạ tầng thành số liệu đẹp, và không có cách nào phân biệt "judge chấm
  đúng" với "judge không chạy" nếu chỉ nhìn file metrics. Dấu vết duy nhất còn lại nằm
  trong chuỗi `reasoning` của từng sample.

### Phần chưa xử lý xong

- **Phạm vi bị ảnh hưởng:** `judge_accuracy` và `mean_judge_score` ở cả ba trạng thái;
  Rubric mục 5 (Agent).
- **Những gì đã loại trừ:** API key sai (đã xác minh hợp lệ); thiếu credential
  (`require_llm_credentials` pass); lỗi `build_llm` (khởi tạo thành công); tên model không
  tồn tại (đã liệt kê 31 model khả dụng qua REST).
- **Bước tiếp theo:** quota free tier 20/ngày/model không đủ cho 42 lần gọi, nên phương án
  thực tế là **chấp nhận heuristic judge và ghi rõ trong báo cáo** — điều mà `judge_mode`
  đã tự động làm. Nếu muốn judge thật, cần tài khoản trả phí hoặc chia nhỏ số lần gọi
  theo ngày. Không được im lặng gọi kết quả hiện tại là LLM-as-a-judge.

## 7. Hiểu biết về luồng end-to-end

**1. Dữ liệu đi từ Crossref đến vector index như thế nào?**
`fetch_source_records` gọi Crossref REST với query và filter `from-pub-date:…,has-abstract:true`,
lưu **raw response trước khi parse** vào `data/raw/crossref_response.json`, rồi parse thành
`PaperRecord` và lưu `crossref_records.json`. Raw snapshot bất biến này là điều kiện cần
để repair — không có nó thì chỉ còn cách sửa tay, tức che lỗi chứ không sửa lỗi.
`build_clean_dataframe` chuẩn hoá text, parse ngày về chuỗi ISO, dedupe theo `paper_id`,
tính `age_days` và ghép `text_for_embedding` từ 5 nhãn cố định. `LocalEmbeddingIndex.build`
đọc 9 cột từ DataFrame, embed `text_for_embedding` bằng MiniLM-L6-v2 và nạp vào Chroma
collection `papers-baseline`, đồng thời ghi manifest sang `data/embeddings/`.

**2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
Mỗi sample có `ground_truth` (câu trả lời đúng) và `ground_truth_doc_ids` (paper chứa câu
trả lời đó). `evaluate_pipeline` gọi `answer_question`, rồi tính hai thứ độc lập nhau:
`retrieval_hit` = có `paper_id` nào trong top-k nằm trong `ground_truth_doc_ids` không, và
`token_f1` = độ trùng token giữa câu trả lời và ground truth. Tách hai chỉ số này là quan
trọng vì chúng chỉ ra hai chỗ hỏng khác nhau — lấy nhầm tài liệu, hay lấy đúng tài liệu
nhưng trả lời sai.

**3. Quality checks khác freshness monitoring ở điểm nào?**
Quality check hỏi *"dữ liệu có đúng hợp đồng không"* — đủ cột, `paper_id` unique, summary
dùng được, title không rỗng. Nó không quan tâm dữ liệu cũ hay mới. Freshness hỏi *"dữ liệu
có còn kịp thời không"* — paper mới nhất là bao giờ, bao nhiêu row quá hạn, phân bố
`age_days` ra sao. Một dataset có thể pass sạch mọi quality check mà vẫn vô dụng vì toàn
tài liệu 6 năm trước; ngược lại một dataset rất mới vẫn có thể hỏng schema. Trong lab này
sự khác biệt đó hiện rõ: operator `drop_latest` **không làm quality check nào fail** —
số row thậm chí còn tăng — mà chỉ lộ qua `latest_published` và `min_age_days` của freshness.

**4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
Đây là thí nghiệm có đối chứng: chỉ được đổi **một** biến là trạng thái dataset, mọi thứ
còn lại phải giữ nguyên — test set, embedding model, `top_k`, evaluator. Nếu test set được
tạo lại từ corrupted data thì câu hỏi và ground truth cũng bị corrupt theo, và chênh lệch
metric không còn quy về corruption được nữa. Vì vậy `build_test_set` chọn deterministic và
pipeline chỉ tạo lại test set khi `REFRESH_TEST_SET` được bật.

**5. Repair được xem là thành công dựa trên artifact và metric nào?**
Ba tầng bằng chứng, phải đạt cả ba: (a) `repair_validation.json` cho
`core_content_hash_equal: true`, tức nội dung cột lõi của repaired trùng baseline;
(b) repaired pass lại các hard check đã fail ở corrupted và `is_fresh` trở lại `true`;
(c) `repaired_metrics.json` phục hồi về mức baseline trên cùng test set. Nếu chỉ metric
phục hồi mà quality signal chưa, hoặc ngược lại, thì phải ghi rõ là **phục hồi chưa hoàn
toàn** thay vì công bố thành công.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0 | *chưa chạy* | *chưa chạy* | Baseline hoàn hảo do thiết kế, không phải do RAG tốt — xem dưới |
| `mean_token_f1` | 1.0 | *chưa chạy* | *chưa chạy* | Mọi sample bằng 1.0, không có sample nào dưới 1.0 |
| `judge_accuracy` | 1.0 | *chưa chạy* | *chưa chạy* | **Không phải LLM-as-a-judge** — `judge_fallback_rate = 1.0` |
| `mean_judge_score` | 5 | *chưa chạy* | *chưa chạy* | Giá trị heuristic suy ra từ `token_f1`, không phải điểm LLM chấm |
| Quality checks | 7 hard pass, 2 warning | **2 hard fail**, 3 warning | *chưa chạy* | `paper_id_unique`, `summary_all_usable` |
| Freshness status | `is_fresh: true` | `is_fresh: false` | *chưa chạy* | `stale_rows 0 → 2`, `max_age_days 175 → 2318` |

**Cột Repaired chưa có số liệu.** `src/pipelines/corruption_flow.py` vẫn còn
`NotImplementedError`, nên chưa chạy được bước repair và re-evaluate. Số liệu cột
Corrupted ở hai dòng cuối lấy từ lần chạy `corrupt_clean_dataframe` trực tiếp (seed 42)
chứ chưa qua `corruption_flow.py`; bốn dòng metric đầu cần re-evaluate qua Chroma nên
chưa có. Không điền số ước lượng vào các ô này.

### Kết luận từ số liệu

**Chuỗi 1 — corruption → signal → (dự kiến) metric.**
`blank_summary` xoá trắng `summary` của 2 paper → `cleaning.py` bảo đảm mọi row có
`summary_chars >= 40`, nên `summary_all_usable` chuyển từ pass sang **fail**
(`unusable_summaries: 0 → 2`) và `text_for_embedding` của 2 paper đó mất phần Abstract →
dự kiến `mean_token_f1` giảm ở các câu `summary`, vì ground truth là
`first_sentence(summary)` nhưng metadata không còn nội dung để trả về.

**Chuỗi 2 — repair → phục hồi.** Chưa chạy được. Cơ chế đã sẵn sàng: raw snapshot 48
record còn nguyên, `run_context.json` đã ghim `run_date` nên replay cleaning cho ra
`age_days` giống hệt baseline, và `core_content_hash` của `cleaning.py` cho phép chứng
minh repaired trùng baseline. Chưa có artifact thì chưa kết luận.

**Corruption nào ảnh hưởng rõ nhất?**
Xét theo số signal dịch chuyển, `stale_date` mạnh nhất: nó làm đổi 5 signal cùng lúc
(`freshness_no_stale_rows`, `stale_rows`, `is_fresh`, `max_age_days`, `oldest_published`),
đẩy `max_age_days` từ 175 lên **2318** ngày. Nhưng xét theo mức nguy hiểm thực tế thì
ngược lại — xem phần dưới.

**Kết quả nào khác với kỳ vọng ban đầu?**

*Thứ nhất: số row TĂNG sau khi mất dữ liệu.* Tôi dự đoán `drop_latest` sẽ làm giảm row
count. Thực tế 48 → **49**, vì `duplicate_rows` thêm 2 row trong khi `drop_latest` chỉ xoá
1. Không một quality check nào phản ứng. Ai chỉ nhìn row count sẽ kết luận "không mất dữ
liệu gì" trong khi paper mới nhất đã biến mất. Chỉ freshness thấy được:
`latest_published 2026-12-01 → 2026-08-01`, `min_age_days −117 → 5`.

*Thứ hai: `inject_noise` không bị bắt, và đó là kết quả đúng.* `detection_rate = 0.8333`
chứ không phải 1.0. Payload prompt-injection được **nối thêm** vào `summary`, nên
`summary_chars` tăng chứ không giảm; `paper_id`, `title`, `published` nguyên vẹn. Không
một schema check nào có thể thấy nó. Đây là ranh giới giữa **monitoring** (kiểm tập điều
kiện đã biết) và **observability** (đủ tín hiệu để điều tra cả lỗi chưa biết trước):
data poisoning chỉ lộ ra khi agent trả lời theo nội dung đã bị đầu độc, tức qua RAG metric,
không qua rule-based validation.

*Thứ ba: corruption vô tình sửa một defect.* `future_published_rows` đi **1 → 0**. Dữ liệu
Crossref thật có 1 paper ghi `published = 2026-12-01` trong khi `run_date = 2026-08-06` —
ngày xuất bản trong tương lai, khiến `min_age_days = −117` và freshness report in "age_days
nhỏ nhất = −117" kèm kết luận "tươi", vô nghĩa với người đọc. `drop_latest` xoá đúng paper
đó vì nó là "mới nhất" theo `published`. Tôi đã thêm check `no_future_published` (mức
warning, vì đây là hành vi hợp lệ của nguồn chứ không phải corruption). Bài học: không được
đếm số check fail rồi kết luận — chiều thay đổi cũng quan trọng.

*Thứ tư: baseline hoàn hảo tuyệt đối.* `retrieval_hit_rate = 1.0`, `mean_token_f1 = 1.0`,
mọi document ở hạng 1/4. Con số này **không chứng minh RAG tốt**. Nó là hệ quả thiết kế:
`qa.py` lấy thẳng một trường metadata, ground truth của tôi chính là trường đó, và
exact-title lookup luôn tìm ra đúng document. Đọc theo hướng tích cực thì đây là **điều
kiện lý tưởng cho thí nghiệm**: baseline không có nhiễu nền, nên mọi sụt giảm sau
corruption đều quy được về corruption.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về data pipeline:** raw snapshot bất biến và `run_date` được ghim là hai thứ quyết
   định khả năng repair. Nếu `age_days` được tính lại bằng `datetime.now()` ở lần chạy sau,
   repaired sẽ khác baseline dù logic hoàn toàn đúng, và phép so hash luôn fail. Điều này
   khiến `run_context.json` không phải tiện ích mà là điều kiện đúng đắn của thí nghiệm.

2. **Về data quality/observability:** ngưỡng tỉ lệ là phỏng đoán, bất biến là hợp đồng.
   Ngưỡng `>= 0.90` hiệu chỉnh trên 15 row im lặng hoàn toàn trên 48 row với cùng một
   corruption. Check tốt phải khẳng định điều mà bước upstream đã bảo đảm, để bất kỳ vi
   phạm nào cũng có nghĩa là "có thứ gì đó đã sửa dữ liệu sau đó". Và quan trọng không kém:
   phải ghi lại cả signal **không** đổi, nếu không báo cáo sẽ ngầm gợi ý rằng hệ thống
   quality phát hiện được mọi loại lỗi.

3. **Về ảnh hưởng của data đến RAG agent:** không phải mọi corruption đều hạ mọi metric,
   và cơ chế trả lời quyết định corruption nào gây hại. Vì `qa.py` có exact-title lookup,
   blank summary hạ `token_f1` nhưng **không** hạ `retrieval_hit_rate`; chỉ truncate title
   hoặc drop document mới phá được retrieval. Còn noise injection thì không tín hiệu cấu
   trúc nào bắt được — cần semantic monitoring, không phải rule-based validation.

### Nếu có thêm thời gian

Thêm một check ngữ nghĩa cho chính lỗ hổng đã xác định: tính embedding của `summary` mỗi
row rồi so với centroid của corpus, cảnh báo những row lệch bất thường. Cách đo cải thiện:
chạy lại đúng corruption seed 42 và kiểm xem 2 paper bị `inject_noise` có nằm trong nhóm
lệch nhất không — nếu có thì `detection_rate` lên 1.0 mà không cần thêm rule thủ công nào.
Chi phí gần như bằng không vì embedding đã được tính sẵn khi build index.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Kỳ Anh
**Ngày xác nhận:** 2026-08-06
