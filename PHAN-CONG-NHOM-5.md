# PHÂN CÔNG NHÓM 5 NGƯỜI — K3 Day 10: Data Pipeline & Data Observability

> Bản mở rộng từ khung phân công của BTC (`phan-cong-day-10-data-pipeline-4h.html`), bổ sung phần kỹ thuật chi tiết, rule Git, UI demo và báo cáo tổng kết kiến thức.
>
> **Lưu ý về sĩ số:** nhóm 5 tách ingestion và cleaning thành 2 người → thêm một mặt phân giới nằm **ngay giữa luồng dữ liệu**. Đổi lại, có thêm công suất để `docs/KNOWLEDGE.md` có chủ sở hữu riêng và demo Tier 2 thành bắt buộc. R1 phải điều phối chặt hơn so với cấu hình 4 người.

---

## MỤC LỤC

- [PHẦN 0 — PRE-WORK (làm TRƯỚC buổi lab)](#phần-0--pre-work-làm-trước-buổi-lab)
- [PHẦN 1 — GIT RULES](#phần-1--git-rules-chống-conflict-và-crash)
- [PHẦN 2 — NĂM VAI TRÒ](#phần-2--năm-vai-trò)
- [PHẦN 3 — CÁC BẪY KỸ THUẬT](#phần-3--7-bẫy-kỹ-thuật-bắt-buộc-né)
- [PHẦN 4 — TIMELINE CP0–CP6](#phần-4--timeline-cp0cp6)
- [PHẦN 5 — DELIVERABLE BỔ SUNG](#phần-5--deliverable-bổ-sung)
- [PHẦN 6 — DEFINITION OF DONE](#phần-6--definition-of-done)

---

# PHẦN 0 — PRE-WORK (làm TRƯỚC buổi lab)

> **Đây là phần quan trọng nhất của tài liệu này. BTC không có phần này.**

## 0.1. Vì sao bắt buộc

CP0 chỉ có **30 phút**. Kiểm chứng thực tế trên máy:

| Hạng mục | Trạng thái | Thời gian |
|---|---|---|
| `uv` | **chưa cài** | 2–5 phút |
| `.venv` | **chưa có** | 1 phút |
| Dependency | **180 package**, gồm `torch 2.12.0` | **30–45 phút, ~2,5–3GB** |
| `.env` | **chưa có** | 2 phút |
| Model MiniLM-L6-v2 | tải ở lần build index đầu | 3–5 phút, ~90MB |

Nếu cả nhóm cài lúc bắt đầu buổi lab, **toàn bộ CP0 bị nuốt sạch** và không ai viết được dòng code nào. Cả 5 người phải hoàn tất mục 0.2 trước khi đồng hồ CP0 chạy.

## 0.2. Checklist từng người

### Bước 1 — Kiểm tra Python
```powershell
python --version    # phải trong khoảng 3.11 – 3.13
```

### Bước 2 — Cài dependency

**Cách A — dùng `uv` (khuyến nghị):**
```powershell
# Cài uv nếu chưa có
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

uv sync
uv sync --extra dev
```

**Cách B — dùng pip (nếu không cài được `uv`):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

> `pip install -r requirements.txt` **không đủ** — lệnh đó cài thư viện nhưng không cài package trong `src/`, sẽ lỗi `No module named 'pipelines'`.

### Bước 3 — Tạo `.env`
```powershell
Copy-Item .env.example .env
```
Điền credential của **đúng một** provider sẽ dùng. **Không commit `.env`.**

### Bước 4 — Warm-up (tải sẵn model, tránh mất 5 phút giữa CP2)
```powershell
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2'); print('model ready')"
```
Dùng pip thì bỏ `uv run`.

### Bước 5 — Verify
```powershell
uv run python -c "import pandas, chromadb, sentence_transformers, langchain, requests; print('OK')"
```

## 0.3. Quy ước lệnh trong tài liệu này

Mọi lệnh viết dưới dạng `uv run python ...`. Nếu dùng Cách B (pip + venv đã activate), **bỏ `uv run`**:

| Bản `uv` | Bản `pip` |
|---|---|
| `uv run python script/run_phase1.py` | `python script/run_phase1.py` |

## 0.4. Chốt trước buổi lab (15 phút họp nhanh)

- [ ] Ai giữ vai R1 / R2 / R3 / R4 / R5
- [ ] Provider LLM dùng chung (xem [Bẫy 3](#bẫy-3--48-lần-gọi-llm-judge--rate-limit--fallback-im-lặng))
- [ ] Repo chung, ai có quyền merge
- [ ] **R2 và R3 thống nhất trước schema `PaperRecord` → clean DataFrame** — đây là mặt phân giới mới của cấu hình 5 người, không chốt trước sẽ tắc ở CP1
- [ ] Cả 5 đã chạy xong mục 0.2 và báo "môi trường sẵn sàng"

---

# PHẦN 1 — GIT RULES (chống conflict và crash)

> Vi phạm một luật ở đây làm hỏng việc của cả nhóm. Đọc trước phút 0.

## 1.1. Ma trận sở hữu file — KHÔNG sửa file của người khác

| Vai trò | Sở hữu độc quyền |
|---|---|
| **R1 Integrator** | `src/core/config.py`, `src/pipelines/*`, `script/run_phase1.py`, `script/run_corruption_flow.py`, `pyproject.toml`, `uv.lock`, `.env.example`, `.gitignore`, `.github/*`, `README.md`, **`data/**`** |
| **R2 Ingestion** | `src/ingestion/crossref.py` |
| **R3 Cleaning & Corruption** | `src/ingestion/cleaning.py`, `src/ingestion/corruption.py` |
| **R4 RAG & Demo** | `src/presentation/**` (tạo mới), `script/run_dashboard.py`, `script/run_compare_demo.py` (tạo mới) |
| **R5 Eval & Obs** | `src/evaluation/testset.py`, `src/observability/quality.py`, `src/observability/reporting.py` |

**`src/ingestion/__init__.py` do R1 giữ** — file này import cả 3 module của R2 và R3, để chung sẽ conflict. R2/R3 cần đổi export thì báo R1.

**`src/retrieval/**` là read-only với tất cả mọi người.** Muốn sửa → báo R1, R1 quyết. Sửa `index.py` sẽ phá `LocalEmbeddingIndex.load()` và làm gãy cả 3 trạng thái cùng lúc.

Ai tạo file mới thì sở hữu file đó. Cần người khác đổi file của họ → nhắn, đừng tự sửa.

## 1.2. LUẬT VÀNG: chỉ R1 được commit `data/`

**R2, R3, R4, R5 chạy pipeline local thoải mái nhưng KHÔNG BAO GIỜ `git add data/`.**

Lý do: mỗi lần chạy sinh lại toàn bộ JSON. 5 người cùng commit `data/` = conflict trên file sinh tự động, không merge nổi, và không ai biết con số nào là thật.

R1 commit `data/` đúng **2 thời điểm**: cuối CP3 (baseline) và cuối CP6 (đầy đủ).

`.gitignore` bổ sung (R1 làm ở CP0):
```gitignore
data/chroma/          # sqlite binary, rebuild được, conflict không giải nổi
.pytest_cache/
```

## 1.3. Branch và Pull Request

```
main                          ← chỉ nhận PR đã merge, KHÔNG push thẳng
├── feat/r1-config-orchestration
├── feat/r2-ingestion
├── feat/r3-cleaning-corruption
├── feat/r4-retrieval-demo
└── feat/r5-eval-observability
```

- Đặt tên branch: `feat/r<số>-<scope>`
- **Trước mỗi lần push: `git pull --rebase origin main`** — không dùng merge commit, giữ lịch sử thẳng
- PR nhỏ, merge sớm. Đừng ôm branch 2 tiếng rồi merge một cục
- Người review: R1 (riêng PR của R1 thì R5 review)

## 1.4. Thứ tự merge theo dependency

Luồng phụ thuộc **một chiều**, merge sai thứ tự là gãy:

```
R1 config ──→ R2 crossref ──→ R3 cleaning ──→ R5 testset ──→ R4 index ──→ R1 phase1
                                          └──→ R5 quality ───┘
```

Chốt merge bắt buộc:

| Thời điểm | Phải có trong `main` | Vì |
|---|---|---|
| Trước CP1 | `config.py` của R1 | mọi người cần `Settings` mới |
| **Phút 45 (giữa CP1)** | **`crossref.py` của R2** | **R3 không thể hoàn thiện cleaning nếu chưa có `PaperRecord` thật** |
| Trước CP2 | `cleaning.py` của R3 | R5 cần schema thật để làm test set, R4 cần để build index |
| Trước CP3 | toàn bộ PR của CP0–CP2 | phase1 gọi tất cả module |

> **Đây là rủi ro riêng của cấu hình 5 người.** R2 chậm 10 phút thì R3 ngồi chờ, và trễ đó dồn thẳng sang R5 rồi R4. Đối sách: R2 phải merge `parse_crossref_payload` **sớm nhất có thể**, kể cả khi phần retry/fetch chưa xong — R3 chỉ cần schema `PaperRecord` để bắt đầu.

## 1.5. Contract đóng băng — KHÔNG đổi chữ ký hàm

Các chữ ký này là mặt phân giới giữa 5 người. **Không ai được đổi**, kể cả thêm tham số bắt buộc:

```python
parse_crossref_payload(payload: dict) -> list[PaperRecord]
load_raw_records(path: Path) -> list[PaperRecord]
build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame
build_test_set(df: pd.DataFrame, output_path) -> list[dict]
run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict
build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict
```

Ngoại lệ duy nhất được phép — mở rộng **có default**, tương thích ngược:
```python
corrupt_clean_dataframe(df, output_log_path, *, target_doc_ids=None, seed=42)
```

### Contract cột clean DataFrame — R2 và R3 chốt CHUNG ở CP0, dán vào channel nhóm

```
paper_id, title, summary, authors, categories, primary_category,
published (str ISO), updated, abs_url, pdf_url, comment,
authors_joined, categories_joined, summary_chars, age_days, text_for_embedding
```

11 cột đầu đến thẳng từ `PaperRecord` của R2; 5 cột cuối do R3 sinh ra. **Đây là điểm bàn giao quan trọng nhất của nhóm 5** — R2 và R3 phải nói chuyện với nhau ở CP0, không đợi đến CP1.

Đổi tên **một** cột ở đây = gãy đồng thời `index.py`, `qa.py`, `quality.py` và test set.

## 1.6. Đường dẫn artifact — luôn lấy từ `settings.paths`

Không hardcode. Bảng đúng theo `src/core/config.py`:

| Mục đích | Path |
|---|---|
| Raw response | `data/raw/crossref_response.json` |
| Raw records | `data/raw/crossref_records.json` |
| Clean | `data/clean/papers_clean.csv` + `.json` |
| Corrupted | `data/clean/papers_clean_corrupted.csv` + `.json` |
| Repaired | `data/clean/papers_clean_repaired.csv` + `.json` |
| Embedding manifest | `data/embeddings/papers_embeddings{,_corrupted,_repaired}.json` |
| Test set | `data/eval/test_set.json` |
| Metrics | `data/results/{baseline,corrupted,repaired}_metrics.json` |
| Answers | `data/results/{baseline,corrupted,repaired}_answers.json` |
| Agent demo | `data/results/agent_demo_answers.json` |
| Corruption log | `data/results/corruption_log.json` |
| Freshness | `data/quality/freshness_report.json` |
| Report baseline | `data/reports/phase1_report.md` |
| Report so sánh | `data/reports/corruption_report.md` |
| Collection | `papers-baseline` / `papers-corrupted` / `papers-repaired` (**gạch nối**) |

> `config.py` chỉ định nghĩa **một** `freshness_report`. R5 derive thêm 2 path anh em trong `quality_dir` cho corrupted/repaired.

## 1.7. Commit convention

```
feat(ingestion): implement Crossref parser with JATS cleaning
fix(cleaning): keep published as ISO string for Chroma metadata
docs(report): add corruption-to-threat mapping table
chore(git): add data/chroma to gitignore
```

Scope: `ingestion` · `cleaning` · `retrieval` · `eval` · `observability` · `pipeline` · `demo` · `report` · `git`

## 1.8. Checklist trước mọi PR

- [ ] `git pull --rebase origin main` không còn conflict
- [ ] Không có file ngoài phạm vi sở hữu của mình
- [ ] Không có `data/` trong diff (trừ PR của R1)
- [ ] Không secret: `git diff --cached | Select-String -Pattern "api[_-]?key|sk-|AIza|@gmail"`
- [ ] Không hardcode absolute path (`D:\...`) — luôn dùng `settings.paths.*`
- [ ] Không đổi chữ ký hàm ở §1.5

## 1.9. Ghi chú cá nhân — chống conflict trên báo cáo

Mỗi người ghi note **vào file riêng**, không ai chạm file người khác:

```
report/notes/r1_integrator.md
report/notes/r2_ingestion.md
report/notes/r3_cleaning_corruption.md
report/notes/r4_rag_demo.md
report/notes/r5_eval_obs.md
```

Ghi **liên tục trong lúc làm**: quyết định kỹ thuật, lỗi gặp, số liệu quan sát được. CP6 R1 gộp lại. Gộp từ 5 file rời thì không bao giờ conflict; 5 người cùng sửa `group_report.md` thì conflict liên tục.

---

# PHẦN 2 — NĂM VAI TRÒ

## R1 — Integrator & Release Owner
> BTC: *"Pipeline integrator — settings, orchestration, release"* · `src/core/` · `src/pipelines/`

**Sở hữu:** `src/core/config.py`, `src/pipelines/*`, `script/`, `src/ingestion/__init__.py`, `.github/`, `data/` (người commit duy nhất)

**Nhiệm vụ:**
- Mở rộng `Settings` + tạo `run_context.json` (xem [Bẫy 4](#bẫy-4--run_date-không-được-persist))
- Viết `phase1.py` và `corruption_flow.py`
- **Chủ Git rules**: `.gitignore`, `.github/PULL_REQUEST_TEMPLATE.md`, `CODEOWNERS`
- Review mọi PR, quyết thứ tự merge, chạy end-to-end, commit `data/`
- **Điều phối bàn giao R2 → R3 ở CP1** — mặt phân giới rủi ro nhất của cấu hình 5 người
- CP6: gộp `report/notes/*` → `group_report.md`

## R2 — Ingestion Owner
> BTC: *"Ingestion owner — Crossref + raw lineage"* · `src/ingestion/crossref.py` · `data/raw/`

**Sở hữu:** `src/ingestion/crossref.py`

**Nhiệm vụ chính:** `parse_crossref_payload`, `fetch_source_records`, `load_raw_records`.

**Nhiệm vụ mở rộng: chủ sở hữu `docs/KNOWLEDGE.md`** (xem [Phần 5.1](#51-docsknowledgemd--báo-cáo-tổng-kết-kiến-thức))

### Vì sao R2 nhận báo cáo kiến thức

R2 xong việc code sớm nhất — ingestion hoàn tất ở CP1, sau đó chỉ còn verify lineage. Từ CP2 trở đi R2 có công suất trống.

Và vai này hợp về mặt nội dung: luận điểm trung tâm của lab — **"raw snapshot bất biến là điều kiện cần để repair"** — chính là câu chuyện của ingestion owner. Người viết `fetch_source_records` là người hiểu rõ nhất vì sao phải lưu raw response *trước khi* parse.

**Ưu tiên tuyệt đối ở CP0–CP1:** merge `parse_crossref_payload` sớm nhất có thể để R3 không phải chờ. Phần retry/backoff có thể hoàn thiện sau.

## R3 — Cleaning & Corruption Owner
> BTC: *"Cleaning & corruption owner — clean schema, corruption, repair"* · `src/ingestion/cleaning.py` · `corruption.py`

**Sở hữu:** `src/ingestion/cleaning.py`, `src/ingestion/corruption.py`

**Đây là vai nặng nhất về code** trong cấu hình 5 người, và nằm ở **trung tâm luồng dữ liệu** — mọi module downstream (test set, index, quality) đều phụ thuộc vào schema R3 sinh ra.

**Nhiệm vụ:** cleaning (normalize + dedupe + derived columns) · corruption (6 operator + log deterministic).

**Rủi ro cần quản:** R3 phụ thuộc R2 ở CP1. Đối sách — R3 viết trước phần không cần dữ liệu thật (khung hàm, normalize helper, format `text_for_embedding`) dựa trên `PaperRecord` đã chốt ở CP0, rồi ghép dữ liệu thật khi R2 merge.

## R4 — RAG & Demo Owner
> BTC: *"RAG & agent owner — MiniLM, Chroma, search, lookup"* · `src/retrieval/` · `data/embeddings/`

**Sở hữu:** `src/presentation/**` (tạo mới), `script/run_dashboard.py`, `script/run_compare_demo.py`

### Vì sao vai này được mở rộng

**Toàn bộ `src/retrieval/` đã implement sẵn 100%** — `embeddings.py`, `index.py`, `llm.py`, `agent.py`, `qa.py` đều không có `TODO(student)` nào. Phần RAG thật của R4 chỉ là build index + smoke test + verify, khoảng **45 phút**.

Công suất còn lại dồn vào **UI demo** — deliverable làm nên nét riêng của nhóm, và BTC không giao cho ai.

### Nhiệm vụ RAG (giữ nguyên theo BTC)
- Build 3 collection qua `LocalEmbeddingIndex.build(df, settings, embeddings_output_path)`
- Smoke test: semantic search + exact lookup với query kiểm chứng được
- Chạy agent → `data/results/agent_demo_answers.json` (Rubric mục 5 = 10 điểm)
- Xác nhận `papers-baseline` không bị mutate khi build corrupted/repaired

### Nhiệm vụ Demo (bổ sung) — cả 2 tier đều bắt buộc

Nhóm 5 có công suất, nên **cả Tier 1 và Tier 2 đều là deliverable bắt buộc**, không phải tùy chọn như nhóm 4.

**Tier 1 — `docs/dashboard.html`**

`src/presentation/dashboard.py` — Python thuần đọc JSON trong `data/` → sinh HTML tĩnh self-contained:
- Bảng 3 trạng thái (baseline / corrupted / repaired) với delta tô màu
- Bar chart 4 metric chính
- Timeline 6 corruption operator kèm ánh xạ mối đe dọa bảo mật
- Quality check pass/fail, freshness gauge
- Artifact inventory có link

**Ràng buộc: inline CSS + inline SVG, KHÔNG CDN, KHÔNG dependency mới.** Không đụng `uv.lock` → không có nguy cơ conflict lockfile.

**Tier 2 — `script/run_compare_demo.py`**

Nhập 1 câu hỏi → query cả 3 collection → in 3 câu trả lời + doc retrieved cạnh nhau.

Đây là khoảnh khắc thuyết phục nhất khi demo: **cùng một câu hỏi, dữ liệu hỏng trả lời sai, repair xong trả lời đúng lại.** Luận điểm của lab được *nhìn thấy* thay vì *đọc*. Cũng zero dependency mới.

> Không dùng Streamlit/Gradio trừ khi CP6 còn dư ≥20 phút. Thêm dependency lúc gấp là rủi ro conflict `uv.lock` không đáng.

## R5 — Evaluation & Observability Owner
> BTC: *"Evaluation & observability — test set, metrics, quality, freshness, reports"* · `src/evaluation/` · `src/observability/`

**Sở hữu:** `src/evaluation/testset.py`, `src/observability/quality.py`, `src/observability/reporting.py`

**Vai nặng thứ nhì** — 3 file, 5 hàm.

**Nhiệm vụ:** test set bất biến · quality checks (7 hard-fail + 5 warning) · freshness report · 2 báo cáo Markdown.

**Trách nhiệm riêng:** R5 là người duy nhất được sinh Markdown report, và phải đảm bảo **mọi số trong `.md` khớp `.json`**. Rubric trừ điểm nếu report không match artifact.

---

# PHẦN 3 — 7 BẪY KỸ THUẬT BẮT BUỘC NÉ

> Tất cả đã được kiểm chứng trên `uv.lock` và source code thật của repo. Đọc trước khi code.

## Bẫy 1 — pandas 3.0.3 Copy-on-Write  ⚠️ NGUY HIỂM NHẤT
**Ai cần biết:** R3 (bắt buộc), R5

`uv.lock` pin **pandas 3.0.3**, không phải 2.x. Copy-on-Write là mặc định:

```python
df[df.paper_id == pid]['summary'] = ""       # ✗ IM LẶNG KHÔNG LÀM GÌ CẢ
df.loc[df.paper_id == pid, 'summary'] = ""   # ✓ đúng
```

Nếu viết sai kiểu đầu trong `corrupt_clean_dataframe`: file corrupted **vẫn sinh ra**, pipeline **vẫn xanh**, corruption log **vẫn ghi đủ** — nhưng dữ liệu y hệt baseline. Metrics không đổi. Cả nhóm sẽ đi debug nhầm sang hướng "corruption chưa đủ mạnh" và mất cả CP5.

**Cách chặn:** sau khi corrupt, assert số row thực sự khác baseline khớp với số đã ghi trong log, **trước khi** build index.

## Bẫy 2 — Chroma từ chối `None` / `NaN` / `datetime` trong metadata
**Ai cần biết:** R3 (bắt buộc), R4

`index.py` dòng 54–63 đẩy **thẳng** cột DataFrame vào Chroma metadata. Chroma chỉ nhận `str`/`int`/`float`/`bool`.

Trong `build_clean_dataframe`:
- Parse date bằng `pd.to_datetime(..., errors="coerce", utc=True)` vào cột phụ **`published_dt`** (dùng để tính `age_days`, sort, freshness)
- Cột **`published` giữ chuỗi ISO `YYYY-MM-DD`**, rỗng thì `""`
- `fillna("")` mọi cột string: `summary`, `abs_url`, `pdf_url`, `authors_joined`, `categories_joined`, `comment`
- **Drop `published_dt`** trước khi ghi CSV/JSON và trước khi build index

## Bẫy 3 — 48 lần gọi LLM judge → rate limit → fallback im lặng
**Ai cần biết:** R5 (bắt buộc), R1

`_judge_answer` tạo **client LLM mới cho mỗi sample** (`metrics.py` dòng 62). Với 16 câu × 3 trạng thái = **48 lần gọi API**, cộng agent demo.

Gemini free tier ~10 RPM → sẽ dính `429` → `except Exception` ở dòng 64 **nuốt lỗi** → rơi về heuristic. Pipeline vẫn xanh, metric vẫn đẹp, nhưng **không còn là LLM-as-a-judge nữa**.

**Đối sách (không sửa `metrics.py`):**
- Đếm sample có `judge.reasoning` bắt đầu bằng `"Fallback heuristic judge"` → `judge_fallback_count` / `judge_fallback_rate`
- Nếu rate = 1.0, report **không được** gọi kết quả là "LLM-as-a-judge" — phải ghi rõ là heuristic
- Cân nhắc giảm test set xuống **12 câu** → 36 lần gọi
- Nếu dùng Gemini free: chốt trước, và coi fallback là kết quả chấp nhận được có ghi chú

## Bẫy 4 — `run_date` không được persist
**Ai cần biết:** R1 (bắt buộc), R3

`run_phase1.py` và `run_corruption_flow.py` là **2 tiến trình riêng**. Repair replay cleaning ở thời điểm khác → `age_days` lệch → so hash baseline vs repaired **luôn fail dù code hoàn toàn đúng**.

R1 ghi `data/results/run_context.json` ở CP1:
```json
{"run_date": "...", "source_query": "...", "source_filter": "...",
 "max_results": 48, "embedding_model": "...", "top_k": 4,
 "freshness_threshold_days": 180}
```
`corruption_flow.py` đọc lại `run_date` từ đây khi replay cleaning.

## Bẫy 5 — Title chứa dấu nháy đơn phá exact lookup
**Ai cần biết:** R5 (bắt buộc)

`qa.py` dòng 33 bắt title bằng regex `r"'([^']+)'"`. Title chứa apostrophe (vd `Agent's memory`) sẽ bị cắt sai → exact lookup fail → `retrieval_hit_rate` tụt không rõ lý do.

**Khi chọn paper cho test set: loại mọi title chứa ký tự `'`.**

## Bẫy 6 — Ground truth phải khớp đúng cột `_extract_answer` trả về
**Ai cần biết:** R5 (bắt buộc)

`qa.py` dòng 20–29 nhận diện intent theo từ khóa và trả về **đúng một trường metadata**:

| Câu hỏi chứa | Trả về |
|---|---|
| `who authored` / `list the authors` | `authors_joined` |
| `when was` / `publication date` / `published on` | `published` |
| `what categories` | `categories_joined` |
| *(còn lại)* | `first_sentence(summary)` |

→ 4 template bắt buộc dùng đúng chữ:
```
Summarize the paper '<title>'.
Who authored '<title>'?
When was '<title>' published?
What categories are associated with '<title>'?
```

**Ground truth cho câu summary phải là `first_sentence(summary)`, KHÔNG phải cả abstract.** Dùng cả abstract → `token_f1` sập dù logic hoàn toàn đúng, và cả nhóm sẽ debug nhầm chỗ.

## Bẫy 7 — Không sửa `src/retrieval/index.py`
**Ai cần biết:** tất cả

`index.py` tự ghi manifest `{backend, embedding_model, persist_path, collection_name, documents}` và `load()` đọc lại đúng 3 key đó. Thay schema manifest → `LocalEmbeddingIndex.load()` gãy → mất cả 3 trạng thái.

Manifest do code có sẵn lo. Chỉ gọi `build()` và để nó tự derive collection name từ đường dẫn manifest.

---

# PHẦN 4 — TIMELINE CP0–CP6

> Mốc thời gian và pass criteria giữ nguyên theo BTC. Phần việc được bơm chi tiết theo từng vai.

## CP0 · 00:00–00:30 · Khởi động, contract & ingestion raw
**Pass (BTC):** raw response và raw records JSON tồn tại; `PaperRecord` có stable `paper_id`; mỗi người biết rõ artifact mình bàn giao.

| Vai | Việc |
|---|---|
| **R1** | Setup Git rules Phần 1 (`.gitignore`, branch, `CODEOWNERS`, PR template) — **làm đầu tiên, push ngay**. Mở rộng `Settings`: `crossref_mailto`, `request_timeout_seconds=30`, `request_max_retries=4`, `random_seed=42`, `source_query` đọc env, `max_results` đọc env (default 48), path `run_context`. Cập nhật `.env.example`. **Merge vào `main` trước phút 25.** |
| **R2** | Smoke test Crossref `rows=3`. Chốt mapping: `DOI`→`paper_id` (lowercase), `abstract`→`summary`, `subject`→`categories`, `container-title[0]`→`comment`, `link` content-type PDF→`pdf_url`. **Ngồi với R3 chốt contract bàn giao.** Viết `parse_crossref_payload` + hàm strip JATS trước, retry sau. |
| **R3** | **Ngồi với R2 chốt 16 cột clean DataFrame.** Viết trước phần không cần dữ liệu thật: khung hàm, normalize helper, format `text_for_embedding`. |
| **R4** | Đọc `index.py`, `qa.py`, `agent.py`. Ghi lại 2 ràng buộc cứng: `index.py:44-66` đọc cố định 9 cột; Chroma metadata chỉ nhận scalar. Phác khung `dashboard.py`. |
| **R5** | Đọc `qa.py:20-29` + `metrics.py`. Chốt 4 template câu hỏi và quy tắc ground truth ([Bẫy 6](#bẫy-6--ground-truth-phải-khớp-đúng-cột-_extract_answer-trả-về)). Thiết kế danh sách quality check (7 hard-fail + 5 warning). |

**Rủi ro:** query cybersecurity + `has-abstract:true` + 180 ngày có thể ra <24 record. R2 smoke test ngay; thiếu thì fallback `from-pub-date:2025-01-01` → rồi bỏ `type:journal-article`. Ghi lại quyết định cho report.

**Lệnh kiểm tra:** `ls data/raw`

---

## CP1 · 00:30–01:05 · Cleaning, data model & quality gates
**Pass (BTC):** clean CSV/JSON đọc được; `paper_id` unique; `text_for_embedding` và `age_days` có mặt; count/lý do record bị loại có thể truy vết.

| Vai | Việc |
|---|---|
| **R1** | Ghi `run_context.json` ([Bẫy 4](#bẫy-4--run_date-không-được-persist)) — **critical**. Dựng khung `phase1.py` với log `[n/13]`. **Theo dõi sát bàn giao R2→R3, ép merge đúng phút 45.** |
| **R2** | Hoàn thành ingestion: retry `429/500/502/503/504` + tôn trọng `Retry-After` + backoff 1→2→4→8s + jitter; **không** retry `400/401/403/404`; atomic write raw **trước** khi parse (`.tmp` → rename). **Merge `parse_crossref_payload` trước phút 45** kể cả khi retry chưa xong. |
| **R3** | Hoàn thành `build_clean_dataframe`, áp [Bẫy 2](#bẫy-2--chroma-từ-chối-none--nan--datetime-trong-metadata). Ngưỡng `summary_chars >= 80`; còn <24 record thì hạ 40 và **ghi rõ**. Dedupe theo `paper_id` (giữ summary dài hơn, hòa thì `updated` mới hơn), log số bị loại. Sort `published_dt` desc + `paper_id` asc. **Merge trước phút 65.** |
| **R4** | Khi cleaning merge: đọc 5 `text_for_embedding` thật — đủ Title/Authors/Categories/Published/Abstract, không rỗng. Dựng layout dashboard với dữ liệu giả. |
| **R5** | `run_data_quality_checks` + `build_freshness_report`. Ba `report_name`: `baseline_quality` / `corrupted_quality` / `repaired_quality`. Derive 3 path freshness trong `quality_dir`. |

**Lệnh kiểm tra:** `ls data/clean`

---

## CP2 · 01:05–01:35 · Test set, RAG index & agent smoke test
**Pass (BTC):** `test_set.json`, embedding manifest và collection baseline tồn tại; semantic search, exact lookup và agent đều trả về kết quả có nguồn.

| Vai | Việc |
|---|---|
| **R1** | Ghép `phase1.py`: raw → clean → quality → index → testset → evaluate. Xử lý `REFRESH_SOURCE` / `REFRESH_TEST_SET`. |
| **R2** | Xác minh một `paper_id` xuyên suốt raw → clean → index metadata. **Không refresh source giữa chừng** làm baseline đổi. **Bắt đầu `docs/KNOWLEDGE.md`** — đây là lúc R2 có công suất trống. |
| **R3** | Sửa lỗi schema R4/R5 báo. Review row được chọn vào test set để đảm bảo nội dung sạch. Bắt đầu thiết kế 6 corruption operator. |
| **R4** | Build `papers-baseline`. Smoke test semantic search + exact lookup. Chạy agent → `agent_demo_answers.json`, **bọc try/except** để thiếu key không sập pipeline. |
| **R5** | `build_test_set`: chọn deterministic 8 paper (2 mới nhất, 2 cũ nhất, 2 abstract dài nhất, 2 ở giữa), **loại title chứa `'`** ([Bẫy 5](#bẫy-5--title-chứa-dấu-nháy-đơn-phá-exact-lookup)). ~16 câu (8 summary / 3 authors / 3 date / 2 categories). Ground truth theo [Bẫy 6](#bẫy-6--ground-truth-phải-khớp-đúng-cột-_extract_answer-trả-về). Guard: <4 sample thì raise (tránh `StatisticsError` ở `mean()`). |

**Lệnh kiểm tra:** `find data -maxdepth 2 -type f | sort`

---

## CP3 · 01:35–02:00 · Baseline end-to-end & báo cáo
**Pass (BTC):** `baseline_metrics.json`, answers, quality/freshness và `phase1_report.md` tồn tại; team giải thích được ít nhất một hit/miss bằng artifact.

| Vai | Việc |
|---|---|
| **R1** | `uv run python script/run_phase1.py`. Fix tới khi xanh. **Commit `data/` lần 1.** |
| **R2** | Đối chiếu raw count vs clean count cùng R3, giải thích chênh lệch. Tiếp tục `KNOWLEDGE.md`. |
| **R3** | Kiểm tra clean schema, `age_days`, `text_for_embedding` trong artifact đã ghi. Xác minh quality check phản ánh dữ liệu thật, không hard-code pass. |
| **R4** | Xác nhận Chroma count == clean row count. Nạp số thật vào dashboard. |
| **R5** | `generate_phase1_report`. **Đếm `judge_fallback_rate`** ([Bẫy 3](#bẫy-3--48-lần-gọi-llm-judge--rate-limit--fallback-im-lặng)). Đọc 1 hit + 1 miss, giải thích được bằng artifact. |

> **Chốt cứng: không xong baseline thì KHÔNG sang CP5.** Corruption không có baseline là vô nghĩa.

**Lệnh kiểm tra:** `uv run python script/run_phase1.py`

---

## CP4 · 02:00–02:15 · Nghỉ 15 phút

Trước khi nghỉ: mỗi người ghi 3 dòng vào `report/notes/<mình>.md`. Sau nghỉ: R3 trình bày 60 giây kế hoạch corruption.

**Lệnh kiểm tra:** `cat data/results/baseline_metrics.json`

---

## CP5 · 02:15–03:15 · Corruption có kiểm soát & đo impact
**Pass (BTC):** corruption log, corrupted clean/index/answers/metrics/quality và report có đủ; baseline không bị ghi đè.

| Vai | Việc |
|---|---|
| **R1** | `corruption_flow.py` bước 1–8. **Verify baseline artifacts trước, thiếu thì raise** hướng dẫn chạy Phase 1 — không tự chạy baseline ngầm. |
| **R2** | Xác nhận raw source nguyên vẹn **trước khi** corrupt clean data. Chọn record có lineage rõ để chứng minh repair được. Kiểm tra corruption flow không fetch source mới làm comparison mất công bằng. Tiếp tục `KNOWLEDGE.md`. |
| **R3** | `corrupt_clean_dataframe(df, log_path, *, target_doc_ids, seed=42)`. **Copy df, dùng `.loc`** ([Bẫy 1](#bẫy-1--pandas-303-copy-on-write--nguy-hiểm-nhất)). 6 operator: drop latest 1–2 / blank summary 2 / noise 2–3 / truncate title 1–2 / stale date 2–3 / duplicate 2. Target: một phần từ `ground_truth_doc_ids` (để đo được), một phần ngoài test set (để thực tế). **Rebuild `text_for_embedding` + `summary_chars` + `age_days` + `authors_joined` + `categories_joined`** — quên là corruption vô hiệu. Log: `{seed, before/after count, operations:[{type, paper_ids, count, before_hash, after_hash}]}`, chỉ ID + hash. |
| **R4** | Build `papers-corrupted` riêng. Chạy lại đúng query baseline, ghi lại retrieval đổi thế nào. **Xác nhận `papers-baseline` còn đọc được và không bị mutate.** |
| **R5** | Quality/freshness trên corrupted, lưu report riêng. Nối corruption → check. **Nêu rõ: noise injection không có schema check nào bắt được, chỉ lộ qua RAG metric** — đây là điểm phân tích ăn điểm. Ghi cả signal nào KHÔNG đổi để tránh kết luận quá mức. |

**Nếu metrics không đổi, kiểm theo thứ tự:**
1. **[Bẫy 1](#bẫy-1--pandas-303-copy-on-write--nguy-hiểm-nhất) trước tiên** — data có thực sự đổi không?
2. Corrupted doc có nằm trong test set không?
3. `text_for_embedding` đã rebuild chưa?
4. Đang query nhầm collection baseline không?
5. Test set có bị tạo lại từ corrupted data không?

**Lệnh kiểm tra:** `uv run python script/run_corruption_flow.py`

---

## CP6 · 03:15–04:00 · Repair từ raw, comparison, review & demo
**Pass (BTC):** repaired artifacts và comparison report có baseline–corrupted–repaired/delta; repo không có secret; demo dùng artifact thật.

| Vai | Việc |
|---|---|
| **R1** | Chạy full 2 script. Sinh `data/results/repair_validation.json`. **Commit `data/` lần 2.** Gộp `report/notes/*` → `group_report.md`. Checklist cuối: artifacts đủ, reports match, no secret. |
| **R2** | Reload raw records đúng snapshot dùng ở baseline. **Chứng minh record bị corrupt/drop đã phục hồi bằng lineage.** Hoàn thiện `docs/KNOWLEDGE.md`. Hỗ trợ kiểm tra API key không lọt vào Git. |
| **R3** | Re-run cleaning từ raw tạo repaired dataset — **cùng `run_date` từ `run_context.json`**, không copy sửa tay từ baseline. Kiểm tra repaired schema, row count và quality signals. Demo khác biệt clean/corrupted/repaired. |
| **R4** | Build `papers-repaired`. **Hoàn thiện `docs/dashboard.html` + `run_compare_demo.py`.** **Dẫn phần demo.** |
| **R5** | `generate_corruption_report` → `data/reports/corruption_report.md`: bảng 3 trạng thái, `corruption_delta = corrupted−baseline`, `repair_gap = repaired−baseline`, `recovery = repaired−corrupted`, phân tích theo `question_type`. Nêu rõ nếu recovery chưa hoàn toàn. |
| **Cả nhóm** | 10 phút cuối: mỗi người viết `report/individual_report.md` của mình. |

**Lệnh kiểm tra:** `ls data/results/repaired_metrics.json data/reports/corruption_report.md`

---

# PHẦN 5 — DELIVERABLE BỔ SUNG

## 5.1. `docs/KNOWLEDGE.md` — báo cáo tổng kết kiến thức
**Chủ sở hữu: R2** · mỗi người đóng góp mục thuộc phần việc của mình

> BTC không giao ai làm việc này. Đây là chỗ ăn bonus rubric ("báo cáo rõ ràng có phân tích thay đổi metrics", "corruption scenario hợp lý và có ý nghĩa").

### Kiến thức trong luồng (lab yêu cầu)
1. **ETL hay ELT?** Lab này là ETL — transform trước khi nạp vào Chroma. ELT tương đương sẽ là: load nguyên trạng vào warehouse rồi transform bằng SQL/dbt.
2. **Bronze / Silver / Gold**: `crossref_response.json` → `papers_clean.csv` → Chroma collection.
3. **Data contract, lineage, idempotency, replay, backfill** — minh họa bằng chính artifact của nhóm.
4. **6 chiều chất lượng**: completeness, uniqueness, validity, consistency, freshness, timeliness.
5. **Monitoring vs Observability**: monitoring kiểm tra tập điều kiện đã biết; observability đủ tín hiệu để điều tra cả lỗi chưa biết trước.
6. **Controlled experiment**: giữ nguyên test set / embedding model / top_k / judge, chỉ đổi trạng thái dataset.

### Kiến thức ngoài luồng — phần tạo khác biệt

7. **Ánh xạ corruption → mối đe dọa bảo mật thật** (linh hồn chủ đề nhóm):

| Corruption trong lab | Mối đe dọa thật | Check phát hiện được |
|---|---|---|
| Xóa paper mới nhất | Knowledge base stale, agent trả lời theo thông tin cũ | freshness + row count |
| Blank abstract | Mất knowledge context, agent bịa | `summary_usable_ratio` |
| Inject noise | **Data poisoning** | *không check nào bắt* → chỉ lộ qua RAG metric |
| Truncate title | Entity / document resolution failure | title length / retrieval hit |
| Stale published date | Temporal reasoning sai | freshness / stale ratio |
| Duplicate records | Retrieval bias, top-k kém đa dạng | `paper_id_unique` |

8. **Vì sao một số corruption không hạ mọi metric.** `qa.py` có exact-title lookup → blank summary hạ `token_f1` nhưng **không** hạ `retrieval_hit_rate`. Chỉ truncate title hoặc drop document mới phá được retrieval. Đây là phân tích phân biệt nhóm giỏi với nhóm chỉ chạy được lệnh.
9. **Giới hạn của `token_f1`**: set token lowercase tách theo whitespace — mù với paraphrase và từ đồng nghĩa.
10. **Rủi ro judge fallback im lặng**: `_judge_answer` nuốt exception → pipeline vẫn ra số đẹp dù judge chết. Bài học: **metric phải tự khai báo độ tin cậy của nó**.
11. **Raw snapshot bất biến là điều kiện cần để repair.** Không có nó thì chỉ còn cách sửa tay — tức là che lỗi, không phải sửa lỗi. *(R2 viết mục này — đây là câu chuyện của ingestion owner.)*
12. **Noise injection không schema check nào bắt được** → cần semantic monitoring, không phải rule-based validation.

## 5.2. UI Demo
**Chủ trì: R4** — xem chi tiết ở [Phần 2 · R4](#r4--rag--demo-owner).

Nhóm 5 làm **cả Tier 1 và Tier 2**, không phải tùy chọn.

## 5.3. Báo cáo nhóm và cá nhân
**Chủ trì: R1** (gộp) · mỗi người tự viết phần cá nhân

`report/group_report.md` và `report/individual_report.md` là **deliverable bắt buộc** theo `report/README.md` (nhóm 3–5 thành viên). Mọi số liệu lấy từ JSON thật trong `data/`, không ghi tay.

---

# PHẦN 6 — DEFINITION OF DONE

```powershell
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
uv run python script/run_dashboard.py
Get-ChildItem src -Recurse -Filter *.py | Select-String 'TODO\(student\)|NotImplementedError'
git status --short
```

## Checklist

**Functional**
- [ ] Không còn `NotImplementedError` bắt buộc
- [ ] Phase 1 chạy end-to-end
- [ ] Corruption flow chạy end-to-end
- [ ] 3 collection `papers-baseline` / `papers-corrupted` / `papers-repaired` tách biệt, baseline không bị ghi đè

**Data & Evidence**
- [ ] Đủ artifact: `data/raw/`, `clean/`, `embeddings/`, `eval/`, `results/`, `quality/`, `reports/`
- [ ] Test set **giống hệt nhau** ở cả 3 trạng thái
- [ ] `corruption_log.json` có đủ 6 operator, ID bị tác động và tham số
- [ ] `agent_demo_answers.json` có kết quả agent thật

**Observability**
- [ ] Corruption làm **≥2 quality check fail**
- [ ] Corruption làm **≥1 metric giảm rõ rệt**
- [ ] Repaired pass quality checks
- [ ] `repair_validation.json` cho `core_content_hash_equal: true`

**Reporting**
- [ ] Số trong `.md` khớp `.json` — đối chiếu tay ít nhất 3 giá trị
- [ ] `docs/dashboard.html` mở được, số khớp artifact
- [ ] `script/run_compare_demo.py` chạy được trên cả 3 collection
- [ ] `docs/KNOWLEDGE.md` hoàn chỉnh
- [ ] `group_report.md` + 5 bản `individual_report.md`
- [ ] Nếu `judge_fallback_rate = 1.0`: report ghi rõ là heuristic, **không** gọi là LLM-as-a-judge

**Bảo mật & tái lập**
- [ ] Không `.env`, API key, email cá nhân trong Git
- [ ] Không hardcode absolute path
- [ ] `data/chroma/` đã gitignore
- [ ] Rebuild được clean data từ raw snapshot mà không gọi lại Crossref

## Thứ tự hy sinh khi trễ giờ

**Giữ bằng mọi giá** (rubric 90 điểm cơ bản):
`baseline → corruption → repair → comparison report`

**Bỏ theo thứ tự này:**
1. Great Expectations
2. Ragas (`RUN_RAGAS` để mặc định tắt)
3. Unit tests
4. Demo Tier 2 (`run_compare_demo.py`)
5. Dashboard Tier 1

**Không bao giờ bỏ:** raw snapshot và `run_context.json`. Bỏ chúng là mất khả năng repair — tức mất luôn mục 8 của rubric (Corruption và comparison, 10 điểm).

## Rủi ro riêng của cấu hình 5 người

**Bàn giao R2 → R3 nằm ngay giữa luồng dữ liệu.** R2 chậm 10 phút thì R3 ngồi chờ, và trễ đó dồn thẳng sang R5 rồi R4 — tức là 3 người bị chặn bởi 1 người.

Ba biện pháp giảm rủi ro, phải làm từ CP0:
1. R2 và R3 chốt contract `PaperRecord` → clean schema **ở CP0**, không đợi CP1
2. R2 merge `parse_crossref_payload` **trước phút 45**, kể cả khi retry/fetch chưa xong
3. R3 viết trước phần không cần dữ liệu thật (normalize helper, format `text_for_embedding`) rồi ghép sau

Nếu nhóm không tự tin điều phối được mặt phân giới này, cấu hình 4 người gộp R2+R3 làm một là lựa chọn an toàn hơn.
