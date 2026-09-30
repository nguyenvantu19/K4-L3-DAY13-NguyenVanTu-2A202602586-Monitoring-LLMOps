# Hướng dẫn làm Monitoring & LLMOps theo từng checkpoint

> Làm theo thứ tự từ CP0 đến CP4. Chạy lệnh từ thư mục gốc của repo. Hướng dẫn ưu tiên PowerShell trên Windows.

## Bài lab này làm gì?

Mục tiêu là điều tra một request có vấn đề theo chuỗi:

```text
Metrics → Logs → Traces → Root cause
```

- **Metrics** cho biết triệu chứng và thời điểm.
- **Logs** giúp tìm request cụ thể bằng `correlation_id`.
- **Traces** cho biết bước nào của request chậm hoặc lỗi.
- **Root cause** là kết luận có bằng chứng từ cả ba lớp trên.

`data/logs.jsonl` là structured log, đồng thời là nguồn dữ liệu dashboard. Langfuse lưu trace/span và prompt version. Hai nơi phải nối được bằng `correlation_id`.

## Chuẩn bị một lần

### Cài môi trường

Cần Python 3.11 trở lên, Git, và tài khoản Langfuse Cloud cá nhân.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu PowerShell chặn activate, cho phép trong cửa sổ hiện tại rồi thử lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Tạo `.env` từ `.env.example` **chỉ khi chưa có `.env`**:

```powershell
Copy-Item .env.example .env
```

Trong Langfuse Cloud, tạo project riêng tên `day13-k4-l3b-<MSSV>`, tạo key cho project đó và điền vào `.env`:

```dotenv
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
LANGFUSE_PROMPT_NAME=day13-chat
LANGFUSE_PROMPT_LABEL=production
```

Không commit/chia sẻ `.env`, key, hoặc ảnh trang API Keys. Dùng project riêng; không dùng key/project của bạn khác.

### Chạy API

Mở hai terminal ở thư mục repo. Terminal 1:

```powershell
uvicorn app.main:app --reload --env-file .env
```

Giữ terminal 1 mở. Terminal 2 dùng để chạy các lệnh sau. Kiểm tra API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Kết quả cần có `ok: true`. Metrics endpoint là `http://127.0.0.1:8000/metrics`.

## CP0 — Setup và baseline

**Mục tiêu:** xác nhận starter chạy được và lưu lại kết quả trước khi sửa TODO.

1. Chạy API như hướng dẫn trên.
2. Gửi workload mẫu:

   ```powershell
   python scripts/load_test.py
   ```

3. Kiểm tra `/health`, xác nhận có log mới trong `data/logs.jsonl` và trace trong đúng project Langfuse cá nhân.
4. Chạy baseline validators và tests:

   ```powershell
   python scripts/validate_logs.py
   python scripts/validate_dashboard.py
   python -m pytest -q
   ```

5. Ghi kết quả thực tế (kể cả kết quả chưa đạt) vào bảng **Kết quả kỹ thuật** của `submission/REPORT.md`. Lưu output/screenshot vào `submission/evidence/`.

**Đạt CP0 khi:** API trả `ok: true`; workload tạo log và trace; tests/validators đã chạy; baseline được ghi lại.

Baseline log validator thấp có thể bình thường vì correlation ID, metadata và PII là mục tiêu CP1. Giữ lại điểm baseline để so sánh.

## CP1 — Logging, correlation ID và PII

**Mục tiêu:** gắn một ID xuyên suốt mỗi request, bổ sung ngữ cảnh vào JSON log và che dữ liệu cá nhân trước khi ghi.

### Sửa TODO

1. `app/middleware.py`: đầu request xóa context cũ; nhận `x-request-id` hoặc sinh ID `req-<8 ký tự hex>`; bind ID vào structlog và request state; trả ID trong response header `x-request-id`.
2. `app/main.py`: trước log `request_received`, bind `user_id_hash`, `session_id`, `feature`, `model`, `env`.
3. `app/logging_config.py`: đặt processor scrub PII trước JSON renderer/file writer.
4. `app/pii.py` và tests: kiểm tra email, số điện thoại Việt Nam, CCCD, số thẻ thanh toán. Chỉ dùng PII giả.

### Đo lại

Validator đọc toàn bộ `data/logs.jsonl`; log cũ vẫn có thể làm kết quả thấp. Lưu baseline trước, rồi xóa/đổi tên log cũ, restart API và tạo log mới:

```powershell
python scripts/load_test.py --concurrency 5
python scripts/validate_logs.py
python -m pytest -q
```

Kiểm tra output mới: log có timestamp, event, correlation ID và metadata; PII giả đã che; header trả lại ID hợp lệ.

**Đạt CP1 khi:** validator log ≥ 80/100, ID nối được request/log/response, metadata đủ, không còn PII thô trong log mẫu.

## CP2 — Traces, prompt, dashboard, SLO và alerts

**Mục tiêu:** hiểu bước nào trong request gây chậm/lỗi; truy xuất được prompt đã dùng; xem sức khỏe hệ thống trên dashboard.

### 1. Tạo traces có span tree

Chạy workload để tự tạo ít nhất 10 trace trong project cá nhân:

```powershell
python scripts/load_test.py --concurrency 5
```

Trong `app/agent.py`, instrument hai child observations bằng API của Langfuse Python SDK v4:

- Retrieval: span/retriever riêng.
- LLM: generation riêng có model, prompt, input/output tokens và cost.

Trace cần metadata `correlation_id`, model và prompt name/label/version. Không capture raw input/output có thể chứa PII; chỉ dùng dữ liệu đã scrub. Mở Langfuse kiểm tra cây root → `lab-agent-run` → retrieval và generation.

### 2. Tạo prompt v1/v2 và rollback

Làm theo [PROMPT_VERSIONING.md](PROMPT_VERSIONING.md):

1. Trong project riêng, tạo text prompt `day13-chat` với các biến `{{feature}}`, `{{docs}}`, `{{message}}`.
2. Lưu v1 với labels `baseline` và `production`.
3. Tạo v2 có thay đổi nhỏ, gắn label `candidate`.
4. Chạy **cùng input** với baseline và candidate; trong trace xác nhận `prompt_name`, `prompt_label`, `prompt_version`.
5. Chuyển `production` sang v2, chạy request, rồi rollback `production` về v1.
6. Lưu trace ID mỗi version và ảnh danh sách version/rollback. Không hard-code metadata để giả version.

### 3. Dựng dashboard sáu panel

Dùng `data/logs.jsonl` làm nguồn chuẩn. Chọn Streamlit, notebook, Grafana hoặc công cụ tương đương. `config/dashboard.yaml` là contract; trường `query` là pseudocode logic, không bắt buộc dùng nguyên cú pháp đó.

| Panel | Nội dung |
|---|---|
| Latency | P50/P95/P99 và TTFT P95, đơn vị ms |
| Traffic | request count hoặc request/phút |
| Errors | error rate, breakdown lỗi, retrieval success |
| Cost | tổng cost theo thời gian và cả cửa sổ, USD |
| Tokens | tổng input/output tokens |
| Quality | trung bình `quality_score`, thang 0–1 |

Đặt time range 60 phút, refresh 15–30 giây nếu hỗ trợ, đơn vị và threshold/SLO line. Đối chiếu ngưỡng chính xác trong `config/dashboard.yaml` (hiện có ví dụ latency P95 ≤ 3000 ms, error rate ≤ 2%, cost ≤ 2.5 USD, quality ≥ 0.75).

Kiểm tra contract:

```powershell
python scripts/validate_dashboard.py
```

Cần `HỢP LỆ: 6/6 panel`. Validator không chứng minh dashboard runtime đang đọc đúng log; cần ảnh dashboard có dữ liệu thật. Xem [DASHBOARD_SETUP.md](DASHBOARD_SETUP.md).

### 4. SLO, alert và runbook

- `config/slo.yaml`: SLO mẫu là 99.5% request thành công và latency ≤ 3000 ms trong 28 ngày; error budget là 0.5%. Với 10,000 requests, ngân sách tương ứng tối đa 50 request không đạt. Giải thích vì sao phù hợp với baseline hoặc nêu lý do khi chỉnh.
- `config/alert_rules.yaml`: thay ba TODO bằng alert theo triệu chứng (latency cao, error tăng, retrieval thấp, v.v.). Mỗi alert cần condition, duration, severity, owner, Slack channel và runbook.
- `docs/alerts.md`: ghi ảnh hưởng tới user, các bước kiểm tra ban đầu và mitigation cho từng alert. Có alert mẫu để tham khảo.

**Đạt CP2 khi:** có ≥10 trace cá nhân với span tree, v1/v2 và rollback có evidence, dashboard runtime đủ sáu panel, validator 6/6, SLO/error budget cùng ba alert/runbook đã giải thích.

## CP3 — Điều tra challenge

**Chỉ làm challenge chính thức sau khi Lab Coach gửi riêng `config/challenge.json` đúng lớp K4-L3B.** Không tự tạo/sửa/lấy file từ lớp khác, không commit/force-add/chia sẻ file này. File đã bị `.gitignore`.

Khi đã nhận file chính thức:

```powershell
python scripts/inject_incident.py
python scripts/load_test.py --challenge --concurrency 5
```

Nếu chưa nhận file, chỉ chạy practice; không gọi `inject_incident.py` thiếu `--scenario`:

```powershell
python scripts/inject_incident.py --scenario rag_slow
python scripts/load_test.py --concurrency 5
python scripts/inject_incident.py --scenario rag_slow --disable
```

Scenario practice có sẵn: `rag_slow`, `tool_fail`, `cost_spike`.

### Quy trình điều tra

1. **Metric:** tìm triệu chứng và khoảng thời gian bất thường.
2. **Log:** lọc `data/logs.jsonl`, tìm request bất thường, ghi log line và `correlation_id`.
3. **Trace:** tìm trace có cùng ID trên Langfuse; xác định span chậm/lỗi.
4. **Kết luận:** chỉ chốt root cause khi metric, log và trace cùng chỉ về một sự cố.
5. **Hành động:** ghi fix action và preventive measure có thể kiểm chứng, như rollback prompt, sửa timeout, thêm alert hoặc test hồi quy.

**Đạt CP3 khi:** report có Challenge ID, khoảng thời gian, metric cụ thể, log/correlation ID, trace ID/span, root cause, fix action và preventive measure. Challenge ID/seed/query phải khớp file đúng lớp.

## CP4 — Report, evidence, kiểm tra cuối và nộp

1. Điền `submission/REPORT.md`: thông tin repo/commit; baseline và kết quả cuối; logging/PII; traces/prompt; dashboard/SLO/alerts; incident; quyết định kỹ thuật, blocker và cách xử lý.
2. Đặt evidence trong `submission/evidence/`. Danh sách đầy đủ xem [SUBMISSION.md](SUBMISSION.md). Các mục gợi ý:
   - `01-pytest`, `02-log-validator`, `03-dashboard-validator`.
   - `04-structured-log`, `05-pii-redaction`.
   - `06-trace-list`, `07-trace-waterfall`, `08-trace-metadata`.
   - `09-prompt-versions`, `10-prompt-rollback`, `11-dashboard-overview`.
   - `12-incident-metric`, `13-incident-log`, `14-incident-trace`.
3. Trong report dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`. Ảnh phải đọc được tên panel, giá trị, time range, ID; che secret/PII.
4. Chạy kiểm tra cuối:

   ```powershell
   python -m pytest -q
   python scripts/validate_logs.py
   python scripts/validate_dashboard.py
   git status --short
   git diff --check
   ```

5. Kiểm tra danh sách file sẽ commit. Không đưa `.env`, `.venv/`, log có PII thô hoặc `config/challenge.json` vào commit. Commit source/config/report/evidence cần thiết vào repo cá nhân.
6. Nộp URL repo cá nhân và commit SHA cuối trên VLearn LMS/Codelabs. Deadline mặc định là 23:59:59 ngày diễn ra lab theo giờ Asia/Ho_Chi_Minh; nếu có thông báo chính thức khác thì theo thông báo đó.

**Đạt CP4 khi:** report/evidence khớp commit cuối, kiểm tra cuối đã chạy, không lộ secret/PII/challenge file, demo giải thích được Metrics → Logs → Traces → Root cause, và đã nộp URL cùng SHA.

## Bảng kiểm nhanh

| CP | Việc chính | Tiêu chí tự kiểm tra |
|---|---|---|
| CP0 | Setup, API, workload, baseline | Health OK; có log/trace; ghi lại baseline |
| CP1 | Correlation ID, metadata, PII | Log validator ≥80/100; log/response nối được; PII đã che |
| CP2 | Trace tree, prompt, dashboard, SLO/alerts | ≥10 traces; rollback có evidence; dashboard 6/6 và runtime |
| CP3 | Điều tra incident/challenge | Metric → log/ID → trace/span → root cause |
| CP4 | Report, evidence và nộp | Đủ evidence trên commit cuối; nộp repo URL + SHA |

## Thuật ngữ cơ bản

- `correlation_id`: mã nối log và trace của cùng request.
- `trace_id`: mã của trace; một trace gồm nhiều span/observation.
- `span`: một bước trong request, như retrieval hoặc generation.
- P50/P95/P99: các mốc phân vị latency; P95 nghĩa là 95% request nhanh bằng hoặc nhanh hơn giá trị đó.
- TTFT: thời gian đến token đầu tiên.
- PII: dữ liệu nhận dạng cá nhân như email, điện thoại, CCCD, số thẻ.
- SLO: mục tiêu chất lượng; error budget là phần không đạt tối đa được phép trong cửa sổ đo.

## Tài liệu tham khảo trong repo

- [Setup và xử lý lỗi](SETUP.md), [checkpoint gốc](CHECKPOINTS.md), [gợi ý debug](GUIDE.md)
- [Dựng dashboard](DASHBOARD_SETUP.md), [dashboard contract](dashboard-spec.md)
- [Prompt versioning](PROMPT_VERSIONING.md), [alerts/runbook](alerts.md)
- [Rubric](RUBRIC.md), [quy định](RULES.md), [hướng dẫn nộp](SUBMISSION.md), [checklist evidence](grading-evidence.md)
- [Report cần điền](../submission/REPORT.md)
