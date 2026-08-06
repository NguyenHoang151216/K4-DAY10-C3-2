# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
|---|---|
| Họ và tên | Nguyễn Chí Hoàng |
| MSSV | 2A202601638 |
| Khóa/Lớp | K4 |
| Tên nhóm | C3-1 |
| Vai trò chính | R2 — Ingestion Owner |
| Repository | <https://github.com/NguyenHoang151216/K4_Day10_C3-1> |
| Ngày hoàn thành | 2026-08-06 |

> Trạng thái báo cáo: phần ingestion, raw lineage và preflight repair của R2 đã
> hoàn thành. Kết luận corrupted/repaired cuối cùng còn chờ pipeline tích hợp
> sinh đủ metrics và repaired artifacts; báo cáo không điền số liệu giả cho các
> trạng thái chưa có artifact.

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
|---|---|---|---|---|
| Crossref ingestion | `src/ingestion/crossref.py`: `PaperRecord`, `strip_jats`, `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref `/works` payload và `Settings` | Raw response, raw records và danh sách `PaperRecord` | Hoàn thành |
| Raw lineage và replay | `data/raw/`, `data/results/run_context.json` | Raw snapshot, run date, clean/index artifacts | Hash nguồn, stable ID và expected repair hash | Hoàn thành phần độc lập; chờ repaired artifact để xác minh cuối |
| Báo cáo kiến thức | `docs/KNOWLEDGE.md`, `report/notes/r2_ingestion.md` | Code và artifact thật của nhóm | Phân tích ETL, lineage, replay, idempotency và repair | Hoàn thành phần R2; chờ đóng góp R1/R3/R4/R5 |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
|---|---|---|
| Chốt contract 11 trường `PaperRecord` → clean schema | R3 cleaning | 48 raw records được clean thành 48 rows, không đổi `paper_id` |
| Xác minh `paper_id` raw → clean → manifest → Chroma | R1/R3/R4 | ID `10.1007/s10115-026-02792-4` khớp ở cả bốn chặng |
| Khóa hash raw/run-context/test-set trước corruption | R1 integration | Có mốc kiểm chứng flow không refresh source hoặc đổi test set |
| Secret scan trên file được Git track | Cả nhóm | Không thấy `.env`, key prefix hoặc email tại thời điểm kiểm tra |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
|---|---|---|---|
| Parse Crossref thành schema ổn định | `parse_crossref_payload()` | DOI lowercase; JATS được loại; optional field không truyền scalar `None` | Smoke test `rows=3` và parser contract checks |
| Fetch có khả năng chịu lỗi | `fetch_source_records()` | Retry `429/500/502/503/504`, backoff `1/2/4/8s`, jitter và `Retry-After` | Mock sequence `503 → 429 → 200`; HTTP 400 chỉ gọi một lần |
| Lưu lineage có thể replay | `crossref_response.json`, `crossref_records.json`, `load_raw_records()` | Raw response ghi atomic trước parse; raw records reload không gọi API | Rebuild clean trong bộ nhớ từ raw snapshot |
| Xác minh baseline lineage | Raw, clean, embedding manifest và Chroma | 48 → 48 → 48 → 48; title và `paper_id` khớp | ID `10.1007/s10115-026-02792-4` cho kết quả `True` ở mọi chặng |
| Chuẩn bị bằng chứng repair | Raw/run context/test-set hash và `core_content_hash` | Expected repaired hash `7b3243b2308b272d` | Rebuild từ raw bằng đúng `run_date` cho cùng hash và thứ tự ID |

Output cụ thể quan trọng nhất là raw snapshot bất biến gồm 48 record:

```text
crossref_response.json SHA-256 = 3201C23DAD6408B24F6EDFF6BF26D98F93B8BB3528522BD4F78F833F6AFCD3B8
crossref_records.json  SHA-256 = 8407431AE30918943967574339E07BFCDF1EA37782847BE0FD587AE818DD0344
```

`corruption_log.json` hiện cho biết lineage candidate
`10.1007/s10115-026-02792-4` đã bị operator `drop_latest` tác động. Đây là
record R2 sẽ dùng để chứng minh phục hồi khi repaired dataset/index xuất hiện.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Crossref trả metadata không đồng nhất: nhiều trường là list, ngày dùng
`date-parts`, abstract chứa JATS, một số trường có thể thiếu và source có thể
trả rate-limit hoặc lỗi tạm thời. Pipeline cần biến payload đó thành contract
ổn định, đồng thời giữ raw snapshot để audit, replay và repair mà không phải gọi
lại một nguồn sống có thể đã thay đổi.

### Cách triển khai

1. DOI được chuẩn hóa lowercase và dùng làm `paper_id` ổn định.
2. Title/container title lấy phần tử text đầu tiên; authors ghép `given family`;
   subject được chuẩn hóa thành list categories.
3. Abstract được parse bằng `HTMLParser` để loại JATS/HTML nhưng giữ text và
   giải mã entity.
4. Ngày xuất bản được lấy theo thứ tự ưu tiên
   `published-print → published-online → published → issued → created` và đổi
   sang ISO.
5. Request chỉ retry lỗi có khả năng hồi phục. Lỗi client `400/401/403/404`
   dừng ngay để không che lỗi query/credential.
6. JSON được ghi qua file sibling `.tmp`, sau đó atomic replace. Raw response
   được ghi trước parser để lỗi transform không làm mất dữ liệu nguồn.
7. `load_raw_records()` kiểm tra JSON array và contract trước khi cho pipeline
   replay.

### Input, output và contract

| Thành phần | Mô tả |
|---|---|
| Input | Crossref `/works` JSON; query/filter/timeout/retry từ `Settings` |
| Output | `list[PaperRecord]`, raw response JSON và parsed raw records JSON |
| Module phụ thuộc | `src/core/config.py`, thư viện `requests` |
| Module sử dụng output | Cleaning, phase1, corruption repair và lineage verification |
| Điều kiện lỗi cần xử lý | 429/5xx, `Retry-After`, timeout, JSON lỗi, thiếu DOI/title, JATS malformed, raw snapshot sai contract |

### Cách xác minh

```powershell
# Kiểm tra raw count và stable ID
$raw = Get-Content -Raw -Encoding UTF8 data/raw/crossref_records.json | ConvertFrom-Json
$raw.Count
$raw | Where-Object { $_.paper_id -cne $_.paper_id.ToLowerInvariant() }

# Khóa hash nguồn trước corruption
Get-FileHash data/raw/crossref_response.json,
  data/raw/crossref_records.json,
  data/results/run_context.json,
  data/eval/test_set.json -Algorithm SHA256
```

- **Kết quả mong đợi:** 48 record, không có DOI uppercase; hash nguồn không đổi
  giữa baseline, corrupted và repaired.
- **Kết quả thực tế:** 48 record; raw → clean → manifest → Chroma đều giữ cùng
  `paper_id`; rebuild từ raw cho `core_hash_equal=true`.
- **Artifact/log:** `data/raw/`, `data/results/run_context.json`,
  `report/notes/r2_ingestion.md` và `docs/KNOWLEDGE.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Nếu parser chạy trước rồi mới lưu dữ liệu, một lỗi schema/JATS
  có thể làm mất payload của lần fetch và khiến repair phải gọi lại Crossref.
- **Các phương án đã cân nhắc:** chỉ lưu parsed records; lưu payload sau khi
  parse thành công; hoặc lưu raw response atomic trước parse.
- **Phương án đã chọn:** ghi raw response qua `.tmp → replace` trước khi gọi
  `parse_crossref_payload()`.
- **Lý do:** raw snapshot trở thành bằng chứng bất biến và nguồn replay. Chi phí
  thêm chỉ là một file JSON nhỏ, nhưng đổi lại có thể tái lập baseline/repair
  mà không phụ thuộc trạng thái mới của Crossref.
- **Bằng chứng quyết định phù hợp:** rebuild clean từ raw với cùng `run_date`
  cho đúng 48 rows, đúng thứ tự ID và cùng core hash `7b3243b2308b272d`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `406 Client Error: Not Acceptable` khi gọi
  `https://api.crossref.org/works`.
- **Bước tái hiện:** chạy baseline với `REFRESH_SOURCE=true`; pipeline dừng tại
  bước fetch trước khi thay raw snapshot.
- **Nguyên nhân gốc:** header `Accept` dùng vendor media type quá chặt và một số
  Crossref edge node từ chối với HTTP 406.
- **Cách xử lý:** đổi header sang `Accept: application/json`; không thêm 406 vào
  retry list vì đây là lỗi client/cấu hình, không phải lỗi tạm thời.
- **Cách xác minh sau khi sửa:** baseline fetch được 48 records và hoàn thành đủ
  13 bước; payload schema không thay đổi.
- **Điều học được:** retry không phải cách sửa mọi HTTP error. Cần phân biệt lỗi
  tạm thời với lỗi request để tránh lặp vô ích và che nguyên nhân thật.

Blocker còn lại không thuộc ownership R2: chưa có corrupted/repaired RAG metrics,
repaired dataset/index và `repair_validation.json`, nên chưa thể tuyên bố repair
end-to-end đã pass.

## 7. Hiểu biết về luồng end-to-end

1. Crossref payload được lưu raw, parse thành `PaperRecord`, clean thành schema
   16 cột, tạo `text_for_embedding`, sau đó MiniLM sinh vector và Chroma lưu
   document cùng metadata.
2. Evaluation set giữ câu hỏi, câu trả lời chuẩn và
   `ground_truth_doc_ids`. Retrieval hit đo document kỳ vọng có nằm trong top-k;
   token F1/judge đo câu trả lời so với ground truth.
3. Quality checks kiểm tra các điều kiện cấu trúc đã biết như missing, duplicate
   và summary usability. Freshness theo dõi độ mới của corpus qua publication
   date, `age_days`, latest record và stale ratio.
4. Ba trạng thái phải dùng cùng test set, model embedding, `top_k` và judge để
   thay đổi metric chỉ đến từ dataset. Tạo lại test set sau corruption sẽ làm
   phép so sánh mất ý nghĩa.
5. Repair thành công khi dữ liệu được dựng lại từ raw với cùng `run_date`,
   repaired quality pass, core hash bằng baseline, record bị tác động xuất hiện
   lại và RAG metrics quay về baseline hoặc có giải thích rõ phần chưa phục hồi.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
|---|---:|---:|---:|---|
| `retrieval_hit_rate` | 1.0000 | Chưa có artifact | Chưa có artifact | Chưa thể kết luận RAG impact/recovery |
| `mean_token_f1` | 1.0000 | Chưa có artifact | Chưa có artifact | Baseline hoàn hảo do exact-title/metadata lookup; cần giữ cùng test set |
| `judge_accuracy` | 1.0000 | Chưa có artifact | Chưa có artifact | Baseline judge có khả năng dùng heuristic fallback; không gọi là LLM-as-a-judge khi chưa đo fallback rate |
| `mean_judge_score` | 5.0000 | Chưa có artifact | Chưa có artifact | Chưa đủ cơ sở so sánh ba trạng thái |
| Quality checks | PASS; warning categories và future date | FAIL: `paper_id_unique`, `summary_all_usable` | Chưa có artifact | Structural corruption đã được quality checks phát hiện |
| Freshness status | `is_fresh=true`, stale rows 0 | `is_fresh=false`, stale rows 2 | Chưa có artifact | Stale-date/drop-latest đã làm freshness suy giảm |

Baseline có 14 evaluation samples. Corruption log có đủ 6 operators, làm dataset
từ 48 thành 49 rows và xác minh 7 records thay đổi nội dung.

### Kết luận từ số liệu

1. Duplicate records và blank summary → corrupted quality fail
   `paper_id_unique`/`summary_all_usable`; stale date → freshness chuyển từ
   `true` sang `false` với 2 stale rows. Chưa có `corrupted_metrics.json`, nên
   không gắn thêm kết luận agent metric chưa được đo.
2. Expected repair từ raw → rebuilt core hash bằng baseline
   `7b3243b2308b272d`. Tuy nhiên chưa có repaired artifact nên chưa thể kết luận
   quality và agent metrics đã phục hồi thực tế.

Corruption quan sát rõ nhất hiện tại là stale date và duplicate/blank summary vì
chúng làm quality/freshness đổi trạng thái trực tiếp. Noise injection quan trọng
về bảo mật nhưng schema checks không phát hiện được; cần corrupted RAG metrics
hoặc semantic monitoring để chứng minh impact.

Kết quả khác kỳ vọng là Crossref không cung cấp `subject` cho corpus hiện tại,
làm categories ratio warning và test set chỉ có 14 thay vì 16 câu. Đây là đặc
tính dữ liệu nguồn, không phải lỗi parser, nên nhóm giữ warning và không bịa
categories.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw snapshot và run context quan trọng ngang code: thiếu chúng thì không thể
   replay, audit hoặc chứng minh repair.
2. Data quality rules phát hiện tốt lỗi cấu trúc đã biết nhưng không đủ cho data
   poisoning; observability phải kết hợp lineage, quality, freshness và RAG metrics.
3. Chất lượng agent phụ thuộc trực tiếp vào document identity và metadata. Chỉ
   đổi title/summary/date cũng có thể làm exact lookup, retrieval hoặc answer
   correctness thay đổi dù code agent không đổi.

### Nếu có thêm thời gian

Tôi sẽ bổ sung integration test dựng một response Crossref giả, chạy
parse → clean → index manifest → replay, rồi assert raw hash không đổi và
`paper_id` giống nhau ở mọi chặng. Test này giúp phát hiện sớm schema drift mà
không gọi API hoặc tải model trong mỗi lần CI.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận đã nêu đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Chí Hoàng  
**Ngày xác nhận:** 2026-08-06
