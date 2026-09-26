"""Tests for the Interactions API helpers in Google Generative AI Conversation."""

from typing import override

from google.genai import interactions
from google.genai.types import HarmCategory
import probatio
import pytest

from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_DANGEROUS_BLOCK_THRESHOLD,
    CONF_HARASSMENT_BLOCK_THRESHOLD,
    CONF_HATE_BLOCK_THRESHOLD,
    CONF_MAX_TOKENS,
    CONF_SEXUAL_BLOCK_THRESHOLD,
    CONF_TEMPERATURE,
    CONF_THINKING_LEVEL,
    CONF_TOP_K,
    CONF_TOP_P,
    RECOMMENDED_CHAT_MODEL,
)
from homeassistant.components.google_generative_ai_conversation.interactions import (
    build_interaction_request,
    create_safety_settings,
    format_response_format,
    format_tools_for_interactions,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm


def test_format_tools_for_interactions() -> None:
    """Test formatting LLM tools for Interactions API."""

    class MockTool(llm.Tool):
        name = "test_tool"
        description = "A test tool"
        parameters = probatio.Schema(
            {
                probatio.Required("location"): str,
                probatio.Required("count"): int,
            }
        )

        @override
        async def async_call(
            self,
            hass: HomeAssistant,
            tool_input: llm.ToolInput,
            llm_context: llm.LLMContext,
        ) -> llm.ToolResult:
            return llm.ToolResult(data={})

    tool = MockTool()

    formatted = format_tools_for_interactions([tool])
    assert formatted == [
        interactions.Function(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["location", "count"],
                "additionalProperties": False,
            },
        )
    ]


def test_format_tools_google_search() -> None:
    """Test formatting Google Search tool for Interactions API."""
    formatted = format_tools_for_interactions([], enable_google_search=True)
    assert formatted == [interactions.GoogleSearch()]

    formatted_none = format_tools_for_interactions(None, enable_google_search=True)
    assert formatted_none == [interactions.GoogleSearch()]


def test_format_response_format() -> None:
    """Test formatting response_format for structured output."""
    assert format_response_format(None) is None

    schema = probatio.Schema({probatio.Required("status"): str})
    formatted = format_response_format(schema)
    assert formatted == interactions.TextResponseFormat(
        type="text",
        mime_type="application/json",
        schema_={
            "type": "object",
            "properties": {
                "status": {"type": "string"},
            },
            "required": ["status"],
            "additionalProperties": False,
        },
    )


def test_create_safety_settings() -> None:
    """Test creating safety settings from options."""
    options = {
        CONF_HATE_BLOCK_THRESHOLD: "BLOCK_LOW_AND_ABOVE",
        CONF_HARASSMENT_BLOCK_THRESHOLD: "BLOCK_MEDIUM_AND_ABOVE",
        CONF_DANGEROUS_BLOCK_THRESHOLD: "BLOCK_ONLY_HIGH",
        CONF_SEXUAL_BLOCK_THRESHOLD: "BLOCK_NONE",
    }
    settings = create_safety_settings(options)
    assert len(settings) == 4
    categories = {s.category: s.threshold for s in settings}
    assert categories[HarmCategory.HARM_CATEGORY_HATE_SPEECH] == "BLOCK_LOW_AND_ABOVE"
    assert categories[HarmCategory.HARM_CATEGORY_HARASSMENT] == "BLOCK_MEDIUM_AND_ABOVE"
    assert categories[HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT] == "BLOCK_ONLY_HIGH"
    assert categories[HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT] == "BLOCK_NONE"


def test_build_interaction_request_store_false_enforced() -> None:
    """Test build_interaction_request strictly enforces store=False."""
    request = build_interaction_request(
        model=RECOMMENDED_CHAT_MODEL,
        input_content="Hello world",
    )
    assert request["store"] is False
    assert request["stream"] is True

    with pytest.raises(
        ValueError,
        match="Home Assistant interactions must be stateless \\(store=False\\)",
    ):
        build_interaction_request(
            model=RECOMMENDED_CHAT_MODEL,
            input_content="Hello world",
            store=True,
        )


def test_build_interaction_request_full_parameters() -> None:
    """Test build_interaction_request with comprehensive parameters."""
    options = {
        CONF_CHAT_MODEL: "gemini-3.1-flash-lite",
        CONF_TEMPERATURE: 0.7,
        CONF_TOP_P: 0.9,
        CONF_TOP_K: 40,
        CONF_MAX_TOKENS: 1500,
        CONF_THINKING_LEVEL: "high",
    }
    safety_settings = create_safety_settings({})
    tools = [interactions.GoogleSearch()]
    response_format = interactions.TextResponseFormat(
        type="text", mime_type="application/json", schema_={}
    )

    request = build_interaction_request(
        model="gemini-3.1-flash-lite",
        input_content=[
            {"type": "user_input", "content": [{"type": "text", "text": "Hi"}]}
        ],
        options=options,
        system_instruction="You are a helpful assistant.",
        tools=tools,
        response_format=response_format,
        safety_settings=safety_settings,
        stream=True,
    )

    assert request["model"] == "gemini-3.1-flash-lite"
    assert request["store"] is False
    assert request["stream"] is True
    assert request["system_instruction"] == "You are a helpful assistant."
    assert request["tools"] == tools
    assert request["response_format"] == response_format
    assert request["safety_settings"] == safety_settings
    assert request["generation_config"] == {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "max_output_tokens": 1500,
        "thinking_level": "high",
    }
