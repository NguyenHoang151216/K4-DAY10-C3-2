# GHI CHÚ KỸ THUẬT VÀ NHẬT KÝ R4 (RAG & DEMO OWNER)

> **Người thực hiện:** Role 4 (R4)  
> **Nhánh Git:** `QUYEN`   
> **Dự án:** K4-DAY10-C3-2 - Data Pipeline & Data Observability Lab

---

## 📌 GIAI ĐOẠN CP0: Khởi động & Nắm bắt RAG Contract

### 1. Phân tích cấu trúc module `src/retrieval/`
- **`src/retrieval/embeddings.py`**: Sử dụng `SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")` sinh vector 384-dimensional.
- **`src/retrieval/index.py`**: Quản lý ChromaDB vector store.
  - **Quy tắc cứng:** `LocalEmbeddingIndex.build(df, settings, manifest_path)` đọc 9 cột metadata cố định từ clean DataFrame (`summary`, `authors_joined`, `categories_joined`, `published`, `abs_url`, `pdf_url`, v.v.).
  - **Né Bẫy 2:** Metadata Chroma từ chối `None`, `NaN`, `datetime`. Đã thống nhất với R3 rằng mọi trường rỗng phải fill `""`, ngày đăng giữ dạng chuỗi ISO `YYYY-MM-DD`, và drop cột `published_dt`.
  - **Né Bẫy 7:** `index.py` tự lưu manifest và đặt tên collection (`papers-baseline`, `papers-corrupted`, `papers-repaired`). Không được sửa `index.py`.

### 2. Thiết kế hệ thống UI Demo (R4 sở hữu độc quyền)
- **Tier 1 — `docs/dashboard.html` (`src/presentation/dashboard.py`):**
  - Sinh file HTML tĩnh tự chứa (Self-contained HTML).
  - Dùng Inline CSS & Inline SVG icons. Không dùng CDN/JS bên ngoài để đảm bảo 100% offline & zero dependency conflict.
  - Đọc từ các artifact trong `data/` (`baseline_metrics.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `quality_report`, `freshness_report.json`).
- **Tier 2 — `script/run_compare_demo.py`:**
  - CLI so sánh trực tiếp câu trả lời của Agent / Document Retrieval trên cả 3 Chroma collection cùng lúc.

---

## 📌 GIAI ĐOẠN CP3 & CP4: Tổng kết Phase 1 Baseline & Chuẩn bị CP5

### 1. Kết quả thực thi Baseline Index & RAG Agent
- **Chroma Count:** Collection `papers-baseline` chứa khớp đúng 100% **48 vector bài báo** từ `data/clean/papers_clean.csv`.
- **LLM Setup:** Chuyển đổi thành công sang **OpenAI API (`LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini`)**, giải quyết dứt điểm lỗi quota HTTP 429 của Gemini free tier.
- **Manifest Portability:** Chuẩn hóa trường `persist_path` trong `data/embeddings/papers_embeddings.json` về đường dẫn tương đối `"data/chroma"`, loại bỏ hoàn toàn đường dẫn tuyệt đối local.
- **Agent Demo Outputs:** Xuất thành công tệp `data/results/agent_demo_answers.json` với 100% câu trả lời thật (`"status": "success"`).
- **Dashboard UI (`docs/dashboard.html`):** Sinh file báo cáo HTML tĩnh hoàn chỉnh với các chỉ số baseline thật (Hit Rate 100%, Token F1 100%, Judge Score 5.0/5), xử lý linh hoạt trạng thái chờ Phase 2 không bị lỗi `N/A`.

### 2. Chuẩn bị tập câu hỏi truy vấn cho Corrupted Testing (CP5)
- **Query 1 (Test Blank Summary / Noise Injection):** *"Summarize the paper on autonomous agent architectures."*
- **Query 2 (Test Truncate Title / Lookup Fail):** *"Who authored the paper on deep retrieval augmented generation?"*
- **Query 3 (Test Drop Latest / Stale Date):** *"What categories are associated with RAG models?"*

---

## 📅 Nhật ký Checkpoint
- [x] **CP0 (00:00 - 00:30):** Khởi tạo nhánh, nghiên cứu contract `src/retrieval/`, phác thảo khung `src/presentation/dashboard.py` và chuẩn bị tệp nhật ký R4.
- [x] **CP1 (00:30 - 01:05):** Đã khởi tạo script `script/inspect_clean_data.py` để tự động kiểm tra 16 cột contract & 5 mẫu `text_for_embedding`. Đã hoàn thiện layout HTML Dashboard trong `src/presentation/dashboard.py` và sinh thử file `docs/dashboard.html`.
- [x] **CP2 (01:05 - 01:35):** Build `papers-baseline` Chroma index thành công qua `script/run_cp2_baseline.py`, smoke test semantic search & exact lookup chính xác, xuất file `data/results/agent_demo_answers.json`.
- [x] **CP3 (01:35 - 02:00):** Verify baseline count 48/48 & sinh `docs/dashboard.html` thật với 100% Hit Rate & Token F1.
- [x] **CP4 (02:00 - 02:15):** Nghỉ 15 phút, cập nhật nhật ký kỹ thuật R4 & chuẩn bị tập câu hỏi test cho CP5.
- [ ] **CP5 (02:15 - 03:15):** Build `papers-corrupted` collection, đo tác động suy giảm chất lượng retrieval.
- [ ] **CP6 (03:15 - 04:00):** Build `papers-repaired`, hoàn thiện Dashboard Tier 1 & Compare CLI Tier 2, dẫn buổi Live Demo.
