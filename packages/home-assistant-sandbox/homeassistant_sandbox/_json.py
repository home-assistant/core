"""Shared JSON coercion for the sandbox client package."""

from typing import Any

from .messages import decode_json, encode_json


def json_safe(value: Any) -> Any:
    """Return ``value`` coerced to plain JSON-safe Python objects."""
    return decode_json(encode_json(value))
