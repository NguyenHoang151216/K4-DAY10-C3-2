# R1 — Integrator & Release Owner

## CP4 — Ghi chú sau baseline

- Quyết định kỹ thuật: persist `run_date` và toàn bộ cấu hình thí nghiệm vào `data/results/run_context.json`; corruption/repair phải đọc lại context này để `age_days` không lệch giữa hai process.
- Kết quả baseline: pipeline hoàn tất đủ `13/13`, raw/clean/Chroma cùng có 48 document, quality hard checks pass, freshness pass; test set và answers cùng có 14 sample.
- Metrics quan sát: `retrieval_hit_rate=1.0`, `mean_token_f1=1.0`, `judge_accuracy=1.0`, `mean_judge_score=5`; tuy nhiên `judge_fallback_rate=1.0` nên kết quả judge là heuristic, không được gọi là LLM-as-a-judge.
- Giới hạn dữ liệu: test set có 8 summary, 3 authors và 3 date question nhưng thiếu 2 categories question vì các record được chọn không có category ground truth dùng được.
- Agent smoke test được pipeline bọc lỗi đúng yêu cầu nhưng artifact hiện ghi `status=skipped` do chưa có credential LLM; cần chạy lại khi nhóm cấu hình provider để đạt trọn mục Agent trong rubric.
- Lỗi tích hợp đã xử lý: Crossref HTTP 406 cần `Accept: application/json`; MiniLM cache thiếu trọng số; `phase1.py` cần gọi `enrich_metrics` trước khi ghi metrics/report.
- Git/release: `data/chroma/` đã được ignore và bỏ track vì là binary rebuild được; baseline artifacts đã được commit, còn collection local `papers-baseline` có 48 document để demo.

## Việc cần giữ nguyên khi sang corruption

- Không refresh Crossref source hoặc test set giữa ba trạng thái.
- Không ghi đè collection `papers-baseline` khi build corrupted/repaired.
- Mọi số liệu trong report phải đọc từ JSON artifact, không chép số thủ công.

## CP5 — Corruption có kiểm soát

- `run_corruption_flow.py` hoàn tất đủ `8/8`; guard xác nhận baseline artifact tồn tại và không tự chạy Phase 1 ngầm.
- Corruption deterministic với `seed=42`: 48 baseline row → 49 corrupted row, đủ 6 operator và 7 row được xác minh thực sự đổi nội dung.
- Collection được tách đúng: `papers-baseline=48`, `papers-corrupted=49`; hash baseline artifact và baseline collection count không đổi sau flow.
- Quality hard failures: `paper_id_unique`, `summary_all_usable`; freshness chuyển từ pass sang fail.
- Metrics giảm so với baseline: retrieval hit `1.0000 → 0.8571`, token F1 `1.0000 → 0.7174`, judge accuracy `1.0000 → 0.7143`, mean judge score `5.0000 → 3.8571`.
- `corruption_impact.json` ghi detection rate `0.8333`; `inject_noise` là operator không bị structural quality/freshness bắt, chỉ biểu hiện qua metric RAG.
- Judge vẫn ở chế độ heuristic với `judge_fallback_rate=1.0`; không diễn giải judge metrics như LLM-as-a-judge.
