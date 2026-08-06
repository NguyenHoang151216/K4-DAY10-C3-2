# Báo cáo cá nhân — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Phan Đức Anh |
| MSSV | 2A202601554 |
| Khóa/Lớp | K4 |
| Tên nhóm | C3-1 |
| Vai trò chính | R1 — Integrator & Release Owner |
| Repository | https://github.com/NguyenHoang151216/K4-DAY10-C3-2 |
| Ngày hoàn thành báo cáo | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cấu hình dùng chung | `src/core/config.py`, `load_settings()` | Biến môi trường và thư mục dự án | `Settings`, toàn bộ đường dẫn artifact và tên collection | Hoàn thành |
| Baseline orchestration | `src/pipelines/phase1.py`, `write_run_context()`, `main()` | Raw snapshot, cấu hình, test set | Baseline clean data, index, metrics, quality, freshness và report | Hoàn thành, chạy đủ 13/13 bước |
| Corruption orchestration | `src/pipelines/corruption_flow.py` bước 1–8 | Baseline và test set bất biến | Corrupted data/index/metrics/quality/freshness | Hoàn thành |
| Repair orchestration | `src/pipelines/corruption_flow.py` bước 9–14 | Raw snapshot và `run_context.json` | Repaired data/index/metrics, `repair_validation.json` | Hoàn thành phần repair; toàn flow đang dừng 13/14 do report của R5 |
| Git và release | `.gitignore`, `.github/`, `data/`, `report/notes/r1_integrator.md` | Thay đổi từ các role | Nhánh tích hợp, quy tắc commit artifact, ghi chú R1 | Hoàn thành đến CP5; commit dữ liệu CP6 chờ comparison report |
| Báo cáo nhóm | `report/group_report.md` | `report/notes/r1` đến `r5` | Báo cáo chung | Chưa chốt vì CP6 chưa đủ comparison report |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra contract tích hợp | R2 ingestion và R3 cleaning/corruption | Xác nhận repair gọi `load_raw_records()` rồi `build_clean_dataframe()` thay vì sửa corrupted data bằng tay |
| Tích hợp observability | R5 evaluation/observability | Gọi `enrich_metrics()` cho cả ba trạng thái, giữ cùng test set và truyền đúng bảy payload vào `generate_corruption_report()` |
| Chuẩn bị demo ba trạng thái | R4 retrieval/presentation | Duy trì ba collection riêng: `papers-baseline`, `papers-corrupted`, `papers-repaired` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Persist cấu hình thí nghiệm | `data/results/run_context.json` | Lưu `run_date`, query, filter, model, `top_k` và freshness threshold | Đọc JSON sau khi chạy Phase 1 |
| Chạy baseline end-to-end | `script/run_phase1.py` | 48 raw record → 48 clean row; baseline metrics đều đạt 1.0, mean judge score 5 | Chạy script và kiểm tra `data/results/baseline_metrics.json` |
| Tạo corruption có kiểm soát | `script/run_corruption_flow.py` | 6 operator, 48 → 49 row, 7 row thay đổi được xác minh | `data/results/corruption_log.json` |
| Đo tác động corruption | `corrupted_metrics.json`, `corrupted_quality.json` | Retrieval hit 0.8571, token F1 0.7174; hard check `paper_id_unique` và `summary_all_usable` fail | Đối chiếu các artifact JSON |
| Repair từ nguồn bất biến | `papers_clean_repaired.*`, `papers_embeddings_repaired.json` | Phục hồi 48 row và build collection `papers-repaired` độc lập | Manifest, clean JSON và Chroma collection count |
| Chứng minh repair đúng nội dung | `data/results/repair_validation.json` | Schema bằng nhau và `core_content_hash_equal=true` với hash `7b3243b2308b272d` | Đọc artifact validation |
| Re-evaluate repaired | `repaired_metrics.json`, `repaired_quality.json`, `freshness_report_repaired.json` | Bốn metric trở lại baseline, hard quality pass, freshness true | Đối chiếu ba artifact |

Output quan trọng nhất của phần tích hợp là `data/results/repair_validation.json`. Artifact này chứng minh repaired dataset được tái tạo từ raw snapshot với cùng `run_date`, có cùng 48 dòng, cùng 16 cột và cùng core-content hash với baseline. Đây là bằng chứng mạnh hơn việc chỉ nhìn metric, vì metric giống nhau chưa đảm bảo toàn bộ dữ liệu đã được phục hồi đúng.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline gồm nhiều module do các thành viên khác nhau phát triển. R1 phải ghép chúng thành một luồng chạy có thứ tự, có artifact rõ ràng và có thể tái hiện. Rủi ro chính là baseline bị ghi đè khi corruption, `run_date` thay đổi giữa hai process làm `age_days` lệch, test set bị tạo lại khiến phép so sánh mất công bằng, hoặc repaired data chỉ được sửa trực tiếp từ corrupted data thay vì khôi phục từ nguồn tin cậy.

### Cách triển khai

Phase 1 persist `run_context.json`, đọc hoặc fetch raw records, cleaning, quality/freshness, build baseline index, giữ hoặc tạo test set, evaluation, agent smoke test và tạo report. Corruption flow trước tiên kiểm tra đầy đủ baseline artifact; nếu thiếu thì dừng và hướng dẫn chạy Phase 1, không tự tạo baseline ngầm. Luồng chụp SHA-256 của các artifact baseline, tạo corrupted dataframe bằng seed 42, build collection riêng và đánh giá lại trên test set cũ.

Ở bước repair, pipeline đọc `run_date` đã persist, reload đúng `data/raw/crossref_records.json`, rồi gọi lại cleaning. Repaired dataframe được ghi ra CSV/JSON, build collection `papers-repaired`, chạy lại evaluation, quality và freshness. Cuối cùng pipeline so schema, row count, core-content hash và metric gap với baseline. Hash baseline được chụp lại sau flow để bảo đảm corruption/repair không sửa artifact gốc.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Raw snapshot theo `PaperRecord`, clean baseline 16 cột, evaluation set có `ground_truth_doc_ids`, `run_context.json` |
| Output | Ba trạng thái clean/index/metrics, quality/freshness JSON, corruption log, repair validation và comparison report |
| Module phụ thuộc | `ingestion.crossref`, `ingestion.cleaning`, `ingestion.corruption`, `retrieval.index`, `evaluation.metrics`, `observability.quality`, `observability.reporting` |
| Module sử dụng output | Dashboard/compare CLI của R4, report của R5 và báo cáo nhóm |
| Điều kiện lỗi cần xử lý | Thiếu baseline, collection sai tên hoặc sai count, test set rỗng, corruption không làm metric giảm, repaired hash khác baseline, metric không phục hồi, report function chưa triển khai |

### Cách xác minh

```powershell
$env:REFRESH_SOURCE='false'
$env:REFRESH_TEST_SET='false'
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** script đầu hoàn tất 13/13; script sau hoàn tất 14/14, có đủ baseline/corrupted/repaired artifact và comparison report.
- **Kết quả thực tế:** script đầu hoàn tất 13/13. Script sau hoàn thành corruption, repair, validation và re-evaluation nhưng dừng ở 13/14 vì `generate_corruption_report()` của R5 còn `NotImplementedError`.
- **Artifact/log:** `data/results/run_context.json`, `data/results/*_metrics.json`, `data/results/repair_validation.json`, `data/quality/*.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** `age_days` phụ thuộc thời điểm chạy. Nếu baseline và repaired dùng hai `datetime.now()` khác nhau, cùng một raw record vẫn có thể tạo ra dataframe khác.
- **Các phương án đã cân nhắc:** (1) tính lại `run_date` ở mỗi script; (2) copy baseline thành repaired; (3) persist `run_date` của baseline và replay cleaning từ raw với giá trị đó.
- **Phương án đã chọn:** Persist `run_date` trong `run_context.json`, sau đó repair bằng cách reload raw snapshot và chạy lại cleaning với đúng giá trị đã lưu.
- **Lý do:** Cách này vừa tái hiện được kết quả, vừa chứng minh repair xuất phát từ nguồn bất biến; không che lỗi bằng cách copy baseline hoặc sửa corrupted data thủ công.
- **Bằng chứng quyết định phù hợp:** `repair_validation.json` cho `baseline_core_content_hash` và `repaired_core_content_hash` cùng bằng `7b3243b2308b272d`; `schema_equal`, `row_count_equal` và `core_content_hash_equal` đều là `true`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `Package 'day10-data-observability-lab-student' requires a different Python: 3.14.6 not in '<3.14,>=3.11'`.
- **Lệnh hoặc bước tái hiện:** chạy `python -m pip install -e .` trong virtual environment dùng Python 3.14.6.
- **Nguyên nhân gốc:** `pyproject.toml` chỉ hỗ trợ Python từ 3.11 đến dưới 3.14, còn virtual environment ban đầu được tạo bằng Python 3.14.6. Máy cũng chưa nhận lệnh `py`, nên không thể chọn Python 3.12 qua Python Launcher.
- **Cách xử lý:** cài và dùng `uv` để quản lý interpreter/môi trường đúng constraint của dự án, sau đó chạy pipeline trong môi trường dự án.
- **Cách xác minh sau khi sửa:** Phase 1 chạy đủ 13/13 và corruption/repair chạy được đến bước tạo report.
- **Điều học được:** Virtual environment không làm hạ phiên bản Python; nó kế thừa interpreter dùng để tạo môi trường. Cần chọn đúng interpreter trước khi cài dependency.

Blocker hiện chưa xử lý xong thuộc dependency liên vai trò:

- **Phạm vi bị ảnh hưởng:** `data/reports/corruption_report.md`, bước 14 của flow, commit dữ liệu CP6 và báo cáo nhóm cuối.
- **Những gì đã loại trừ:** Đã fetch `origin/main` mới nhất và kiểm tra nhánh Role 5; hàm `generate_corruption_report()` vẫn chủ động ném `NotImplementedError`. Các repaired artifact, hash, quality, freshness và metrics đều đã sinh thành công trước lỗi.
- **Bước tiếp theo:** Role 5 triển khai hàm theo contract, merge vào main; R1 cập nhật nhánh rồi chạy lại `script/run_corruption_flow.py`, kiểm tra 14/14 và commit dữ liệu lần hai.

## 7. Hiểu biết về luồng end-to-end

1. Crossref trả về response; R2 parse thành danh sách `PaperRecord` và ghi raw snapshot. R3 cleaning text, chuẩn hóa list/ngày, dedupe, tính `summary_chars`, `age_days` và `text_for_embedding`. R4/Retrieval chuyển mỗi row thành document, tạo embedding MiniLM và lưu vào collection Chroma tương ứng.
2. Evaluation set chứa câu hỏi, ground truth answer và `ground_truth_doc_ids`. Pipeline hỏi trên index, đối chiếu ID lấy được để tính retrieval hit, so answer với ground truth bằng token F1 và judge. Vì vậy có thể tách lỗi retrieval lấy nhầm document khỏi lỗi answer sai dù lấy đúng document.
3. Quality checks đo tính đầy đủ, hợp lệ, duy nhất và khả dụng của schema/nội dung. Freshness tập trung vào thời gian, ví dụ paper mới nhất/cũ nhất, `age_days`, stale ratio và trạng thái `is_fresh`. Hai lớp bổ sung cho nhau; schema hợp lệ không đồng nghĩa dữ liệu còn mới.
4. Cùng test set là điều kiện để so sánh công bằng. Nếu mỗi trạng thái có câu hỏi hoặc ground-truth ID khác nhau, delta metric có thể do bộ kiểm tra đổi chứ không phải do corruption/repair.
5. Repair thành công cần đồng thời có `core_content_hash_equal=true`, schema/row count khớp, repaired hard checks pass, freshness trở lại true và metric trên cùng test set phục hồi về baseline. Chỉ một trong các tín hiệu này chưa đủ để kết luận.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.8571 | 1.0000 | Corruption làm mất document mục tiêu khỏi top-k; repair phục hồi hoàn toàn |
| `mean_token_f1` | 1.0000 | 0.7174 | 1.0000 | Blank/noise/truncated content làm answer lệch rõ nhất |
| `judge_accuracy` | 1.0000 | 0.7143 | 1.0000 | Phục hồi hoàn toàn, nhưng judge đang là heuristic |
| `mean_judge_score` | 5.0000 | 3.8571 | 5.0000 | Phục hồi hoàn toàn, không được diễn giải là LLM-as-a-judge |
| Hard quality checks | PASS | FAIL: 2 check | PASS | `paper_id_unique` và `summary_all_usable` fail ở corrupted rồi pass lại |
| Freshness status | `true` | `false` | `true` | `stale_date`/`drop_latest` tạo tín hiệu freshness có thể quan sát |

`judge_fallback_rate=1.0` ở cả ba trạng thái, nên các metric judge trong bảng đến từ fallback heuristic dựa trên answer similarity, không phải một LLM judge thực sự. Việc ghi rõ giới hạn này tránh báo cáo quá mức độ tin cậy của kết quả.

### Kết luận từ số liệu

1. `drop_latest`, `blank_summary`, `truncate_title` và duplicate/noise có kiểm soát → hard quality fail và freshness chuyển false → retrieval hit giảm 0.1429, token F1 giảm 0.2826, judge accuracy giảm 0.2857.
2. Reload raw snapshot rồi cleaning với cùng `run_date` → core hash và hard checks phục hồi, freshness trở lại true → cả bốn metric trở về đúng baseline.

Tác động rõ nhất trên agent là nhóm corruption làm hỏng hoặc loại nội dung liên quan trực tiếp tới test set. Ví dụ câu `summary-03` vẫn retrieve đúng document nhưng summary bị blank nên token F1 bằng 0; câu `authors-01` bị mất document mục tiêu nên retrieval miss và answer sai. `inject_noise` đáng chú ý vì structural check không phát hiện trực tiếp, dù tác động của corruption tổng thể vẫn hiện ra ở metric RAG.

Kết quả khác kỳ vọng là quality check `categories_present_ratio` cảnh báo ở cả baseline và repaired vì raw snapshot hiện không cung cấp category usable; đây không phải lỗi do corruption. Ngoài ra judge fallback 100% khiến kết quả không đạt ý nghĩa LLM-as-a-judge như tên metric gợi ý. Hai điểm này được kiểm tra bằng `baseline_quality.json`, `repaired_quality.json` và trường `judge_mode` trong metrics.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Một pipeline tái hiện được cần persist cả dữ liệu nguồn lẫn context thời gian/cấu hình; lưu raw snapshot một mình chưa đủ.
2. Observability phải kết hợp hard checks, warning signals, freshness và downstream metrics. Một operator như data poisoning có thể lọt qua schema checks nhưng vẫn làm RAG suy giảm.
3. Repair đáng tin cậy phải quay về nguồn bất biến và được chứng minh bằng nhiều tầng bằng chứng, không chỉ bằng một điểm metric đẹp.

### Nếu có thêm thời gian

Tôi sẽ bổ sung semantic-drift check bằng cosine similarity giữa embedding centroid của baseline và trạng thái mới. Mục tiêu là phát hiện `inject_noise`, operator hiện không bị structural quality/freshness bắt. Cách đo là chạy lại cùng seed, kiểm tra drift check chỉ fail ở corrupted nhưng pass ở baseline và repaired, sau đó đối chiếu với thay đổi retrieval/token F1.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phan Đức Anh  
**Ngày xác nhận:** 2026-08-06
