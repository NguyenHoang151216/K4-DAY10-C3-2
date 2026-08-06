# R2 — Ingestion Owner — Ghi chú làm việc

> File riêng của R2 theo §1.9. CP6 R1 gộp các kết luận đã có artifact vào
> `group_report.md`. R2 chỉ nhận ownership cho `src/ingestion/crossref.py`, raw
> lineage và `docs/KNOWLEDGE.md`.

---

## CP0 — Contract và smoke test nguồn

- Đã chốt `paper_id = DOI.lower()` để ID ổn định xuyên suốt pipeline.
- Mapping nguồn: `abstract → summary`, `subject → categories`,
  `container-title[0] → comment`, link PDF → `pdf_url`.
- Parser loại JATS/HTML nhưng giữ text content, chuẩn hóa whitespace và không
  truyền scalar `None` xuống cleaning.
- Smoke test Crossref `rows=3` trả đủ 3 record nên không cần fallback query.

Contract R2 bàn giao R3 gồm 11 trường:

```text
paper_id, title, summary, authors, categories, primary_category,
published, updated, abs_url, pdf_url, comment
```

## CP1 — Fetch, retry và raw replay

- Retry có chọn lọc cho `429/500/502/503/504`; không retry
  `400/401/403/404`.
- Backoff `1 → 2 → 4 → 8s`, có jitter deterministic theo `random_seed` và
  tôn trọng `Retry-After` dạng giây hoặc HTTP date.
- Raw response được ghi atomic qua file `.tmp` **trước khi parse**.
- Parsed records cũng được ghi atomic; `load_raw_records()` hỗ trợ replay mà
  không gọi Crossref lại.
- Đã xử lý HTTP 406 thực tế bằng `Accept: application/json`; payload schema
  không đổi.

Kiểm tra mock đã chứng minh: `503 → 429 → 200` có retry, HTTP 400 chỉ gọi một
lần, raw response tồn tại trước parser và không còn file `.tmp` sau khi ghi.

## CP2 — Lineage raw → clean → index

Baseline chính thức có 48 record. ID được chọn để kiểm tra:

```text
10.1007/s10115-026-02792-4
```

Kết quả:

```text
raw=True
clean=True
embedding_manifest_metadata=True
chroma_metadata=True
title_matches=True
collection=papers-baseline
raw_count=48
clean_count=48
manifest_count=48
chroma_count=48
```

## CP3 — Đối chiếu raw và clean

```text
raw records       = 48
clean rows        = 48
dropped           = 0
duplicates_removed= 0
summary threshold = 80
```

Không có chênh lệch count vì cả 48 record đều có DOI, title, publication date
và abstract dài tối thiểu 80 ký tự. Thiếu `subject/categories` không làm record
bị loại; quality report ghi đúng một warning `categories_present_ratio`.

## CP4 — Ba dòng chốt trước khi nghỉ

1. Raw snapshot là điểm phục hồi duy nhất; không fetch lại trong controlled experiment.
2. `paper_id` DOI lowercase đã khớp raw, clean, manifest và Chroma metadata.
3. CP5/CP6 phải chứng minh raw hash không đổi và repaired core hash bằng baseline.

## CP5 — Preflight độc lập của R2

### Snapshot đã khóa

| Artifact | SHA-256 |
|---|---|
| `data/raw/crossref_response.json` | `3201C23DAD6408B24F6EDFF6BF26D98F93B8BB3528522BD4F78F833F6AFCD3B8` |
| `data/raw/crossref_records.json` | `8407431AE30918943967574339E07BFCDF1EA37782847BE0FD587AE818DD0344` |
| `data/results/run_context.json` | `E568510FBA3F2A9A139A08FF2FD03452348A3FE3DE345676091BBF655AEABEEC` |
| `data/eval/test_set.json` | `5255DAF86B7225FB61F5450D5C5EFC4EC579B6730C6BD963144F3FA9BA850A55` |

`load_settings().refresh_source == false` ở trạng thái mặc định sau baseline.
Ba ID trong test set được chọn làm lineage candidates:

```text
10.1007/s10115-026-02792-4
10.1111/exsy.70341
10.36713/epra26155
```

Khi `corruption_log.json` tồn tại, R2 sẽ chọn candidate thực sự bị tác động và
đối chiếu `before_hash`/`after_hash`. Pass CP5 yêu cầu hai raw SHA-256 ở trên
không đổi và flow không gọi `fetch_source_records()`.

## CP6 — Expected repair và security preflight

R2 đã reload đúng raw snapshot và chạy `build_clean_dataframe()` trong bộ nhớ
với `run_date=2026-08-06T09:25:13.243798+00:00` từ `run_context.json`.

```text
baseline_clean_core_hash = 7b3243b2308b272d
rebuilt_from_raw_core_hash= 7b3243b2308b272d
core_hash_equal          = true
paper_id_order_equal     = true
rebuilt rows             = 48
```

Đây là expected repair độc lập, không copy từ baseline và không gọi source.
Sau khi R1/R3 sinh repaired artifact, R2 chỉ cần xác minh repaired hash bằng
`7b3243b2308b272d` và candidate bị corrupt/drop đã xuất hiện lại với nội dung
trùng raw/clean expected.

Security scan trên toàn bộ file đang được Git track:

```text
.env tracked             = false
recognized secret hits   = 0
email occurrences        = 0
```

### Dependency còn chờ — không tự nhận là đã pass

- `corruption_log.json` và corrupted dataset từ R1/R3.
- Repaired dataset và `repair_validation.json` từ R1/R3.
- Repaired Chroma metadata từ R4.
- Metrics/quality/comparison artifact từ R5 để hoàn thiện phân tích chung.

R2 không sửa `corruption_flow.py`, `corruption.py`, `index.py`, quality/report
hoặc dashboard để tránh vi phạm ownership.
