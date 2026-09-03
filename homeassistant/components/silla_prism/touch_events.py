"""Helpers for parsing Prism touch event MQTT payloads."""

import re
from typing import Any

_INTEGER_RE = re.compile(r"-?\d+")
_TEXT_SEQUENCES = {
    "single": (1,),
    "singolo": (1,),
    "double": (2,),
    "doppio": (2,),
    "long": (3,),
    "lungo": (3,),
    "pressione_lunga": (3,),
}


def normalize_touch_payload(payload: Any) -> tuple[int, ...] | None:
    """Return a normalized touch event sequence from a Prism MQTT payload."""
    if payload is None:
        return None
    if isinstance(payload, bytes):
        payload = payload.decode(errors="ignore")
    text = str(payload).strip().strip('"').strip("'")
    if not text:
        return None

    normalized_text = text.lower().replace("-", "_").replace(" ", "_")
    for marker, sequence in _TEXT_SEQUENCES.items():
        if marker in normalized_text:
            return sequence

    values = tuple(int(match) for match in _INTEGER_RE.findall(text))
    return values or None


def touch_payload_matches(
    payload: Any, accepted_sequences: tuple[tuple[int, ...], ...]
) -> bool:
    """Return True when a Prism touch payload matches one accepted event shape."""
    sequence = normalize_touch_payload(payload)
    return sequence in accepted_sequences if sequence is not None else False
