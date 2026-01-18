"""Tests for AWS Bedrock entity helpers."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.aws_bedrock.entity import (
    _build_tool_name_maps,
    _clean_schema,
    _convert_messages,
    _sanitize_bedrock_tool_name,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm


def test_convert_messages_skips_ui_only_assistant_between_tool_use_and_result() -> None:
    """Test that UI-only assistant messages are not sent to Bedrock."""
    chat_content: list[conversation.Content] = [
        conversation.UserContent("Turn on the living room lights"),
        conversation.AssistantContent(
            agent_id="test",
            content="I'll help you turn on the lights in the living room.",
            tool_calls=[
                llm.ToolInput(
                    id="tool_1",
                    tool_name="HassTurnOn",
                    tool_args={"area": "living room", "domain": ["light"]},
                )
            ],
        ),
        # This can be injected by HA while the tool runs; it must be skipped.
        conversation.AssistantContent(
            agent_id="test",
            content="Calling HassTurnOn…",
            tool_calls=None,
        ),
        conversation.ToolResultContent(
            agent_id="test",
            tool_call_id="tool_1",
            tool_name="HassTurnOn",
            tool_result={"success": True},
        ),
        conversation.AssistantContent(agent_id="test", content="Done", tool_calls=None),
    ]

    messages = _convert_messages(chat_content)

    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]

    assistant_with_tool = messages[1]
    assert any("toolUse" in part for part in assistant_with_tool["content"])

    # Ensure the UI-only assistant message did not get included.
    assert all(
        part.get("text") != "Calling HassTurnOn…"
        for msg in messages
        for part in msg.get("content", [])
        if isinstance(part, dict)
    )

    # Ensure toolResult follows immediately after toolUse
    tool_result_msg = messages[2]
    assert tool_result_msg["role"] == "user"
    assert any("toolResult" in part for part in tool_result_msg["content"])


def test_clean_schema_keeps_only_supported_fields() -> None:
    """Test schema cleaning for Nova tool requirements."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "My Schema",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "area": {
                "type": "string",
                "description": "Area name",
                "title": "Area",
            },
            "device": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Name"}},
                "required": ["name"],
                "additionalProperties": False,
            },
        },
        "required": ["area"],
    }

    cleaned = _clean_schema(schema)

    assert set(cleaned) <= {"type", "properties", "required"}
    assert cleaned["type"] == "object"
    assert "properties" in cleaned
    assert "required" in cleaned
    assert isinstance(cleaned["required"], list)

    area = cleaned["properties"]["area"]
    assert set(area) <= {
        "type",
        "enum",
        "description",
        "properties",
        "required",
        "items",
    }
    assert area["type"] == "string"


def test_clean_schema_adds_required_when_missing() -> None:
    """Test required is added for object schemas when missing."""
    cleaned = _clean_schema({"type": "object", "properties": {"x": {"type": "string"}}})

    assert cleaned["type"] == "object"
    assert "required" in cleaned
    assert cleaned["required"] == []


def test_sanitize_bedrock_tool_name() -> None:
    """Test Nova-safe tool name sanitization."""
    assert _sanitize_bedrock_tool_name("aws-bedrock-web-search__web_search") == (
        "aws_bedrock_web_search__web_search"
    )
    assert _sanitize_bedrock_tool_name("123bad") == "t_123bad"


def test_convert_messages_maps_tool_names() -> None:
    """Test that toolUse names are mapped to Bedrock-safe names."""

    class _TestTool(llm.Tool):
        name = "aws-bedrock-web-search__web_search"
        description = "Web search"
        parameters = vol.Schema({"q": str})

        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> llm.JsonObjectType:
            raise NotImplementedError

    tool = _TestTool()
    ha_to_bedrock, _ = _build_tool_name_maps([tool])

    chat_content: list[conversation.Content] = [
        conversation.AssistantContent(
            agent_id="test",
            content=None,
            tool_calls=[
                llm.ToolInput(
                    id="tool_1",
                    tool_name=tool.name,
                    tool_args={"q": "hi"},
                )
            ],
        )
    ]

    messages = _convert_messages(chat_content, ha_to_bedrock_tool_name=ha_to_bedrock)
    tool_use = next(
        part["toolUse"] for part in messages[0]["content"] if "toolUse" in part
    )
    assert tool_use["name"] == "aws_bedrock_web_search__web_search"
