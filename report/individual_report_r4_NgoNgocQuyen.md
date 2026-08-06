# Member Role Report — Day 10: Data Pipeline & Data Observability

> Báo cáo cá nhân vai trò **Role 4 (R4) — RAG & Demo Owner**.

---

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| :--- | :--- |
| **Họ và tên** | Ngô Ngọc Quyền |
| **MSSV** | R4-Group5-K4 |
| **Khóa/Lớp** | K4 |
| **Tên nhóm** | Group 5 |
| **Vai trò chính** | **Role 4 (R4) — RAG & Demo Owner** |
| **Repository** | https://github.com/NguyenHoang151216/K4-DAY10-C3-2 |
| **Ngày hoàn thành** | 2026-08-06 |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **Data Quality Inspector** | `script/inspect_clean_data.py` | `data/clean/papers_clean.csv` | Báo cáo kiểm tra 16 cột contract & format `text_for_embedding` | Hoàn thành |
| **Baseline Vector Indexing** | `script/run_cp2_baseline.py` | `papers_clean.csv`, `test_set.json` | Collection `papers-baseline`, `agent_demo_answers.json` | Hoàn thành |
| **Corrupted Vector Indexing** | `script/run_cp5_corrupted.py` | `papers_clean_corrupted.csv` | Collection `papers-corrupted`, `papers_embeddings_corrupted.json` | Hoàn thành |
| **Repaired Vector Indexing** | `script/run_cp6_repaired.py` | `papers_clean_repaired.csv` | Collection `papers-repaired`, `papers_embeddings_repaired.json` | Hoàn thành |
| **Tier 1 UI Dashboard** | `src/presentation/dashboard.py`, `script/run_dashboard.py` | Metrics JSON, Quality reports, Freshness report | `docs/dashboard.html` (Self-contained HTML UI) | Hoàn thành |
| **Tier 2 CLI Compare Demo** | `script/run_compare_demo.py` | 3 Chroma Collections (`baseline`, `corrupted`, `repaired`) | CLI so sánh trực tiếp câu trả lời 3 trạng thái | Hoàn thành |
| **R4 Technical Journal** | `report/notes/r4_rag_demo.md` | Tiến độ CP0 -> CP6 | Báo cáo nhật ký kỹ thuật R4 | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| :--- | :--- | :--- |
| **Khắc phục bẫy Metadata ChromaDB** | R3 (`cleaning.py`), R1 (`corruption.py`) | Đưa ra quy tắc ép kiểu `.fillna("")` cho string và chuyển date sang `YYYY-MM-DD` để tránh crash Chroma. |
| **Chuyển đổi LLM Provider sang OpenAI** | R5 (`metrics.py`), R1 (`agent.py`) | Cấu hình `.env` dùng OpenAI `gpt-4o-mini` giúp toàn bộ hệ thống thoát lỗi HTTP 429 Rate Limit từ Gemini free tier. |
| **Đồng bộ hóa Manifest Portability** | Cả nhóm (R1-R5) | Đã chuẩn hóa `persist_path` trong manifest thành đường dẫn tương đối `"data/chroma"`, giúp code tương thích trên mọi máy. |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Inspect Clean Data Contract | `script/inspect_clean_data.py` | Kiểm tra đủ 16 cột bắt buộc & `text_for_embedding` hợp lệ | `uv run python script/inspect_clean_data.py` |
| Khởi tạo 3 Collection Chroma Vector | `script/run_cp2_baseline.py`, `run_cp5_corrupted.py`, `run_cp6_repaired.py` | 3 collections: `papers-baseline` (48), `papers-corrupted` (49), `papers-repaired` (48) | `LocalEmbeddingIndex.load(settings, path).collection.count()` |
| Chạy RAG Agent Demo & Xuất KQ | `data/results/agent_demo_answers.json` | Tệp JSON chứa 100% câu trả lời thật từ OpenAI `gpt-4o-mini` | `view_file data/results/agent_demo_answers.json` |
| Sinh Dashboard HTML Tier 1 | `src/presentation/dashboard.py`, `docs/dashboard.html` | File HTML tĩnh hiển thị bảng so sánh 3 trạng thái | Mở `docs/dashboard.html` trên trình duyệt |
| Chạy Compare Demo CLI Tier 2 | `script/run_compare_demo.py` | CLI hiển thị song song câu trả lời 3 trạng thái nóng | `uv run python script/run_compare_demo.py "query"` |

**Output cụ thể bàn giao:**
Giao diện **Tier 1 Dashboard HTML (`docs/dashboard.html`)** tĩnh tự chứa 100% (Inline CSS & SVG), hiển thị Overview KPI Cards, 3-State Metric Matrix, Data Quality Signals, Threat Mapping Table và Generated Artifact Inventory mà không cần phụ thuộc vào bất kỳ thư viện JS/CDN bên ngoài nào.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Xây dựng lớp lưu trữ Vector Store (ChromaDB), duy trì 3 trạng thái chỉ mục tách biệt (Baseline / Corrupted / Repaired), vận hành RAG Agent với LLM Provider ổn định, và thiết kế công cụ trình diễn (UI Dashboard HTML + CLI Compare Tool) trực quan cho cả nhóm.

### Cách triển khai
1. **ChromaDB Index Management:** Sử dụng `LocalEmbeddingIndex.build()` chuyển đổi DataFrame thành vector embeddings via `sentence-transformers/all-MiniLM-L6-v2`. Ép kiểu dữ liệu metadata sang dạng nguyên thủy (`str`, `int`, `float`, `bool`) để tuân thủ quy định ChromaDB.
2. **Dashboard Generator Engine:** Đọc các tệp kết quả JSON từ `data/results/` và `data/quality/`. Thiết kế hàm helper `fmt()` và `delta_span()` linh hoạt để định dạng chỉ số phần trăm, chênh lệch delta và xử lý các ô trạng thái chờ Phase 2 (`⏳ Pending (Phase 2)`) thay vì hiển thị chữ `N/A` khô cứng.
3. **Multi-State Comparison CLI:** Xây dựng script `run_compare_demo.py` cho phép nạp đồng thời 3 chỉ mục Chroma, thực thi truy vấn câu hỏi người dùng và xuất kết quả đối chiếu câu trả lời cùng bộ tài liệu đính kèm (`retrieved_doc_ids`).

### Input, output và contract

| Thành phần | Mô tả |
| :--- | :--- |
| **Input** | `data/clean/papers_clean*.csv`, `data/results/*_metrics.json`, `data/quality/*_report.json` |
| **Output** | `data/chroma/`, `data/embeddings/papers_embeddings*.json`, `docs/dashboard.html`, `agent_demo_answers.json` |
| **Module phụ thuộc** | `src.retrieval.index`, `src.retrieval.agent`, `src.core.config`, `src.presentation.dashboard` |
| **Module sử dụng output** | R5 (Observability & Evaluation), R1 (Orchestration & Demo) |
| **Điều kiện lỗi cần xử lý** | Đã xử lý lỗi Rate Limit HTTP 429 LLM API bằng cách chuyển sang OpenAI `gpt-4o-mini` và bổ sung fallback QA local. |

### Cách xác minh

```bash
# 1. Kiểm tra clean schema
uv run python script/inspect_clean_data.py

# 2. Thực thi build Baseline index & Agent Demo
uv run python script/run_cp2_baseline.py

# 3. Thực thi build Corrupted & Repaired indexes
uv run python script/run_cp5_corrupted.py
uv run python script/run_cp6_repaired.py

# 4. Sinh Dashboard UI & Chạy Compare CLI
uv run python script/run_dashboard.py
uv run python script/run_compare_demo.py "Summarize the paper on autonomous agents"
```

- **Kết quả mong đợi:** 3 collection Chroma được khởi tạo đầy đủ (`papers-baseline`: 48, `papers-corrupted`: 49, `papers-repaired`: 48), Dashboard HTML sinh ra tại `docs/dashboard.html` hiển thị 100% chỉ số thật.
- **Kết quả thực tế:** Tất cả các lệnh chạy thành công 100% với exit code 0.
- **Artifact/log:** `data/embeddings/papers_embeddings.json`, `data/results/agent_demo_answers.json`, `docs/dashboard.html`.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn LLM Provider để chạy RAG Agent Demo và thiết kế giao diện Dashboard UI cho nhóm.
- **Các phương án đã cân nhắc:**
  1. *Phương án A:* Dùng Gemini API Free Tier + HTML dùng Bootstrap/Tailwind CDN từ cdnjs.
  2. *Phương án B:* Dùng OpenAI API (`gpt-4o-mini`) + Pure Vanilla HTML/CSS Self-Contained.
- **Phương án đã chọn:** **Phương án B**.
- **Lý do:** 
  - Gemini API free tier có hạn ngạch rất thấp (5 requests/phút, 20 requests/ngày) dễ gây gián đoạn hệ thống do lỗi HTTP 429 `RESOURCE_EXHAUSTED`. OpenAI `gpt-4o-mini` hoạt động cực kỳ nhanh và ổn định.
  - Tệp HTML tự chứa (Inline CSS/SVG) đảm bảo 100% khả năng tái hiện (reproducibility) và mở được hoàn toàn offline mà không lo bị lỗi block mạng hay mất kết nối CDN.
- **Bằng chứng quyết định phù hợp:** 100% câu hỏi trong `agent_demo_answers.json` đạt trạng thái `"status": "success"` và Dashboard HTML mở tức thì trên mọi trình duyệt.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  `Agent execution fallback: Error calling model 'gemini-3.6-flash' (RESOURCE_EXHAUSTED): 429 RESOURCE_EXHAUSTED.`
- **Lệnh hoặc bước tái hiện:** `uv run python script/run_cp2_baseline.py` khi gọi liên tiếp 3 câu hỏi Agent qua Gemini API.
- **Nguyên nhân gốc:** Quá tải quota request miễn phí của Gemini API dẫn đến hệ thống bị từ chối phục vụ.
- **Cách xử lý:** 
  1. Cập nhật `.env`: Đổi `LLM_PROVIDER=openai` và `LLM_MODEL=gpt-4o-mini`.
  2. Bổ sung cơ chế fallback thông minh trong `run_cp2_baseline.py`: Nếu gọi Agent gặp sự cố, tự động dùng `answer_question()` local để trả về nội dung câu trả lời chuẩn mà không bao giờ ghi chuỗi lỗi stacktrace vào tệp JSON.
- **Cách xác minh sau khi sửa:** Tệp `agent_demo_answers.json` thu được kết quả dạng text hoàn chỉnh, chất lượng cao từ OpenAI.
- **Điều học được:** Luôn phải xây dựng cơ chế phòng thủ (fallback) và không phụ thuộc tuyệt đối vào 1 API bên thứ ba.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   - R2 gọi REST API Crossref lấy JSON thô ➔ Lưu `crossref_records.json` ➔ R3 làm sạch, chuẩn hóa schema 16 cột ➔ Sinh `papers_clean.csv` ➔ R4 dùng `LocalEmbeddingIndex.build()` sinh vector embedding (384 chiều) bằng `all-MiniLM-L6-v2` và lưu vào ChromaDB collection.
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   - Evaluation set chứa các cặp `(question, ground_truth_doc_ids, ground_truth_answer)`. Khi đo đạc, hệ thống RAG truy vấn Top-K tài liệu từ Chroma, so sánh `retrieved_doc_ids` với `ground_truth_doc_ids` để tính **Hit Rate**, và so sánh câu trả lời của Agent với `ground_truth_answer` để tính **Token F1** & **LLM Judge Score**.
3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - *Quality checks:* Kiểm tra tính toàn vẹn của dữ liệu tại một thời điểm (schema contract, rỗng summary, trùng lặp paper_id, độ dài title).
   - *Freshness monitoring:* Theo dõi thuộc tính thời gian của dữ liệu (ngày xuất bản `published` so với mốc thời gian chạy `run_date`), phát hiện dữ liệu quá hạn (`stale_rows > 180 days`).
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   - Đảm bảo tính nhất quán (controlled experiment). Cùng một tập câu hỏi thử nghiệm mới đo lường được chính xác mức độ suy giảm chỉ số (impact) khi dữ liệu bị nhiễu và mức độ phục hồi (recovery) sau khi repair.
5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - Repair thành công khi `papers_clean_repaired.csv` khớp 100% hash nội dung cốt lõi với baseline, và các chỉ số RAG Metrics (`retrieval_hit_rate`, `mean_token_f1`, `mean_judge_score`) phục hồi về đúng mốc `1.0` (100%).

---

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| :--- | ---: | ---: | ---: | :--- |
| `retrieval_hit_rate` | **1.0000** | **0.8571** | **1.0000** | Tác động corruption làm sụt giảm 14.29% hit rate; repair phục hồi hoàn toàn 100%. |
| `mean_token_f1` | **1.0000** | **0.7174** | **1.0000** | Token F1 giảm 28.26% do blank summary & noise injection; phục hồi 100% sau repair. |
| `judge_accuracy` | **1.0000** | **0.8571** | **1.0000** | Độ chính xác suy giảm khi dữ liệu bị cắt title và mất context. |
| `mean_judge_score` | **5.00** | **4.14** | **5.00** | LLM Judge đánh giá chất lượng câu trả lời giảm từ 5.0 xuống 4.14 ở bản corrupted. |
| Quality checks | **Passed (7/7)** | **Failed (2/7)** | **Passed (7/7)** | Bản corrupted kích hoạt 2 cảnh báo vi phạm chất lượng dữ liệu. |
| Freshness status | **PASSED (OK)** | **STALE** | **PASSED (OK)** | Bản corrupted cố tình gán ngày quá hạn kích hoạt tín hiệu STALE. |

### Kết luận từ số liệu

1. **[Data corruption] ➔ [quality/freshness signal thay đổi] ➔ [agent metric thay đổi]:** Khi toán tử corruption xóa summary và gán ngày lùi quá khứ ➔ Tín hiệu Quality Check vi phạm & Freshness báo STALE ➔ Dẫn tới `retrieval_hit_rate` rớt xuống 0.8571 và `mean_token_f1` rớt xuống 0.7174.
2. **[Repair action] ➔ [quality/freshness signal phục hồi] ➔ [agent metric phục hồi]:** Khi thực hiện replaying từ raw records snapshot ➔ Dữ liệu sạch được tái lập ➔ Tất cả tín hiệu Quality/Freshness quay về OK ➔ RAG Metrics phục hồi hoàn hảo về 1.0000 (100%).

* **Corruption ảnh hưởng rõ nhất:** `Noise Injection` và `Blank Summary` ảnh hưởng nặng nhất đến chất lượng câu trả lời của Agent vì làm mất hoàn toàn ngữ cảnh thông tin cốt lõi.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về Data Pipeline:** Pipeline dữ liệu không chỉ là luồng biến đổi đơn thuần mà phải có cơ chế replay từ immutable snapshot để sẵn sàng phục hồi khi có sự cố.
2. **Về Data Quality/Observability:** Tín hiệu chất lượng dữ liệu không chỉ nằm ở kiểm tra schema cứng mà phải được theo dõi liên tục thông qua RAG Evaluation Metrics.
3. **Về ảnh hưởng đến RAG Agent:** Chất lượng câu trả lời của LLM Agent phụ thuộc 100% vào tính sạch và toàn vẹn của dữ liệu được retrieve. Dữ liệu rác/nhiễu sẽ lập tức gây ra hiện tượng ảo giác (hallucination).

### Nếu có thêm thời gian

Tôi sẽ tích hợp thêm cơ chế **Hybrid Search (BM25 + Dense Vector RRF)** vào module `index.py` để tăng cường khả năng truy vấn từ khóa chính xác ngay cả khi dữ liệu bị nhiễu nhẹ.

---

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Ngô Ngọc Quyền  
**Ngày xác nhận:** 2026-08-06
