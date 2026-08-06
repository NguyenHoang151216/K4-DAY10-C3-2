# Member Role Report — Day 10 — R4 RAG & Demo Owner

> ⚠️ **BẢN NHÁP — CHƯA HỢP LỆ KHI CHƯA CÓ CHỮ KÝ CỦA CHỦ SỞ HỮU.**
> R3 tổng hợp bản này **từ chính `report/notes/r4_rag_demo.md`** do R4 viết.
> **R4 phải:** điền mục 1, tự viết mục 7 / 9 / 10 bằng lời của mình, rà lại mục 3–6 và đổi tên file thành `<MSSV>_HoTen.md`.
> Mục 7, 9, 10 **cố ý để trống** — R3 không điền hộ (`report/README.md` §9).

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | *(R4 điền)* |
| MSSV | *(R4 điền)* |
| Khóa/Lớp | K4 |
| Tên nhóm | C3-1 |
| Vai trò chính | **R4 — RAG & Demo Owner** |
| Nhánh Git | `QUYEN` |
| Repository | https://github.com/NguyenHoang151216/K4-DAY10-C3-1 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

| Module/deliverable | File/hàm phụ trách | Input | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Build 3 collection | `LocalEmbeddingIndex.build` | clean DataFrame | `papers-baseline` / `papers-corrupted` / `papers-repaired` | Hoàn thành |
| Agent demo | `src/retrieval/agent.py` | collection baseline | `data/results/agent_demo_answers.json` | Hoàn thành |
| Demo Tier 1 | `src/presentation/dashboard.py`, `script/run_dashboard.py` | JSON trong `data/` | `docs/dashboard.html` | Hoàn thành |
| Demo Tier 2 | `script/run_compare_demo.py` | 3 collection | so sánh câu trả lời cạnh nhau | Hoàn thành |

## 3. Kết quả theo vai trò

| Nhiệm vụ | Artifact | Cách xác minh |
| --- | --- | --- |
| Index baseline | `data/embeddings/papers_embeddings.json` | Chroma count = **48** = số row clean |
| Index corrupted / repaired | `papers_embeddings_{corrupted,repaired}.json` | 49 / 48 document, tách biệt hoàn toàn |
| Agent demo | `data/results/agent_demo_answers.json` | notes ghi 100% `status: success` với `gpt-4o-mini` |
| Dashboard | `docs/dashboard.html` | mở bằng trình duyệt, số đọc trực tiếp từ artifact |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Kết quả của lab nằm rải rác trong hơn 10 file JSON. Người xem demo không thể đọc JSON để thấy corruption gây hại ra sao — cần một mặt hiển thị **đọc thẳng từ artifact thật**, không gõ số bằng tay.

### Cách triển khai

- **Tier 1 — `docs/dashboard.html`:** Python thuần đọc JSON trong `data/` rồi sinh HTML tĩnh self-contained. **Inline CSS + inline SVG, không CDN, không thêm dependency** → không đụng `uv.lock`, không có nguy cơ conflict lockfile, mở được 100% offline.
- **Tier 2 — `script/run_compare_demo.py`:** nhập một câu hỏi, query cả 3 collection, in 3 câu trả lời kèm document retrieved cạnh nhau. Đây là khoảnh khắc thuyết phục nhất khi demo: cùng một câu hỏi, dữ liệu hỏng trả lời sai, repair xong trả lời đúng lại.
- **Manifest portability:** chuẩn hoá `persist_path` trong embedding manifest về đường dẫn **tương đối** `"data/chroma"`, loại bỏ absolute path của máy local.

### Hai ràng buộc cứng đã ghi nhận từ CP0

1. `index.py` đọc **9 cột metadata cố định** từ clean DataFrame — đã thống nhất với R3 về schema.
2. Chroma metadata từ chối `None` / `NaN` / `datetime` (Bẫy 2) → mọi trường rỗng phải là `""`, `published` giữ dạng chuỗi ISO `YYYY-MM-DD`, cột `published_dt` phải bị drop.
3. **Không sửa `index.py`** (Bẫy 7) — nó tự ghi manifest và tự derive tên collection.

### Cách xác minh

```bash
python script/run_dashboard.py
python script/run_compare_demo.py
```

- **Kết quả thực tế:** dashboard sinh thành công; inventory và mọi chỉ số đọc trực tiếp từ artifact.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** chọn công nghệ cho UI demo khi thời gian còn ít.
- **Phương án đã cân nhắc:** (a) Streamlit/Gradio — đẹp, nhanh có tương tác; (b) HTML tĩnh sinh bằng Python thuần.
- **Phương án đã chọn:** (b).
- **Lý do:** thêm dependency lúc gấp là rủi ro conflict `uv.lock` không đáng đánh đổi. HTML tĩnh mở được offline, không cần chạy server lúc demo, và không thể hỏng vì lỗi môi trường của máy trình chiếu.
- **Bằng chứng:** `docs/dashboard.html` mở trực tiếp bằng trình duyệt, zero dependency mới.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** `HTTP 429` quota exceeded khi gọi LLM qua Gemini free tier.
- **Nguyên nhân gốc:** `_judge_answer` tạo client LLM mới cho **từng sample**; với 14 câu × 3 trạng thái cộng agent demo, số lần gọi vượt ~10 RPM của free tier.
- **Cách xử lý:** chuyển provider sang OpenAI (`LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini`).
- **Xác minh:** `agent_demo_answers.json` ghi 100% `status: success`.
- **Điều học được:** `except Exception` trần trong `_judge_answer` **nuốt lỗi 429** — pipeline vẫn xanh và metric vẫn đẹp trong khi judge đã chết. Metric phải tự khai báo độ tin cậy của nó, nếu không người đọc sẽ tin nhầm.

## 7. Hiểu biết về luồng end-to-end

*(R4 tự viết.)*

## 8. Phân tích kết quả

| Trạng thái | Collection | Số document | `retrieval_hit_rate` |
| --- | --- | ---: | ---: |
| Baseline | `papers-baseline` | 48 | 1.0000 |
| Corrupted | `papers-corrupted` | 49 | 0.8571 |
| Repaired | `papers-repaired` | 48 | 1.0000 |

Ba collection **tách biệt hoàn toàn**; `papers-baseline` được verify là không bị mutate sau khi build hai collection kia — điều kiện bắt buộc để phép so sánh có nghĩa.

`retrieval_hit_rate` tụt là do `drop_latest` (xoá hẳn document khỏi index) và `truncate_title` (phá exact-title lookup ở `qa.py`). `blank_summary` và `inject_noise` **không** hạ hit rate — chúng chỉ hạ `token_f1`, vì document vẫn được tìm thấy, chỉ là nội dung đã sai.

## 9. Điều học được và hướng cải thiện

*(R4 tự viết.)*

## 10. Cam kết của thành viên

*(R4 tự đánh dấu và ký. Bản nháp này chưa có giá trị cam kết.)*

**Họ và tên:** *(R4 điền)*
**Ngày xác nhận:** *(R4 điền)*
