"""Utility helpers for LLM tool schema handling."""

from __future__ import annotations

from typing import Any

UNSUPPORTED_ROOT_SCHEMA_KEYS: frozenset[str] = frozenset(
    {"anyOf", "oneOf", "allOf", "not", "enum"}
)


def sanitize_tool_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Sanitize tool schema for providers that reject root combiners.

    OpenAI and Anthropic reject function/input schemas that include combiners
    (`anyOf`, `oneOf`, `allOf`, `not`) or `enum` at the root level.

    For compatibility, this helper drops unsupported top-level keys and makes
    all root fields optional by setting `required` to an empty list.
    """
    if not UNSUPPORTED_ROOT_SCHEMA_KEYS.intersection(schema):
        return schema

    sanitized_schema = {
        key: value
        for key, value in schema.items()
        if key not in UNSUPPORTED_ROOT_SCHEMA_KEYS
    }
    sanitized_schema["required"] = []
    return sanitized_schema

