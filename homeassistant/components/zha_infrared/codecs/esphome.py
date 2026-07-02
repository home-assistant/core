"""ESPHome-style raw timings codec helpers."""

from __future__ import annotations

from typing import Any


def encode_raw_passthrough(timings: list[int], modulation: int | None = None) -> list[int]:
    """Return timings unchanged for transports expecting raw arrays."""
    del modulation
    return timings


def decode_raw_passthrough(payload: Any) -> list[int] | None:
    """Return payload when it already matches raw timings shape."""
    if not isinstance(payload, list):
        return None
    return [int(item) for item in payload]
