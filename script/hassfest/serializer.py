"""Hassfest utils."""
from __future__ import annotations

from typing import Any


def _dict_to_str(data: dict) -> str:
    """Return a string representation of a dict."""
    items = [f"'{key}':{to_string(value)}" for key, value in data.items()]
    result = "{"
    for item in items:
        result += str(item)
        result += ","
    result += "}"
    return result


def _list_to_str(data: dict) -> str:
    """Return a string representation of a list."""
    items = [to_string(value) for value in data]
    result = "["
    for item in items:
        result += str(item)
        result += ","
    result += "]"
    return result


def to_string(data: Any) -> str:
    """Return a string representation of the input."""
    if isinstance(data, dict):
        return _dict_to_str(data)
    if isinstance(data, list):
        return _list_to_str(data)
    if isinstance(data, str):
        return "'" + data + "'"
    return data
