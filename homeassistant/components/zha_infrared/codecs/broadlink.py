"""Broadlink-compatible codec helpers."""

from __future__ import annotations

from base64 import b64decode, b64encode
from typing import Any


def encode_raw_to_broadlink_base64(
    timings: list[int], modulation: int | None = None
) -> str:
    """Encode timings to Broadlink packet format and wrap as base64."""
    del modulation
    try:
        from broadlink.remote import pulses_to_data as _bl_pulses_to_data
    except ImportError as err:
        raise ValueError("Broadlink codec unavailable in current environment") from err

    packet = _bl_pulses_to_data([abs(value) for value in timings])
    return b64encode(packet).decode("ascii")


def decode_broadlink_base64_to_raw_timings(payload: Any) -> list[int] | None:
    """Decode Broadlink base64 packet into alternating signed timings."""
    if not isinstance(payload, str) or not payload:
        return None
    try:
        packet = b64decode(payload)
    except Exception:
        return None

    try:
        from broadlink.remote import data_to_pulses as _bl_data_to_pulses
    except ImportError:
        return None

    pulses = _bl_data_to_pulses(packet)
    if not isinstance(pulses, list):
        return None
    timings = [int(value) if index % 2 == 0 else -int(value) for index, value in enumerate(pulses)]
    return timings
