# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4 |
| Tên nhóm | C3-1 |
| Repository | https://github.com/NguyenHoang151216/K4-DAY10-C3-1 |
| Ngày hoàn thành | 2026-08-06 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Phan Đức Anh | 2A202601554 | R1 — Integrator & Release Owner | `src/core/config.py`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `script/`, `data/` |
| 2 | Nguyễn Chí Hoàng | 2A202601638 | R2 — Ingestion Owner | `src/ingestion/crossref.py`, `docs/KNOWLEDGE.md` |
| 3 | Phạm Tuấn Anh | 2A202601480 | R3 — Cleaning & Corruption Owner | `src/ingestion/cleaning.py`, `src/ingestion/corruption.py` |
| 4 | Ngô Ngọc Quyền | 2A202601928 | R4 — RAG & Demo Owner | `src/presentation/dashboard.py`, `script/run_dashboard.py`, `script/run_compare_demo.py` |
| 5 | Nguyễn Kỳ Anh | 2A202601558 | R5 — Evaluation & Observability Owner | `src/evaluation/testset.py`, `src/observability/quality.py`, `src/observability/reporting.py` |

Tên và MSSV lấy trực tiếp từ báo cáo cá nhân của từng người trong `report/`, không gán hộ.
**Đủ 5/5 thành viên đã nộp báo cáo cá nhân.**

| Vai | Báo cáo cá nhân |
| --- | --- |
| R1 | `report/individual_report_r1_PhanDucAnh.md` |
| R2 | `report/individual_report_r2_NguyenChiHoang.md` |
| R3 | `report/2A202601480_PhamTuanAnh.md` |
| R4 | `report/individual_report_r4_NgoNgocQuyen.md` |
| R5 | `report/individual_report_r3_NguyenKyAnh.md` |

Đủ tên và MSSV của cả 5 thành viên.

> Ghi chú tên file: báo cáo của R5 (Nguyễn Kỳ Anh) đặt tên `individual_report_r3_NguyenKyAnh.md` theo cách đánh số vai trò của tài liệu BTC, khác với cách đánh số R1–R5 dùng trong repo này. Nội dung bên trong ghi đúng phạm vi Evaluation & Observability. Tên file không theo đúng quy ước `<MSSV>_HoTen.md` nhưng mỗi file đều ghi rõ họ tên và MSSV của chủ sở hữu ở mục 1.

---

## 2. Nguồn dữ liệu và cấu hình thí nghiệm

| Hạng mục | Giá trị |
| --- | --- |
| Nguồn | Crossref REST API (`https://api.crossref.org/works`) |
| Query | `agentic retrieval augmented generation large language model` |
| Filter | `from-pub-date:<hôm nay − 180 ngày>,has-abstract:true` |
| Số record thô | **48** |
| Số row sau cleaning | **48** (0 record bị loại, 0 trùng `paper_id`) |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store | ChromaDB, cosine, `top_k = 4` |
| Test set | **14 câu** — 8 `summary` / 3 `authors` / 3 `date` |
| Seed corruption | `42` |

Ba trạng thái được đánh giá trên **cùng một test set, cùng embedding model, cùng `top_k`, cùng judge**. Chỉ trạng thái dataset thay đổi — đó là điều kiện để phép so sánh có nghĩa.

---

## 3. Kết quả ba trạng thái

Nguồn: `data/results/{baseline,corrupted,repaired}_metrics.json`.

| Metric | Baseline | Corrupted | Repaired | corruption_delta | repair_gap | recovery |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.0000 | 0.8571 | 1.0000 | −0.1429 | 0.0000 | +0.1429 |
| `mean_token_f1` | 1.0000 | 0.7174 | 1.0000 | −0.2826 | 0.0000 | +0.2826 |
| `judge_accuracy` | 1.0000 | 0.7143 | 1.0000 | −0.2857 | 0.0000 | +0.2857 |
| `mean_judge_score` | 5.0000 | 3.8571 | 5.0000 | −1.1429 | 0.0000 | +1.1429 |
| Row count | 48 | 49 | 48 | +1 | 0 | −1 |
| Quality check pass | 11/13 | 8/13 | 11/13 | −3 | 0 | +3 |
| Freshness `is_fresh` | ✅ | ✅ | ✅ | – | – | – |

`repair_gap = 0` ở cả bốn metric → **repair phục hồi hoàn toàn**, không phải phục hồi một phần.

### Phân tích theo `question_type`

| question_type | n | Baseline `token_f1` | Corrupted `token_f1` | Δ |
| --- | --: | ---: | ---: | ---: |
| `summary` | 8 | 1.0000 | 0.6304 | **−0.3696** |
| `authors` | 3 | 1.0000 | 0.6667 | −0.3333 |
| `date` | 3 | 1.0000 | 1.0000 | 0.0000 |

Câu `date` **không suy giảm chút nào**, dù `stale_date` đã lùi 2 paper đi 6 năm. Lý do: `qa.py` trả thẳng `metadata["published"]`, và ground truth của test set được sinh **từ chính dataset đang đo**. Ngày bị làm sai vẫn "khớp" với ground truth của trạng thái đó. Muốn bắt lỗi này thì phải so với snapshot raw, không so nội bộ.

---

## 4. Corruption đã làm gì

Nguồn: `data/results/corruption_log.json` — 48 → 49 row, `rows_changed_verified = 7`.

| Operator | Số row | Mối đe dọa thật | Bị phát hiện bởi |
| --- | --: | --- | --- |
| `drop_latest` | 1 | knowledge base stale | row count |
| `blank_summary` | 2 | mất context, agent bịa | `summary_all_usable` (hard) |
| `inject_noise` | 2 | **data poisoning** | **không check nào** — chỉ lộ qua RAG metric |
| `truncate_title` | 1 | entity resolution failure | `title_min_length` (warn) |
| `stale_date` | 2 | temporal reasoning sai | `freshness_no_stale_rows` (warn) |
| `duplicate_rows` | 2 | retrieval bias | `paper_id_unique` (hard) |

**Hai chuỗi nhân quả:**

1. `duplicate_rows` + `blank_summary` → `paper_id_unique` và `summary_all_usable` **fail (hard)** → `mean_token_f1` tụt từ 1.0000 xuống 0.7174.
2. Repair replay cleaning từ raw snapshot bất biến với đúng `run_date` trong `run_context.json` → quality trở lại **11/13 y hệt baseline** → cả 4 metric về đúng giá trị baseline (`repair_gap = 0`).

Bằng chứng repair: `data/results/repair_validation.json` cho `core_content_hash_equal: true` — baseline và repaired có cùng hash `7b3243b2308b272d` trên 6 cột nội dung lõi.

---

## 5. Ba điều phải nói rõ để không kết luận quá mức

**1. `judge_accuracy` và `mean_judge_score` KHÔNG phải LLM-as-a-judge.**
`judge_fallback_rate = 1.0000` ở cả ba trạng thái — toàn bộ 14 sample rơi về heuristic. `_judge_answer` tạo client LLM mới cho từng sample và bắt `except Exception` trần, nên khi không có credential hợp lệ thì pipeline vẫn xanh và metric vẫn đẹp. Hai cột đó chỉ là ngưỡng đặt trên `token_f1`, **không mang thêm thông tin độc lập**. Kết luận của nhóm dựa vào `retrieval_hit_rate` và `mean_token_f1`.

**2. Hai warn check fail ở CẢ baseline lẫn repaired — đó là giới hạn của nguồn, không phải hậu quả corruption.**
- `categories_present_ratio`: **48/48 row không có categories** vì Crossref thường không trả field `subject`. Hệ quả kéo theo: `build_test_set` báo `categories 0/2`, test set còn 14 câu thay vì 16.
- `no_future_published`: 1 paper có `published = 2026-12-01`, tức **sau `run_date`**. Crossref ghi ngày phát hành số tạp chí trước khi tới hạn. Nhóm **không clip `age_days` về 0** vì clip là bóp méo dữ liệu.

**3. Corruption quy mô nhỏ không vượt được check dạng tỉ lệ.**
`blank_summary` chỉ chạm 2/49 row = 0.041, trong khi ngưỡng cho phép là 0.10; `stale_date` cũng 0.041 so với ngưỡng 0.20. Check **không fail không có nghĩa dữ liệu còn sạch** — có thể chỉ là ngưỡng quá lỏng so với quy mô lỗi. Chỉ check đếm-không-khoan-nhượng (`paper_id_unique`) mới bắt được.

Riêng `inject_noise` thì khác về bản chất: nội dung vẫn đúng kiểu, đúng độ dài, đúng schema, nên **không rule-based check nào có thể bắt**. Nó chỉ lộ qua RAG metric. Đây là luận điểm trung tâm của bài lab — quality check dạng rule không thay thế được semantic monitoring.

---

## 6. Cách tái lập

```powershell
uv sync                                   # hoặc: python -m pip install -e .
Copy-Item .env.example .env               # điền credential của đúng một provider
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
uv run python script/run_dashboard.py
uv run python script/run_compare_demo.py
```

Repair **không gọi lại Crossref**: nó replay cleaning từ `data/raw/crossref_records.json` với `run_date` đọc từ `data/results/run_context.json`. Đây là lý do raw snapshot bất biến là điều kiện cần để sửa được lỗi thay vì che lỗi.

## 7. Artifact đối chiếu

| Nhóm | Đường dẫn |
| --- | --- |
| Raw | `data/raw/crossref_{response,records}.json` |
| Clean | `data/clean/papers_clean{,_corrupted,_repaired}.{csv,json}` |
| Embedding manifest | `data/embeddings/papers_embeddings{,_corrupted,_repaired}.json` |
| Test set | `data/eval/test_set.json` |
| Metrics & answers | `data/results/{baseline,corrupted,repaired}_{metrics,answers}.json` |
| Corruption | `data/results/corruption_log.json`, `data/quality/corruption_impact.json` |
| Repair | `data/results/repair_validation.json` |
| Quality & freshness | `data/quality/*.json` |
| Report | `data/reports/{phase1_report,corruption_report}.md` |
| Demo | `docs/dashboard.html`, `script/run_compare_demo.py` |
| Kiến thức | `docs/KNOWLEDGE.md` |

`data/chroma/` **không được commit** — là sqlite binary, rebuild được từ embedding manifest.

## 8. Definition of Done

- [x] Không còn `NotImplementedError` trong `src/`
- [x] Phase 1 chạy end-to-end
- [x] Corruption flow chạy end-to-end 13 bước (corrupt → đo → repair → so sánh)
- [x] 3 collection `papers-baseline` / `papers-corrupted` / `papers-repaired` tách biệt; baseline được verify là không bị mutate sau khi build 2 collection kia
- [x] Test set giống hệt nhau ở cả 3 trạng thái (14 sample)
- [x] `corruption_log.json` đủ 6 operator kèm ID và hash
- [x] `agent_demo_answers.json` có kết quả agent
- [x] Corruption làm **2 hard check** fail (`paper_id_unique`, `summary_all_usable`)
- [x] Corruption làm **4 metric** giảm rõ rệt
- [x] Repaired pass toàn bộ hard check
- [x] `repair_validation.json` cho `core_content_hash_equal: true`
- [x] Số trong `.md` khớp `.json`
- [x] `docs/dashboard.html` mở được, inventory và số đọc trực tiếp từ artifact
- [x] `docs/KNOWLEDGE.md` hoàn chỉnh
- [x] Không `.env`, API key hay email cá nhân trong Git
- [x] Không hardcode absolute path
- [x] `data/chroma/` đã gitignore và đã gỡ khỏi index
- [x] Rebuild được clean data từ raw snapshot mà không gọi lại Crossref
- [x] `judge_fallback_rate = 1.0` → báo cáo ghi rõ là heuristic, **không** gọi là LLM-as-a-judge
- [x] Đủ **5/5** bản `individual_report`, mỗi bản do chính chủ sở hữu viết và ký
