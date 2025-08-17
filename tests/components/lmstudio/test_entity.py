"""Test LM Studio entity utility functions."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.conversation import SystemContent, UserContent
from homeassistant.components.lmstudio.entity import (
    _convert_message_to_openai,
    _format_tool,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm


class TestToolWithDescription(llm.Tool):
    """Test tool for testing _format_tool function with description."""

    name = "test_tool"
    description = "Test tool description"
    parameters = vol.Schema({vol.Required("param1"): str})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Call the tool."""
        return {"result": "test"}


class TestToolWithoutDescription(llm.Tool):
    """Test tool for testing _format_tool function without description."""

    name = "test_tool"
    description = None
    parameters = vol.Schema({vol.Required("param1"): str})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        """Call the tool."""
        return {"result": "test"}


def test_format_tool_with_description() -> None:
    """Test _format_tool with tool that has description."""
    tool = TestToolWithDescription()

    result = _format_tool(tool, None)

    expected = {
        "type": "function",
        "function": {
            "name": "test_tool",
            "description": "Test tool description",
            "parameters": {
                "type": "object",
                "properties": {"param1": {"type": "string"}},
                "required": ["param1"],
            },
        },
    }
    assert result == expected


def test_format_tool_without_description() -> None:
    """Test _format_tool with tool that has no description."""
    tool = TestToolWithoutDescription()

    result = _format_tool(tool, None)

    expected = {
        "type": "function",
        "function": {
            "name": "test_tool",
            "parameters": {
                "type": "object",
                "properties": {"param1": {"type": "string"}},
                "required": ["param1"],
            },
        },
    }
    assert result == expected


def test_convert_message_system() -> None:
    """Test _convert_message_to_openai for system message."""
    message = SystemContent(content="You are a helpful assistant")

    result = _convert_message_to_openai(message)

    expected = {"role": "system", "content": "You are a helpful assistant"}
    assert result == expected


def test_convert_message_user_string() -> None:
    """Test _convert_message_to_openai for user message with string content."""
    message = UserContent(content="Hello, how are you?")

    result = _convert_message_to_openai(message)

    expected = {"role": "user", "content": "Hello, how are you?"}
    assert result == expected
