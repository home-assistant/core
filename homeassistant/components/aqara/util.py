"""Utility methods for this integration."""
from __future__ import annotations


def remap_value(
    value: float | int,
    from_min: float | int = 0,
    from_max: float | int = 255,
    to_min: float | int = 0,
    to_max: float | int = 255,
    reverse: bool = False,
) -> float:
    """Remap a value from its current range, to a new range."""
    if reverse:
        value = from_max - value + from_min
    return ((value - from_min) / (from_max - from_min)) * (to_max - to_min) + to_min


def string_dot_to_underline(data: str) -> str:
    """Replace dot to underline. lumi.53523534__4.1.85     ->  lumi_53523534__4_1_85"""  #
    new_data = data.replace(".", "_")
    return new_data


def string_underline_to_dot(data: str) -> str:
    """Replaceunderline to dot. lumi_53523534__4_1_85    ->  lumi.53523534__4.1.85"""
    new_data = data.replace("__", "--").replace("_", ".").replace("--", "__")
    return new_data
