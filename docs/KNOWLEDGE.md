# KNOWLEDGE — Data Pipeline & Data Observability

> Trạng thái: R2 đã hoàn tất bằng chứng lineage CP2. R2 sở hữu cấu trúc tài
> liệu; mỗi role bổ sung bằng chứng và phân tích thuộc module của mình. Không
> điền số liệu bằng tay: mọi count, hash và metric cuối cùng phải lấy từ
> artifact trong `data/`.

## 1. Pipeline này là ETL hay ELT?

Đây là một pipeline **ETL**:

1. **Extract:** lấy metadata bài báo từ Crossref và lưu raw snapshot.
2. **Transform:** parse JATS, chuẩn hóa schema, loại record không hợp lệ, dedupe
   và tạo `text_for_embedding`.
3. **Load:** tạo embedding và nạp document vào Chroma collection.

Nếu triển khai theo ELT, dữ liệu Crossref nguyên trạng sẽ được nạp trước vào
warehouse/lakehouse, sau đó mới transform bằng SQL hoặc dbt. Lab không đi theo
cách đó vì Chroma chỉ nhận dữ liệu đã được chuẩn hóa để embedding.

## 2. Bronze, Silver và Gold

| Tầng | Artifact trong lab | Ý nghĩa |
|---|---|---|
| Bronze | `data/raw/crossref_response.json` | Payload nguồn được lưu trước khi parse, dùng để audit và replay |
| Bronze chuẩn hóa | `data/raw/crossref_records.json` | Danh sách 11 trường theo contract `PaperRecord` |
| Silver | `data/clean/papers_clean.csv` và `.json` | Dữ liệu đã clean, dedupe và có 16 cột đóng băng |
| Gold | collection `papers-baseline` và embedding manifest | Dữ liệu sẵn sàng cho retrieval, agent và evaluation |

Embedding manifest là bằng chứng đọc được bằng JSON cho các document đã đưa
vào index. Chroma là serving store thực tế của tầng Gold.

## 3. Data contract

Mặt phân giới R2 → R3 gồm 11 trường, không được đổi tên:

```text
paper_id, title, summary, authors, categories, primary_category,
published, updated, abs_url, pdf_url, comment
```

R3 bổ sung 5 trường:

```text
authors_joined, categories_joined, summary_chars, age_days,
text_for_embedding
```

`paper_id` là DOI đã lowercase. Đây là join key xuyên suốt raw, clean, embedding
manifest, Chroma metadata và `ground_truth_doc_ids` của test set.

## 4. Lineage và bằng chứng CP2

### Trạng thái artifact khi R2 kiểm tra

| Chặng | Trạng thái | Bằng chứng hiện tại |
|---|---|---|
| Raw response | Có | Corpus chính thức đã fetch một lần; SHA-256 `3201C23DAD6408B24F6EDFF6BF26D98F93B8BB3528522BD4F78F833F6AFCD3B8` |
| Raw records | Có | 48 record; SHA-256 `8407431AE30918943967574339E07BFCDF1EA37782847BE0FD587AE818DD0344` |
| Clean JSON/CSV | Có | 48 row; không drop/dedupe; JSON SHA-256 `7B7CFB10B5A00F791AD1ABD2BFBCF0AD92595B5C7034F4D3AEB9D69B6F12BDBA` |
| Embedding manifest | Có | 48 document; SHA-256 `EC58FEC1FD9918400FF459A6FE3DEDCE7A25BDEA156A2D78347A4CB6FAE9F116` |
| Chroma metadata | Đã xác minh | Collection `papers-baseline` có 48 document và metadata ID khớp manifest |

ID được chọn để kiểm tra end-to-end:

```text
10.1007/s10115-026-02792-4
```

Kết quả kiểm tra:

```text
raw=True
clean=True
index_metadata=True
title_matches=True
collection=papers-baseline
collection_count=48
chroma_match_count=1
document_nonempty=True
```

Như vậy cùng một DOI lowercase đã đi xuyên suốt raw → clean → embedding
manifest → Chroma metadata mà không bị đổi ID hoặc title.

### Phép kiểm tra read-only sau khi R1/R4 sinh artifact

```powershell
$raw = Get-Content -Raw -Encoding UTF8 data/raw/crossref_records.json | ConvertFrom-Json
$clean = Get-Content -Raw -Encoding UTF8 data/clean/papers_clean.json | ConvertFrom-Json
$manifest = Get-Content -Raw -Encoding UTF8 data/embeddings/papers_embeddings.json | ConvertFrom-Json

$rawIds = @($raw.paper_id)
$candidate = $clean | Where-Object { $_.paper_id -in $rawIds } | Select-Object -First 1
if ($null -eq $candidate) { throw "Không có paper_id chung giữa raw và clean" }

$indexed = $manifest.documents | Where-Object {
    $_.metadata.paper_id -eq $candidate.paper_id
} | Select-Object -First 1
if ($null -eq $indexed) { throw "paper_id không có trong index metadata" }

[PSCustomObject]@{
    paper_id = $candidate.paper_id
    raw = $candidate.paper_id -in $rawIds
    clean = $true
    index_metadata = $indexed.metadata.paper_id -eq $candidate.paper_id
    collection = $manifest.collection_name
} | Format-List
```

Pass criterion của role2: cùng một `paper_id` cho kết quả `raw=True`,
`clean=True`, `index_metadata=True`, và collection là `papers-baseline`.

## 5. Idempotency, replay và backfill

- **Idempotency:** cùng raw snapshot, cùng `run_date` và cùng code cleaning phải
  sinh cùng clean content. Sort và dedupe deterministic giúp kết quả không phụ
  thuộc thứ tự response.
- **Replay:** `load_raw_records()` đọc lại `crossref_records.json`; pipeline có
  thể chạy cleaning/index mà không gọi Crossref lần nữa.
- **Backfill:** muốn bổ sung một khoảng thời gian cũ, thay filter nguồn có chủ
  đích, lưu snapshot riêng và chạy lại transform. Không sửa tay clean dataset.
- **Lineage:** raw response → `PaperRecord` → clean row → index metadata → test
  set/answer được nối bằng `paper_id`.

Trong baseline experiment phải giữ `REFRESH_SOURCE=false` sau lần fetch chính
thức. Refresh giữa cleaning, indexing hoặc evaluation sẽ làm corpus thay đổi và
phá tính so sánh.

## 6. Vì sao raw snapshot là điều kiện cần để repair?

Raw snapshot được ghi atomic **trước khi parse**. Vì thế lỗi parser, cleaning,
corruption hoặc index không làm mất đầu vào gốc của lần chạy. Repair có thể đọc
lại snapshot, áp dụng code đã sửa và chứng minh dữ liệu phục hồi bằng ID/hash.

Nếu không có raw snapshot, nhóm chỉ còn hai lựa chọn: gọi API lại và nhận một
tập dữ liệu có thể đã thay đổi, hoặc sửa trực tiếp clean data. Cả hai đều không
chứng minh được repair; chúng tạo một đầu vào mới hoặc che lỗi cũ.

## 7. Controlled experiment

So sánh baseline, corrupted và repaired chỉ có ý nghĩa khi giữ nguyên:

- raw baseline và test set;
- embedding model `sentence-transformers/all-MiniLM-L6-v2`;
- `top_k=4`;
- question/ground truth;
- cách tính metric và judge.

Biến độc lập duy nhất phải là trạng thái dataset. Nếu refresh nguồn hoặc sinh
lại test set giữa ba lần chạy, thay đổi metric không còn quy được cho corruption.

## 8. Sáu chiều data quality

> R5 bổ sung kết quả thật từ quality artifact ở CP3/CP6.

| Chiều | Ví dụ trong lab |
|---|---|
| Completeness | title, summary, authors, categories có đủ hay không |
| Uniqueness | `paper_id` không trùng |
| Validity | ngày ISO, summary đủ dài, metadata là scalar hợp lệ |
| Consistency | `paper_id` và content khớp giữa raw, clean và index |
| Freshness | `age_days`, newest document và stale ratio |
| Timeliness | pipeline fetch/refresh đúng thời điểm phục vụ người dùng |

## 9. Monitoring và observability

Monitoring trả lời các câu hỏi đã biết trước, ví dụ `paper_id` có unique hay
stale ratio có vượt ngưỡng. Observability kết hợp raw snapshot, cleaning stats,
quality/freshness report, retrieval answers và metrics để điều tra nguyên nhân
khi agent giảm chất lượng ngoài các rule đã định nghĩa.

## 10. Corruption và mối đe dọa thực tế

> R3 bổ sung ID bị tác động và tham số thật từ `corruption_log.json` ở CP5.

| Corruption | Mối đe dọa | Tín hiệu phát hiện |
|---|---|---|
| Drop latest | Knowledge base stale | row count và freshness |
| Blank summary | Mất context, tăng nguy cơ hallucination | summary usable ratio |
| Inject noise | Data poisoning | RAG metric/semantic monitoring |
| Truncate title | Entity resolution failure | title length và retrieval hit |
| Stale date | Temporal reasoning sai | freshness/stale ratio |
| Duplicate | Retrieval bias, top-k kém đa dạng | `paper_id_unique` |

## 11. Giới hạn metric và judge

> R5 bổ sung số liệu thật; R4 bổ sung một hit/miss cụ thể từ answer artifact.

- `token_f1` dùng tập token lowercase tách theo whitespace, nên không hiểu
  paraphrase hoặc từ đồng nghĩa.
- Exact-title lookup có thể giữ retrieval hit cao ngay cả khi summary bị blank;
  vì vậy không kỳ vọng mọi corruption làm giảm mọi metric.
- Judge có fallback heuristic khi LLM lỗi. Báo cáo phải công bố fallback rate;
  nếu toàn bộ dùng fallback thì không được gọi kết quả là LLM-as-a-judge.
- Noise injection có thể vượt qua schema validation, nên cần semantic monitoring
  hoặc theo dõi RAG metric chứ không chỉ rule-based checks.

## 12. Việc cần bổ sung bằng artifact thật

- [x] R2: thay bảng lineage CP2 bằng ID từ baseline chính thức.
- [ ] R3: điền cleaning stats và corruption IDs/parameters.
- [ ] R4: điền Chroma count, semantic search và exact lookup evidence.
- [ ] R5: điền quality/freshness, metric và judge fallback rate.
- [ ] R1: đối chiếu mọi con số trong tài liệu với artifact được commit.
