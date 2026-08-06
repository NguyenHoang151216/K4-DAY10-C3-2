# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Phạm Tuấn Anh |
| MSSV | 2A202601480 |
| Khóa/Lớp | K4 |
| Tên nhóm | C3-1 |
| Vai trò chính | **R3 — Cleaning & Corruption Owner** |
| Repository | https://github.com/NguyenHoang151216/K4-DAY10-C3-1 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cleaning & data modeling | `src/ingestion/cleaning.py` — `build_clean_dataframe` | `list[PaperRecord]` từ R2 + `run_date` | Clean DataFrame 16 cột → `papers_clean.csv/.json` | Hoàn thành |
| Contract schema dùng chung | `CLEAN_COLUMNS`, `SUMMARY_MIN_CHARS` | — | Hằng số cho R4/R5 import | Hoàn thành |
| Hash so sánh trạng thái | `core_content_hash`, `row_content_hash` | Clean DataFrame | Hash để R1 sinh `repair_validation.json` | Hoàn thành |
| Corruption & repair | `src/ingestion/corruption.py` — `corrupt_clean_dataframe` | Clean DataFrame + `ground_truth_doc_ids` | Corrupted DataFrame + `corruption_log.json` | Hoàn thành |

Tôi **không** nhận ownership cho `crossref.py` (R2), `quality.py`/`testset.py` (R5), `phase1.py` (R1), `dashboard.py` (R4) hay bất kỳ file nào trong `src/retrieval/` (code có sẵn).

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Phát hiện blocker Crossref 406 | R2 — `crossref.py` | Đo được `Accept: application/vnd.crossref-api-message+json` → 406, `application/json` → 200 với 101.141 kết quả. Không tự sửa file của R2, chỉ báo kèm bằng chứng |
| Cảnh báo schema trước khi R5 code | R5 — `testset.py` | Báo trước 3 điểm: title chứa `'` (Bẫy 5), ground truth phải là `first_sentence(summary)` (Bẫy 6), `categories` rỗng 100% sẽ sinh ground truth rỗng. Cả 3 đã được R5 xử lý |
| Đo ngưỡng quality vs quy mô corruption | R5 — `quality.py` | Chỉ ra `blank_summary` và `stale_date` không kích hoạt được check nào vì tỉ lệ 0.041 < ngưỡng 0.10/0.20 |
| Dry-run toàn tuyến, bàn giao trình tự gọi hàm | R1 — `corruption_flow.py` | 10 bước đã chạy được, kèm số liệu thật |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/artifact | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chốt và implement contract 16 cột | `src/ingestion/cleaning.py` | Clean DataFrame Chroma-safe | Smoke test 52 assertion, `copy_on_write=True` |
| 6 corruption operator deterministic | `src/ingestion/corruption.py` | `corruption_log.json` chỉ chứa ID + hash | Smoke test 40 assertion |
| Dry-run toàn tuyến CP3→CP6 | `report/notes/r3_cleaning_corruption.md` | Bảng 3 trạng thái + `repair_validation` | Chạy sandbox trên 48 record thật |

**Output cụ thể:** `core_content_hash(baseline) == core_content_hash(repaired) == 7b3243b2308b272d` — chứng minh repair từ raw snapshot phục hồi dữ liệu **chính xác đến từng ký tự**, không phải "gần đúng".

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

`build_clean_dataframe` nằm **ngay trung tâm luồng dữ liệu**: R4 (`index.py`), R5 (`testset.py`, `quality.py`) và R1 (`phase1.py`) đều đọc schema do hàm này sinh ra. Đổi tên một cột là gãy đồng thời 4 module. `corrupt_clean_dataframe` thì phải làm hỏng dữ liệu **có kiểm soát và đo được**, chứ không phải hỏng bừa.

### Cách triển khai

**Cleaning** — normalize (unescape HTML + strip markup còn sót) → parse date vào 2 cột phụ → sinh 5 cột dẫn xuất → lọc theo 4 lý do có đếm → dedupe `paper_id` bằng stable sort → drop cột datetime phụ → khoá thứ tự cột theo `CLEAN_COLUMNS`.

**Corruption** — `df.copy()` rồi 6 operator theo thứ tự có ý nghĩa: `drop_latest` chạy đầu (để operator sau không nhắm vào row đã xoá), `duplicate_rows` chạy cuối và chỉ nhân bản row **chưa bị chạm** (để bản sao giữ nguyên hash baseline, giúp bước verify đếm chính xác). Target 6 operator **không chồng nhau**, chia 2 pool trong/ngoài test set.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `list[PaperRecord]` (11 field) + `run_date`; corruption nhận clean DataFrame + `ground_truth_doc_ids` |
| Output | DataFrame đúng 16 cột `CLEAN_COLUMNS`, 0 NaN, không cột datetime; `corruption_log.json` |
| Module phụ thuộc | `ingestion.crossref.PaperRecord`, `core.utils` |
| Module sử dụng output | `retrieval/index.py`, `evaluation/testset.py`, `observability/quality.py`, `pipelines/phase1.py` |
| Điều kiện lỗi cần xử lý | `records` rỗng · `run_date` naive (tz) · date sai format · `paper_id` trùng · corruption không ăn (Bẫy 1) |

### Cách xác minh

```bash
python <scratchpad>/smoke_cleaning.py      # 52 assertion
python <scratchpad>/smoke_corruption.py    # 40 assertion
python <scratchpad>/dryrun_full.py         # toàn tuyến trên 48 record thật
```

- **Kết quả mong đợi:** schema ổn định, corruption làm giảm metric, repair phục hồi.
- **Kết quả thực tế:** tất cả pass. `retrieval_hit_rate` 1.0000 → 0.8571 → 1.0000; `mean_token_f1` 1.0000 → 0.7174 → 1.0000.
- **Artifact/log:** sandbox ngoài repo (`data/` trong repo không bị chạm theo LUẬT VÀNG §1.2). Không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `corrupt_clean_dataframe` phải rebuild `age_days` sau khi `stale_date` đổi `published`, nhưng chữ ký hàm bị đóng băng nên **không nhận được `run_date`**.
- **Các phương án đã cân nhắc:** (a) thêm tham số `run_date` — vi phạm contract đóng băng; (b) đọc `run_context.json` từ trong module — làm module phụ thuộc filesystem, khó test; (c) suy ngược từ chính baseline.
- **Phương án đã chọn:** (c) — mỗi row baseline thoả `run_date ≈ published + age_days`, lấy **median** trên toàn baseline.
- **Lý do:** không đổi contract, không thêm phụ thuộc, và median miễn nhiễm lỗi làm tròn ±1 ngày của `.dt.days`.
- **Bằng chứng:** trong dry-run, `stale_date` lùi `published` 6 năm và `age_days` được tính lại đúng (ví dụ `2026-07-03` age 34 → `2020-07-04` age 2224); `core_content_hash` baseline == repaired vẫn khớp tuyệt đối.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `requests.exceptions.HTTPError: 406 Client Error: Not Acceptable for url: https://api.crossref.org/works?...` khi gọi `fetch_source_records`.
- **Bước tái hiện:** gọi Crossref với header `Accept: application/vnd.crossref-api-message+json`.
- **Nguyên nhân gốc:** Crossref không còn chấp nhận content type đó. Không phải lỗi query hay filter — filter của R1 hoàn toàn đúng.
- **Cách xử lý:** đo đối chứng 4 biến thể header. `application/json` → **200**, 101.141 kết quả, 48 record đều có abstract. `crossref.py` là file của R2 nên **tôi không sửa**; tôi patch header **trong bộ nhớ** ở script sandbox để dry-run đi tiếp, và báo R2 kèm bảng số liệu.
- **Cách xác minh sau khi sửa:** fetch được 48 record → `build_test_set` chạy được (trước đó raise vì `MIN_DOCUMENTS = 8`), `row_count_min` (hard, min 10) chuyển từ fail sang pass.
- **Điều học được:** một giá trị header sai chặn được cả 5 người. Và ranh giới sở hữu file vẫn giữ được kể cả khi gấp — báo kèm bằng chứng đo được thì R2 sửa trong một phút, còn tôi tự sửa thì tạo conflict.

## 7. Hiểu biết về luồng end-to-end

1. **Crossref → vector index:** `fetch_source_records` lưu raw response **trước khi parse** (snapshot bất biến) → `parse_crossref_payload` → `PaperRecord` → `build_clean_dataframe` sinh `text_for_embedding` → `LocalEmbeddingIndex.build` embed bằng MiniLM-L6-v2 và nạp vào Chroma, đẩy 8 trường metadata dạng scalar.
2. **Test set và ground truth:** `build_test_set` chọn deterministic 8 paper, sinh câu hỏi theo 4 template khớp đúng nhánh intent của `qa.py`. `ground_truth_doc_ids` cho phép đo `retrieval_hit_rate` (paper đúng có nằm trong top-k không) tách khỏi `token_f1` (câu trả lời có đúng chữ không) — hai lỗi khác nhau, phải đo riêng.
3. **Quality vs freshness:** quality check là **tập điều kiện đã biết** (monitoring) — cột có đủ không, `paper_id` có unique không. Freshness là **tín hiệu theo thời gian** để điều tra cả lỗi chưa biết trước (observability): dữ liệu vẫn hợp lệ về schema nhưng đã cũ thì agent trả lời theo thông tin lỗi thời.
4. **Vì sao cùng một test set:** đây là controlled experiment — giữ nguyên test set, embedding model, `top_k`, judge, **chỉ đổi trạng thái dataset**. Tạo lại test set từ dữ liệu corrupted là biến chênh lệch metric thành vô nghĩa vì đã đổi 2 biến cùng lúc.
5. **Repair thành công dựa vào:** `core_content_hash_equal: true` (dữ liệu khớp tuyệt đối), repaired pass toàn bộ hard check, và metric quay lại đúng mức baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.8571 | 1.0000 | Giảm 14,3% rồi phục hồi hoàn toàn |
| `mean_token_f1` | 1.0000 | 0.7174 | 1.0000 | Giảm mạnh hơn hit rate — xem phân tích dưới |
| `judge_accuracy` | — | — | — | **Không đo được**: máy thiếu `langchain`, không chạy LLM judge |
| `mean_judge_score` | — | — | — | **Không đo được**, lý do như trên |
| Quality checks (hard fail) | 0 | 1 | 0 | `paper_id_unique` fail do `duplicate_rows` |
| Quality checks (warn fail) | 1 | 2 | 1 | `title_min_length` thêm vào ở corrupted |
| Freshness | 0 stale | 2/49 stale | 0 stale | Dưới ngưỡng 0.20 nên **không** đổi trạng thái |

> Hai metric trên là **bản tự tính** theo đúng công thức trong `metrics.py`, không phải output của `evaluate_pipeline`. Không có LLM nên báo cáo này **không được** gọi kết quả là LLM-as-a-judge.

### Kết luận từ số liệu

1. `truncate_title` + `drop_latest` → `title_min_length` fail và row count giảm → `retrieval_hit_rate` **1.0000 → 0.8571**.
2. Replay cleaning từ raw snapshot bất biến với **cùng `run_date`** → `core_content_hash_equal: true`, hard check về 0 → `retrieval_hit_rate` và `token_f1` **phục hồi hoàn toàn về 1.0000**.

**Corruption nào ảnh hưởng rõ nhất:** `token_f1` giảm (−0.2826) **gấp đôi** `hit_rate` (−0.1429). Vì `qa.py` có exact-title lookup: `blank_summary` làm câu trả lời rỗng → `token_f1` sập, nhưng paper vẫn được tìm thấy → `hit_rate` **không đổi**. Chỉ `truncate_title` và `drop_latest` mới phá được retrieval. Đây là lý do phải đo hai metric riêng chứ không gộp một con số.

**Kết quả khác kỳ vọng:** tôi tưởng `blank_summary` và `stale_date` sẽ làm quality check fail. Thực tế **không**: tỉ lệ 2/49 = 0.041 so với ngưỡng cho phép 0.10 và 0.20. Đã kiểm tra bằng cách in trực tiếp tỉ lệ quan sát cạnh ngưỡng. Kết luận: **check theo tỉ lệ mù với corruption quy mô nhỏ**; chỉ check đếm-không-khoan-nhượng (`paper_id_unique`, `title_min_length`) mới bắt được. Đây là bài học đắt hơn cả việc nó fail đúng như dự đoán.

## 9. Điều học được và hướng cải thiện

1. **Data pipeline:** raw snapshot bất biến là **điều kiện cần** để repair. Không có nó thì chỉ còn cách sửa tay — tức là che lỗi chứ không phải sửa lỗi. `core_content_hash_equal: true` chỉ đạt được vì `fetch_source_records` lưu raw **trước khi** parse và `run_date` được persist trong `run_context.json`.
2. **Data quality/observability:** metric phải **tự khai báo độ tin cậy của nó**. Hai ví dụ trong chính bài này: `_judge_answer` nuốt exception nên pipeline vẫn ra số đẹp dù judge chết; và ngưỡng theo tỉ lệ vẫn "pass" trong khi dữ liệu đã hỏng thật. Một check pass không có nghĩa là dữ liệu tốt — chỉ có nghĩa là check đó không nhìn thấy vấn đề.
3. **Data → RAG agent:** không phải mọi corruption đều hạ mọi metric. Kiến trúc của `qa.py` quyết định corruption nào lộ ra ở metric nào. Muốn kết luận đúng thì phải hiểu code đọc dữ liệu, chứ không chỉ nhìn bảng số.

### Nếu có thêm thời gian

Thêm **semantic drift check**: so embedding trung bình của corpus giữa 2 lần chạy, cảnh báo khi cosine similarity tụt quá ngưỡng. Đây là thứ duy nhất bắt được `inject_noise` — operator mà **không schema check nào phát hiện được**, hiện chỉ lộ qua RAG metric sau khi đã ảnh hưởng người dùng. Đo cải thiện bằng cách chạy lại đúng corruption flow này và xem check mới có fail ở trạng thái corrupted không, trong khi vẫn pass ở baseline và repaired.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng — `judge_accuracy` và `mean_judge_score` được ghi rõ là **không đo được** vì thiếu `langchain`.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc thành viên khác.

**Họ và tên:** Phạm Tuấn Anh — MSSV 2A202601480
**Ngày xác nhận:** 2026-08-06
