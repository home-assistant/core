"""Broadlink-compatible codec helpers."""

from base64 import b64decode, b64encode
from binascii import Error as BinasciiError
from importlib import import_module
from typing import Any


def encode_raw_to_broadlink_base64(
    timings: list[int], modulation: int | None = None
) -> str:
    """Encode timings to Broadlink packet format and wrap as base64."""
    del modulation
    try:
        module = import_module("broadlink.remote")
        broadlink_pulses_to_data = module.pulses_to_data
    except (ImportError, AttributeError) as err:
        raise ValueError("Broadlink codec unavailable in current environment") from err

    packet = broadlink_pulses_to_data([abs(value) for value in timings])
    return b64encode(packet).decode("ascii")


def decode_broadlink_base64_to_raw_timings(payload: Any) -> list[int] | None:
    """Decode Broadlink base64 packet into alternating signed timings."""
    if not isinstance(payload, str) or not payload:
        return None
    try:
        packet = b64decode(payload)
    except (BinasciiError, TypeError, ValueError):
        return None

    try:
        module = import_module("broadlink.remote")
        broadlink_data_to_pulses = module.data_to_pulses
    except (ImportError, AttributeError):
        return None

    pulses = broadlink_data_to_pulses(packet)
    if not isinstance(pulses, list):
        return None
    return [
        int(value) if index % 2 == 0 else -int(value)
        for index, value in enumerate(pulses)
    ]
