"""Tests for the Interactions API helpers in Google Generative AI Conversation."""

from types import SimpleNamespace
from unittest.mock import MagicMock

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
from homeassistant.components.google_generative_ai_conversation.entity import (
    ContentDetails,
    PartDetails,
)
from homeassistant.components.google_generative_ai_conversation.interactions import (
    build_interaction_request,
    create_safety_settings,
    format_response_format,
    format_tools_for_interactions,
    transform_interactions_stream,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
        {
            "type": "function",
            "name": "test_tool",
            "description": "A test tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "count": {"type": "integer"},
                },
                "required": ["location", "count"],
                "additionalProperties": False,
            },
        }
    ]


def test_format_tools_google_search() -> None:
    """Test formatting Google Search tool for Interactions API."""
    formatted = format_tools_for_interactions([], enable_google_search=True)
    assert formatted == [{"type": "google_search"}]

    formatted_none = format_tools_for_interactions(None, enable_google_search=True)
    assert formatted_none == [{"type": "google_search"}]


def test_format_response_format() -> None:
    """Test formatting response_format for structured output."""
    assert format_response_format(None) is None

    schema = probatio.Schema({probatio.Required("status"): str})
    formatted = format_response_format(schema)
    assert formatted == {
        "type": "text",
        "mime_type": "application/json",
        "schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
            },
            "required": ["status"],
            "additionalProperties": False,
        },
    }


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
    tools = [{"type": "google_search"}]
    response_format = {"type": "text", "mime_type": "application/json", "schema": {}}

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


async def test_transform_interactions_stream_text() -> None:
    """Test streaming text events from Interactions API."""
    chat_log = MagicMock()

    async def mock_events():
        yield SimpleNamespace(
            event_type="step.start",
            step=SimpleNamespace(type="model_output"),
        )
        yield SimpleNamespace(
            event_type="step.delta",
            delta=SimpleNamespace(type="text", text="Hello, "),
        )
        yield SimpleNamespace(
            event_type="step.delta",
            delta=SimpleNamespace(type="text", text="world!"),
            metadata=SimpleNamespace(
                total_usage=SimpleNamespace(
                    total_input_tokens=10,
                    total_cached_tokens=0,
                    total_output_tokens=5,
                )
            ),
        )
        yield SimpleNamespace(event_type="step.stop")
        yield SimpleNamespace(
            event_type="interaction.completed",
            interaction=SimpleNamespace(status="completed"),
        )

    deltas = [
        delta async for delta in transform_interactions_stream(chat_log, mock_events())
    ]

    assert deltas == [
        {"role": "assistant"},
        {"content": "Hello, "},
        {"content": "world!"},
    ]

    chat_log.async_trace.assert_called_with(
        {
            "stats": {
                "input_tokens": 10,
                "cached_input_tokens": 0,
                "output_tokens": 5,
            }
        }
    )


async def test_transform_interactions_stream_thinking_and_signature() -> None:
    """Test streaming thinking content and signatures from Interactions API."""
    chat_log = MagicMock()

    async def mock_events():
        yield SimpleNamespace(
            event_type="step.start",
            step=SimpleNamespace(type="thought"),
        )
        yield SimpleNamespace(
            event_type="step.delta",
            delta=SimpleNamespace(type="thought", text="Thinking deeply..."),
        )
        yield SimpleNamespace(
            event_type="step.delta",
            delta=SimpleNamespace(
                type="thought_signature",
                signature=b"test_sig_123",
            ),
        )
        yield SimpleNamespace(event_type="step.stop")
        yield SimpleNamespace(
            event_type="step.start",
            step=SimpleNamespace(type="model_output"),
        )
        yield SimpleNamespace(
            event_type="step.delta",
            delta=SimpleNamespace(type="text", text="Result."),
        )
        yield SimpleNamespace(event_type="step.stop")

    deltas = [
        delta async for delta in transform_interactions_stream(chat_log, mock_events())
    ]

    assert deltas[0] == {"role": "assistant"}
    assert deltas[1] == {"thinking_content": "Thinking deeply..."}
    assert deltas[2] == {"content": "Result."}
    assert deltas[3] == {
        "native": ContentDetails(
            part_details=[
                PartDetails(
                    part_type="thought",
                    index=18,
                    length=0,
                    thought_signature="dGVzdF9zaWdfMTIz",
                )
            ]
        )
    }


async def test_transform_interactions_stream_thought_summary_nested_content() -> None:
    """Test streaming thought summary with nested content text."""
    chat_log = MagicMock()

    async def mock_events():
        yield SimpleNamespace(
            event_type="step.start",
            step=SimpleNamespace(type="thought"),
        )
        yield SimpleNamespace(
            event_type="step.delta",
            delta=SimpleNamespace(
                type="thought_summary",
                text=None,
                content=SimpleNamespace(type="text", text="Summarized reasoning"),
            ),
        )
        yield SimpleNamespace(event_type="step.stop")

    deltas = [
        delta async for delta in transform_interactions_stream(chat_log, mock_events())
    ]

    assert deltas == [
        {"role": "assistant"},
        {"thinking_content": "Summarized reasoning"},
    ]


async def test_transform_interactions_stream_tool_calls_streamed() -> None:
    """Test streaming tool calls with argument deltas from Interactions API."""
    chat_log = MagicMock()

    async def mock_events():
        yield SimpleNamespace(
            event_type="step.start",
            step=SimpleNamespace(
                type="function_call",
                id="call_123",
                name="turn_on",
                signature="sig_call",
            ),
        )
        yield SimpleNamespace(
            event_type="step.delta",
            delta=SimpleNamespace(
                type="arguments_delta",
                arguments='{"entity_id": ',
            ),
        )
        yield SimpleNamespace(
            event_type="step.delta",
            delta=SimpleNamespace(
                type="arguments_delta",
                arguments='"light.living_room"}',
            ),
        )
        yield SimpleNamespace(event_type="step.stop")

    deltas = [
        delta async for delta in transform_interactions_stream(chat_log, mock_events())
    ]

    assert deltas[0] == {"role": "assistant"}
    assert deltas[1] == {
        "tool_calls": [
            llm.ToolInput(
                tool_name="turn_on",
                tool_args={"entity_id": "light.living_room"},
                id="call_123",
            )
        ]
    }
    assert deltas[2] == {
        "native": ContentDetails(
            part_details=[
                PartDetails(
                    part_type="function_call",
                    index=0,
                    length=0,
                    thought_signature="sig_call",
                )
            ]
        )
    }


async def test_transform_interactions_stream_prepopulated_tool_calls() -> None:
    """Test tool calls with pre-populated arguments from Interactions API."""
    chat_log = MagicMock()

    async def mock_events():
        yield SimpleNamespace(
            event_type="step.start",
            step=SimpleNamespace(
                type="function_call",
                id="call_456",
                name="turn_off",
                arguments={"entity_id": "switch.ac"},
            ),
        )
        yield SimpleNamespace(event_type="step.stop")

    deltas = [
        delta async for delta in transform_interactions_stream(chat_log, mock_events())
    ]

    assert deltas[0] == {"role": "assistant"}
    assert deltas[1] == {
        "tool_calls": [
            llm.ToolInput(
                tool_name="turn_off",
                tool_args={"entity_id": "switch.ac"},
                id="call_456",
            )
        ]
    }


async def test_transform_interactions_stream_error_event() -> None:
    """Test handling error event in stream."""
    chat_log = MagicMock()

    async def mock_events():
        yield SimpleNamespace(
            event_type="error",
            error=SimpleNamespace(message="Resource exhausted"),
        )

    with pytest.raises(HomeAssistantError, match="Resource exhausted"):
        async for _ in transform_interactions_stream(chat_log, mock_events()):
            pass


async def test_transform_interactions_stream_status_update_failed() -> None:
    """Test handling failed interaction.status_update event."""
    chat_log = MagicMock()

    async def mock_events():
        yield SimpleNamespace(
            event_type="interaction.status_update",
            status="failed",
        )

    with pytest.raises(HomeAssistantError, match="Status: failed"):
        async for _ in transform_interactions_stream(chat_log, mock_events()):
            pass


async def test_transform_interactions_stream_failed_interaction() -> None:
    """Test handling failed status in stream."""
    chat_log = MagicMock()

    async def mock_events():
        yield SimpleNamespace(
            event_type="interaction.completed",
            interaction=SimpleNamespace(status="failed"),
        )

    with pytest.raises(HomeAssistantError, match="Status: failed"):
        async for _ in transform_interactions_stream(chat_log, mock_events()):
            pass
