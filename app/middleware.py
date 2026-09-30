from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Mỗi request phải bắt đầu với context sạch, tránh lấy nhầm ID/metadata
        # còn sót lại từ request trước trong cùng worker.
        clear_contextvars()

        # Chỉ nhận ID đúng định dạng req- + 8 ký tự hex. Nếu client gửi thiếu
        # hoặc sai định dạng, tự tạo ID mới để mọi request vẫn có mã hợp lệ.
        incoming_id = request.headers.get("x-request-id", "")
        if re.fullmatch(r"req-[0-9a-fA-F]{8}", incoming_id):
            correlation_id = incoming_id.lower()
        else:
            correlation_id = f"req-{uuid.uuid4().hex[:8]}"

        # Contextvars giúp structlog tự thêm ID này vào mọi log trong request.
        bind_contextvars(correlation_id=correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        try:
            response = await call_next(request)

            # Trả lại ID để client có thể đưa nó vào hỗ trợ/debug; response time
            # cũng hữu ích khi so sánh cảm nhận của client với log server.
            elapsed_ms = (time.perf_counter() - start) * 1000
            response.headers["x-request-id"] = correlation_id
            response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"
            return response
        finally:
            # Dọn context sau request, kể cả khi handler phát sinh exception.
            clear_contextvars()
