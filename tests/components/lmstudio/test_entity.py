"""Test LM Studio entity utility functions."""

from __future__ import annotations

from homeassistant.components.conversation import Content
from homeassistant.components.lmstudio.entity import (
    _convert_message_to_openai,
    _format_tool,
)
from homeassistant.helpers import llm


def test_format_tool_with_description() -> None:
    """Test _format_tool with tool that has description."""
    tool = llm.Tool(
        name="test_tool",
        description="Test tool description",
        parameters={"type": "object", "properties": {"param1": {"type": "string"}}},
    )

    result = _format_tool(tool, None)

    expected = {
        "type": "function",
        "function": {
            "name": "test_tool",
            "description": "Test tool description",
            "parameters": {
                "type": "object",
                "properties": {"param1": {"type": "string"}},
            },
        },
    }
    assert result == expected


def test_format_tool_without_description() -> None:
    """Test _format_tool with tool that has no description."""
    tool = llm.Tool(
        name="test_tool",
        description=None,
        parameters={"type": "object", "properties": {"param1": {"type": "string"}}},
    )

    result = _format_tool(tool, None)

    expected = {
        "type": "function",
        "function": {
            "name": "test_tool",
            "parameters": {
                "type": "object",
                "properties": {"param1": {"type": "string"}},
            },
        },
    }
    assert result == expected


def test_convert_message_system() -> None:
    """Test _convert_message_to_openai for system message."""
    message = Content(role="system", content="You are a helpful assistant")

    result = _convert_message_to_openai(message)

    expected = {"role": "system", "content": "You are a helpful assistant"}
    assert result == expected


def test_convert_message_user_string() -> None:
    """Test _convert_message_to_openai for user message with string content."""
    message = Content(role="user", content="Hello, how are you?")

    result = _convert_message_to_openai(message)

    expected = {"role": "user", "content": "Hello, how are you?"}
    assert result == expected
