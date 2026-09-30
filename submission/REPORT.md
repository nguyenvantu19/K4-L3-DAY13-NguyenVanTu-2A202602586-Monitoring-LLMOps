# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:**
- **MSSV:**
- **Lớp:** K4-L3B
- **Repository URL:**
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-<MSSV>`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Log validator trước CP1 | `evidence/00-pre-cp1-log-baseline.txt` |
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.txt` |
| PII redaction | `evidence/05-pii-redaction.txt` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback và thay đổi label `production` | `evidence/10-production-label-transition.md`, `evidence/10-prompt-rollback.txt` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.txt`, `evidence/12-incident-metric-comparison.txt` |
| Incident log | `evidence/13-incident-log.txt` |
| Incident trace | `evidence/14-incident-trace.txt` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 50/100 trước khi xoay log baseline (`evidence/00-pre-cp1-log-baseline.txt`) | 100/100 (26 log, 0 PII leak) | ID `req-1a2b3c4d` nối request, response và log; metadata đủ. Xem evidence 02, 04, 05. |
| `validate_dashboard.py` | | | |
| `pytest` | | | |
| Số traces hợp lệ | | | |
| Số PII leak | | | |
| Latency P95 / TTFT P95 | | | |
| Retrieval success rate | | | |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware nhận `x-request-id` theo dạng `req-<8 ký tự hex>` hoặc sinh ID mới nếu thiếu/sai. ID được bind vào log context, trả qua response header và response body.
- **Các metadata được ghi vào structured log:** `user_id_hash`, `session_id`, `feature`, `model`, `env` cùng `correlation_id`. `user_id` được hash trước khi ghi.
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` chạy trước JSON renderer/file writer và thay email, điện thoại Việt Nam, CCCD, thẻ thanh toán bằng nhãn `[REDACTED_*]`.
- **Cách kiểm chứng kết quả:** `validate_logs.py` đạt 100/100; 0 PII leak. Request thử nghiệm `req-1a2b3c4d` có cùng ID ở response header/body và hai log event `request_received`/`response_sent`. Evidence: `evidence/02-log-validator.txt`, `evidence/04-structured-log.txt`, `evidence/05-pii-redaction.txt`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** API dùng key cá nhân trong `.env`; workload CP2 riêng chỉ gửi câu hỏi tổng hợp, không dùng các dòng mẫu chứa PII. Correlation ID bắt đầu bằng `req-c020` để lọc trong log/trace.
- **Cấu trúc root/retrieval/generation observations:** `day13-agent-request` → `lab-agent-run` → `retrieval` (`retriever`) và `llm-generation` (`generation`). Input/output thô bị tắt capture; generation ghi model, token usage, ước tính cost và prompt reference.
- **Cách nối trace với log:** root metadata có `correlation_id`, cùng giá trị được ghi ở các event `request_received`/`response_sent`.
- **Prompt name:** `day13-chat`; template cần ba biến `{{feature}}`, `{{docs}}`, `{{message}}`.
- **Version/label baseline:** v1, label `baseline` (ban đầu `production` cũng trỏ v1).
- **Version/label candidate:** v2, label `candidate`.
- **Trace ID của mỗi version:** baseline v1 `5c6b1e8762a634d17551d6b468b37406` (`req-c0200072`); candidate v2 `6d8a3e513ae0519278229674a43907a9` (`req-c0200075`). Cả hai dùng cùng một câu hỏi tổng hợp không có PII.
- **Cách promote và rollback `production`:** trước promote, `production` dùng v1 ở trace `c6863d8ac64292d2e308a337b5f7cf13` (`req-c0200065`). Sau promote, `production` dùng v2 ở trace `d88070f551f39d891330a0dee5e39c72` (`req-c0200076`). Sau rollback, `production` quay về v1 ở trace `efad98e37327f730697c84cbb8b7c498` (`req-c0200077`). Xem `evidence/10-production-label-transition.md` và `evidence/10-prompt-rollback.txt`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** `scripts/render_dashboard.py` đọc log JSONL đã scrub, lọc 60 phút, tự refresh mỗi 30 giây; có latency P50/P95/P99 + TTFT P95, traffic, lỗi/retrieval success, cost, tokens và quality. Validator đạt 6/6. Bản runtime: `evidence/11-dashboard-overview.html`.
- **SLO và lý do chọn:** 99.5% request thành công trong 3 giây ở cửa sổ 28 ngày. Ngưỡng 3 giây đo thời gian người dùng chờ toàn bộ retrieval + generation; cần rà soát lại theo baseline thực tế.
- **Cách tính error budget:** 100% - 99.5% = 0.5%; với 10,000 request, tối đa 50 request được phép không đạt SLO.
- **Ba alert và runbook tương ứng:** latency P95 > 3 giây/5 phút (warning), tỷ lệ lỗi > 2%/5 phút (critical), retrieval success < 90%/10 phút (warning); đều báo Slack `#k4-l3b-alerts`, owner `student-2A202602586`, hướng dẫn tại `docs/alerts.md`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (K4, seed 1312), incident `rag_slow`, feature bị ảnh hưởng `monitoring`.
- **Khoảng thời gian điều tra:** 2026-09-30 09:30:39Z–09:30:52Z; workload challenge có 5 request với concurrency 5.
- **Triệu chứng từ metrics:** Ngưỡng challenge là latency ≤ 2.000 ms. Cả 5 response mất 2.652–2.654 ms, P95 là 2.654 ms; TTFT ổn định 50 ms, error rate 0% và retrieval success 100%. Lượt chạy lại có baseline P95 154 ms tại 09:36:52Z–09:36:53Z, sau đó P95 tăng lên 2.654 ms tại 09:36:56Z–09:37:07Z khi bật `rag_slow` (+2.500 ms). Xem `evidence/12-incident-metric.txt` và `evidence/12-incident-metric-comparison.txt`.
- **Log line và correlation ID liên quan:** `response_sent` của `req-0bfe354b` ghi `latency_ms=2653`, `ttft_ms=50`, `tool_name=retrieval`, `tool_success=true`; request received và response sent có cùng correlation ID. Xem `evidence/13-incident-log.txt`.
- **Trace ID và span gây ảnh hưởng:** Trace `47307406e153f05f3271348b3aaeaa1f` cùng `correlation_id=req-0bfe354b` có các span `lab-agent-run`, `retrieval`, `llm-generation`; span `retrieval` mất 2.505 ms. Cả 5 trace challenge đều dùng prompt `production` v2 và có retrieval 2.501–2.505 ms. Xem `evidence/14-incident-trace.txt`.
- **Root cause:** Practice incident `rag_slow` làm chậm retrieval khoảng 2,5 giây. Vì retrieval vẫn thành công và TTFT thấp, đây là latency của dependency/retriever, không phải lỗi API hay failure của generation.
- **Fix action:** Đã tắt `rag_slow` bằng `scripts/inject_incident.py --disable` và xác nhận `/health` trả `rag_slow: false`.
- **Preventive measure:** Giữ alert `UserWaitsTooLong` cho P95 latency > 3 giây và đề xuất thêm cảnh báo sớm khi P95 retrieval > 2 giây. Runbook sẽ kiểm tra duration retriever theo correlation ID trước khi latency tổng vượt SLO.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
