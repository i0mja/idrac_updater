"""Very small symmetric encryption utilities using XOR and base64."""

import base64
from itertools import cycle


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(data, cycle(key)))


def encrypt_data(data: str, secret: str) -> str:
    raw = data.encode("utf-8")
    xored = _xor_bytes(raw, secret.encode("utf-8"))
    return base64.urlsafe_b64encode(xored).decode("utf-8")


def decrypt_data(data: str, secret: str) -> str:
    try:
        raw = base64.urlsafe_b64decode(data.encode("utf-8"))
    except Exception:
        return ""
    xored = _xor_bytes(raw, secret.encode("utf-8"))
    return xored.decode("utf-8", errors="ignore")
