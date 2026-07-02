"""Tuya/Zosung codec helpers."""

from base64 import b64decode, b64encode
from binascii import Error as BinasciiError
import json
import struct
from typing import Any


def encode_raw_to_tuya_base64(timings: list[int], modulation: int | None = None) -> str:
    """Encode signed raw timings to Tuya TS1201-compatible base64."""
    del modulation
    payload = bytearray()
    for timing in timings:
        duration = min(abs(timing), 0xFFFF)
        payload.extend(struct.pack("<H", duration))
    return b64encode(payload).decode("ascii")


def decode_tuya_payload_to_raw_timings(payload: Any) -> list[int] | None:
    """Decode Tuya payload into alternating signed timings."""
    if not isinstance(payload, str) or not payload:
        return None

    extracted = _extract_embedded_key_code(payload)
    if extracted is not None:
        payload = extracted

    try:
        raw = _b64decode_loose(payload)
    except (BinasciiError, TypeError, ValueError):
        return None
    if not raw or len(raw) % 2 != 0:
        return None

    timings: list[int] = []
    for index in range(0, len(raw), 2):
        duration = struct.unpack("<H", raw[index : index + 2])[0]
        timings.append(duration if (index // 2) % 2 == 0 else -duration)
    return timings


def _b64decode_loose(value: str) -> bytes:
    """Decode base64 string with tolerant padding behavior."""
    padding = (-len(value)) % 4
    if padding:
        value = f"{value}{'=' * padding}"
    return b64decode(value)


def _extract_embedded_key_code(payload: str) -> str | None:
    """Extract key_code from JSON payloads returned by TS1201 learn flow."""
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if isinstance(parsed, dict):
        if isinstance(parsed.get("key_code"), str):
            return parsed["key_code"]
        key1 = parsed.get("key1")
        if isinstance(key1, dict) and isinstance(key1.get("key_code"), str):
            return key1["key_code"]
    return None
