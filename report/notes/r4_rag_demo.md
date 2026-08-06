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

## 📅 Nhật ký Checkpoint
- [x] **CP0 (00:00 - 00:30):** Khởi tạo nhánh, nghiên cứu contract `src/retrieval/`, phác thảo khung `src/presentation/dashboard.py` và chuẩn bị tệp nhật ký R4.
- [x] **CP1 (00:30 - 01:05):** Đã khởi tạo script `script/inspect_clean_data.py` để tự động kiểm tra 16 cột contract & 5 mẫu `text_for_embedding`. Đã hoàn thiện layout HTML Dashboard trong `src/presentation/dashboard.py` và sinh thử file `docs/dashboard.html`.
- [ ] **CP2 (01:05 - 01:35):** Build `papers-baseline` Chroma index, smoke test retrieval, xuất `agent_demo_answers.json`.
- [ ] **CP3 (01:35 - 02:00):** Verify baseline count & sinh `docs/dashboard.html` thử nghiệm.
- [ ] **CP4 (02:00 - 02:15):** Nghỉ 15 phút, cập nhật note.
- [ ] **CP5 (02:15 - 03:15):** Build `papers-corrupted` collection, đo tác động suy giảm chất lượng retrieval.
- [ ] **CP6 (03:15 - 04:00):** Build `papers-repaired`, hoàn thiện Dashboard Tier 1 & Compare CLI Tier 2, dẫn buổi Live Demo.
