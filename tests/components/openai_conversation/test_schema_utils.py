"""Tests for tool schema sanitization."""

from __future__ import annotations

from homeassistant.helpers.llm_schema import sanitize_tool_schema

HASS_START_TIMER_SCHEMA = {
    "type": "object",
    "properties": {
        "hours": {"type": "integer", "minimum": 0},
        "minutes": {"type": "integer", "minimum": 0},
        "seconds": {"type": "integer", "minimum": 0},
        "name": {"type": "string"},
        "conversation_command": {"type": "string"},
    },
    "required": [],
    "anyOf": [
        {"required": ["hours"]},
        {"required": ["minutes"]},
        {"required": ["seconds"]},
    ],
}


def test_sanitize_tool_schema_keeps_clean_schema() -> None:
    """Return schema unchanged when root does not contain unsupported keys."""
    schema = {
        "type": "object",
        "properties": {"entity_id": {"type": "string"}},
        "required": ["entity_id"],
    }

    assert sanitize_tool_schema(schema) == schema


def test_sanitize_tool_schema_removes_unsupported_root_keys() -> None:
    """Drop unsupported root keys and force empty required list."""
    schema = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "required": ["x"],
        "anyOf": [{"required": ["x"]}],
        "enum": ["a", "b"],
    }

    result = sanitize_tool_schema(schema)

    assert "anyOf" not in result
    assert "enum" not in result
    assert result["required"] == []


def test_sanitize_tool_schema_keeps_nested_combiners() -> None:
    """Keep nested combiners because only root-level keys are sanitized."""
    schema = {
        "type": "object",
        "properties": {
            "duration": {
                "anyOf": [{"type": "integer"}, {"type": "string"}],
            }
        },
    }

    result = sanitize_tool_schema(schema)

    assert "anyOf" in result["properties"]["duration"]


def test_sanitize_tool_schema_does_not_mutate_input() -> None:
    """Do not mutate the original schema dict."""
    schema = {
        "type": "object",
        "properties": {"x": {"type": "string"}},
        "anyOf": [{"required": ["x"]}],
    }

    _ = sanitize_tool_schema(schema)

    assert "anyOf" in schema


def test_sanitize_tool_schema_hass_start_timer_schema() -> None:
    """Sanitize the real timer schema pattern that triggers provider errors."""
    result = sanitize_tool_schema(HASS_START_TIMER_SCHEMA)

    assert "anyOf" not in result
    assert result["type"] == "object"
    assert result["required"] == []
    assert "hours" in result["properties"]
