# Production label transition evidence

Prompt: `day13-chat`. Các request trong evidence dùng input tổng hợp an toàn, không chứa PII.

| Thời điểm | Correlation ID | Trace ID | Prompt label | Prompt version | Kết quả |
|---|---|---|---|---|---|
| Trước promote | `req-c0200065` | `c6863d8ac64292d2e308a337b5f7cf13` | `production` | `1` | `production` đang trỏ baseline v1. |
| Sau promote | `req-c0200076` | `d88070f551f39d891330a0dee5e39c72` | `production` | `2` | `production` đã trỏ sang candidate v2. |
| Sau rollback | `req-c0200077` | `efad98e37327f730697c84cbb8b7c498` | `production` | `1` | SDK readback xác nhận `production` đã quay về baseline v1. |

Kết luận: ba trace dùng cùng label `production` chứng minh trạng thái v1 trước promote, v2 sau promote, rồi v1 sau rollback. Trace baseline v1 và candidate v2 cũng chứng minh hai request dùng hai prompt version khác nhau.

Nguồn kiểm chứng: `06-trace-list.txt` (trace metadata) và `10-prompt-rollback.txt` (readback sau rollback). Không lưu raw prompt, raw input/output hay API key trong evidence này.
