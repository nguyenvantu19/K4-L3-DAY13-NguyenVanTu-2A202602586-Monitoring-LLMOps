from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, str] = {
    # Email đơn giản; thay toàn bộ địa chỉ bằng nhãn để giữ ngữ cảnh mà không lộ giá trị.
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    # Số điện thoại VN dạng 0xxxxxxxxx hoặc +84xxxxxxxxx, cho phép dấu cách/dấu chấm/gạch nối.
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    # CCCD Việt Nam có 12 chữ số.
    "cccd": r"\b\d{12}\b",
    # Số thẻ mẫu gồm 16 chữ số, có thể ngăn nhóm bằng khoảng trắng hoặc dấu gạch.
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
}


def scrub_text(text: str) -> str:
    """Thay các mẫu PII đã biết bằng nhãn, giữ phần văn bản không nhạy cảm."""
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
