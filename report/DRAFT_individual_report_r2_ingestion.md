# Member Role Report — Day 10 — R2 Ingestion Owner

> ⚠️ **BẢN NHÁP — CHƯA HỢP LỆ KHI CHƯA CÓ CHỮ KÝ CỦA CHỦ SỞ HỮU.**
> R3 tổng hợp bản này **từ chính `report/notes/r2_ingestion.md`** do R2 viết.
> **R2 phải:** điền mục 1, tự viết mục 7 / 9 / 10 bằng lời của mình, rà lại mục 3–6 và đổi tên file thành `<MSSV>_HoTen.md`.
> Mục 7, 9, 10 **cố ý để trống** — R3 không điền hộ (`report/README.md` §9).

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | *(R2 điền)* |
| MSSV | *(R2 điền)* |
| Khóa/Lớp | K4 |
| Tên nhóm | C3-1 |
| Vai trò chính | **R2 — Ingestion Owner** |
| Repository | https://github.com/NguyenHoang151216/K4-DAY10-C3-1 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Parse nguồn | `parse_crossref_payload` | payload Crossref | `list[PaperRecord]` (11 trường) | Hoàn thành |
| Fetch + retry | `fetch_source_records` | `Settings` | `data/raw/crossref_response.json`, `crossref_records.json` | Hoàn thành |
| Raw replay | `load_raw_records` | đường dẫn snapshot | `list[PaperRecord]` | Hoàn thành |
| Báo cáo kiến thức | `docs/KNOWLEDGE.md` | artifact của cả nhóm | tài liệu tổng kết | Hoàn thành |

Contract bàn giao cho R3 — 11 trường, đóng băng từ CP0:

```text
paper_id, title, summary, authors, categories, primary_category,
published, updated, abs_url, pdf_url, comment
```

## 3. Kết quả theo vai trò

| Nhiệm vụ | Artifact | Cách xác minh |
| --- | --- | --- |
| Fetch nguồn thật | `data/raw/crossref_records.json` — **48 record** | đếm phần tử JSON |
| Lưu raw trước khi parse | `data/raw/crossref_response.json` | ghi atomic `.tmp` → rename |
| Replay không gọi lại API | `load_raw_records()` | corruption flow repair chạy offline hoàn toàn |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Nếu parse rồi mới lưu, một lỗi parser sẽ làm mất luôn dữ liệu gốc — và không còn gì để repair. Repair khi đó chỉ còn cách sửa tay, tức là **che lỗi chứ không phải sửa lỗi**.

### Cách triển khai

- `paper_id = DOI.lower()` để ID ổn định xuyên suốt pipeline.
- Mapping: `abstract → summary`, `subject → categories`, `container-title[0] → comment`, link content-type PDF → `pdf_url`.
- Strip JATS/HTML bằng `HTMLParser` nhưng **giữ nguyên text content**; chuẩn hoá whitespace; không truyền `None` xuống cleaning.
- **Ghi raw response atomic (`.tmp` → rename) TRƯỚC khi parse.**
- Retry `429/500/502/503/504`; **không** retry `400/401/403/404`. Backoff `1 → 2 → 4 → 8s`, jitter deterministic theo `random_seed`, tôn trọng `Retry-After` cả dạng giây lẫn HTTP date.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref REST API, `Settings` |
| Output | raw response JSON, raw records JSON, `list[PaperRecord]` |
| Module dùng output | `cleaning.py` (R3) — và qua đó là toàn bộ pipeline |
| Điều kiện lỗi | record thiếu DOI hoặc title bị loại; fetch 0 record hợp lệ → raise kèm gợi ý sửa `SOURCE_QUERY` |

### Cách xác minh

```bash
python -c "import json; print(len(json.load(open('data/raw/crossref_records.json', encoding='utf-8'))))"
```

- **Kết quả thực tế:** 48 record, không record nào thiếu `published`, không trùng `paper_id`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** lưu raw trước hay sau khi parse.
- **Phương án đã cân nhắc:** (a) parse xong mới lưu bản đã chuẩn hoá; (b) lưu nguyên trạng response rồi mới parse.
- **Phương án đã chọn:** (b), và ghi atomic để không có file nửa vời khi tiến trình chết giữa chừng.
- **Lý do:** raw snapshot bất biến là **điều kiện cần để repair**. Không có nó thì CP6 không tồn tại.
- **Bằng chứng:** repair ở CP6 rebuild lại toàn bộ clean data **mà không gọi lại Crossref**, cho `core_content_hash_equal: true`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `HTTP 406 Not Acceptable` từ `https://api.crossref.org/works`.
- **Nguyên nhân gốc:** gửi `Accept: application/vnd.crossref-api-message+json` — content type này không còn được chấp nhận.
- **Cách xử lý:** đổi thành `Accept: application/json`. Payload schema không đổi nên không phải sửa parser.
- **Xác minh:** cùng query trả `HTTP 200` với 48 record đều có abstract.
- **Điều học được:** lỗi ở tầng transport có thể trông giống lỗi query. Đo từng biến một (đổi mỗi header, giữ nguyên query) tách được hai nguyên nhân.

## 7. Hiểu biết về luồng end-to-end

*(R2 tự viết.)*

## 8. Phân tích kết quả

Ingestion không sinh metric riêng, nhưng chất lượng nguồn quyết định trần của mọi metric phía sau:

| Quan sát từ nguồn | Hệ quả xuống pipeline |
| --- | --- |
| 48/48 record **không có `categories`** (Crossref thiếu field `subject`) | `categories_present_ratio` fail ở cả baseline lẫn repaired; test set mất 2 câu `categories`, còn 14 thay vì 16 |
| 1 record có `published = 2026-12-01` (tương lai) | warn `no_future_published` fail ở cả baseline lẫn repaired |
| Có record tiếng Nga (Cyrillic) | MiniLM là model tiếng Anh — abstract Cyrillic nằm lệch trong không gian embedding |

Cả ba đều là **giới hạn của nguồn dữ liệu**, không phải hậu quả của corruption.

## 9. Điều học được và hướng cải thiện

*(R2 tự viết.)*

## 10. Cam kết của thành viên

*(R2 tự đánh dấu và ký. Bản nháp này chưa có giá trị cam kết.)*

**Họ và tên:** *(R2 điền)*
**Ngày xác nhận:** *(R2 điền)*
