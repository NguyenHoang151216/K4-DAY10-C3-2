# Member Role Report — Day 10 — R1 Integrator & Release Owner

> ⚠️ **BẢN NHÁP — CHƯA HỢP LỆ KHI CHƯA CÓ CHỮ KÝ CỦA CHỦ SỞ HỮU.**
> R3 tổng hợp bản này **từ chính `report/notes/r1_integrator.md`** do R1 viết, để R1 không phải gõ lại từ đầu khi sát giờ nộp.
> **R1 phải:** điền mục 1, tự viết mục 7 / 9 / 10 bằng lời của mình, rà lại mục 3–6 và đổi tên file thành `<MSSV>_HoTen.md`.
> Mục 7, 9, 10 **cố ý để trống** — đó là phần chỉ chủ sở hữu trả lời được, R3 không điền hộ (`report/README.md` §9).

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | *(R1 điền)* |
| MSSV | *(R1 điền)* |
| Khóa/Lớp | K4 |
| Tên nhóm | C3-1 |
| Vai trò chính | **R1 — Integrator & Release Owner** |
| Repository | https://github.com/NguyenHoang151216/K4-DAY10-C3-1 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Settings & run context | `src/core/config.py`, `write_run_context` | biến môi trường | `Settings`, `data/results/run_context.json` | Hoàn thành |
| Baseline orchestration | `src/pipelines/phase1.py` | raw records | toàn bộ artifact Phase 1 | Hoàn thành (13/13 bước) |
| Corruption orchestration | `src/pipelines/corruption_flow.py` | baseline artifacts | corrupted artifacts | Hoàn thành bước 1–8 |
| Git rules & release | `.gitignore`, `.github/`, commit `data/` | — | repo sạch, artifact được commit | Hoàn thành |

> Bước 9–13 của `corruption_flow.py` (repair → comparison) do R3 nối thêm ở khâu tổng hợp cuối. R1 xác nhận lại phạm vi này trước khi ký.

## 3. Kết quả theo vai trò

| Nhiệm vụ | Artifact | Cách xác minh |
| --- | --- | --- |
| Persist run context | `data/results/run_context.json` | `age_days` không lệch giữa hai process |
| Chạy baseline end-to-end | `data/results/baseline_metrics.json`, `baseline_answers.json` | `python script/run_phase1.py` — 13/13 bước |
| Chạy corruption flow | `data/results/corruption_log.json` | `python script/run_corruption_flow.py` |
| Guard baseline | — | flow raise nếu thiếu baseline artifact, không tự sinh ngầm |

Số liệu baseline quan sát được: raw/clean/Chroma cùng **48 document**; test set và answers cùng **14 sample**; `retrieval_hit_rate = 1.0`, `mean_token_f1 = 1.0`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

`run_phase1.py` và `run_corruption_flow.py` là **hai tiến trình riêng biệt**. Nếu repair replay cleaning tại một thời điểm khác, `age_days` sẽ lệch và phép so hash baseline vs repaired **luôn fail dù code hoàn toàn đúng**.

### Cách triển khai

Ghi `run_date` cùng toàn bộ cấu hình thí nghiệm (`source_query`, `max_results`, `embedding_model`, `top_k`, `freshness_threshold_days`) vào `data/results/run_context.json` ngay ở Phase 1. Corruption/repair đọc lại context này thay vì gọi `datetime.now()`.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | biến môi trường, raw records từ R2 |
| Output | `Settings`, `run_context.json`, toàn bộ artifact `data/` |
| Module phụ thuộc | `crossref.py` (R2), `cleaning.py` (R3), `testset.py`/`quality.py` (R5), `index.py` |
| Module dùng output | mọi module — `Settings.paths` là nguồn đường dẫn duy nhất |
| Điều kiện lỗi | thiếu baseline artifact → raise kèm hướng dẫn chạy Phase 1, không tự sinh baseline ngầm |

### Cách xác minh

```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả thực tế:** Phase 1 hoàn tất 13/13; corruption flow hoàn tất, baseline collection giữ nguyên 48 document.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** repair chạy ở tiến trình khác baseline nên `age_days` có nguy cơ lệch.
- **Phương án đã cân nhắc:** (a) truyền `run_date` qua tham số hàm — vướng contract đóng băng §1.5; (b) persist ra file JSON để cả hai tiến trình đọc chung.
- **Phương án đã chọn:** (b) `run_context.json`.
- **Lý do:** không phải đổi chữ ký hàm nào, và biến toàn bộ cấu hình thí nghiệm thành artifact kiểm chứng được.
- **Bằng chứng:** `data/results/repair_validation.json` cho `core_content_hash_equal: true`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Crossref trả `HTTP 406 Not Acceptable`, cả nhóm không fetch được dữ liệu.
- **Nguyên nhân gốc:** header `Accept: application/vnd.crossref-api-message+json` không còn được chấp nhận.
- **Cách xử lý:** đổi sang `Accept: application/json`.
- **Xác minh:** fetch trả về 48 record có abstract.
- **Hai lỗi tích hợp khác:** MiniLM cache thiếu trọng số; `phase1.py` phải gọi `enrich_metrics` **trước** khi ghi metrics/report, nếu không report thiếu `by_question_type` và cảnh báo judge.

## 7. Hiểu biết về luồng end-to-end

*(R1 tự viết — trả lời 5 câu hỏi trong `report/individual_report.md` bằng lời của mình.)*

## 8. Phân tích kết quả

| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.8571 | 1.0000 |
| `mean_token_f1` | 1.0000 | 0.7174 | 1.0000 |
| `judge_accuracy` | 1.0000 | 0.7143 | 1.0000 |
| `mean_judge_score` | 5.0000 | 3.8571 | 5.0000 |
| Quality check pass | 11/13 | 8/13 | 11/13 |

> `judge_fallback_rate = 1.0` ở cả ba trạng thái → judge là **heuristic**, không phải LLM-as-a-judge.

**Ghi chú cần R1 xác nhận:** notes của R1 ghi `agent_demo_answers.json` có `status = skipped` do thiếu credential, trong khi notes của R4 ghi `status = success` với OpenAI. Cần thống nhất một mô tả đúng trước khi nộp.

## 9. Điều học được và hướng cải thiện

*(R1 tự viết.)*

## 10. Cam kết của thành viên

*(R1 tự đánh dấu và ký. Bản nháp này chưa có giá trị cam kết.)*

**Họ và tên:** *(R1 điền)*
**Ngày xác nhận:** *(R1 điền)*
