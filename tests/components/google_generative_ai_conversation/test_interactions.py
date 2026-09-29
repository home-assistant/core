"""Tests for the Interactions API helpers in Google Generative AI Conversation."""

from typing import override
from unittest.mock import AsyncMock, MagicMock

from google.genai import interactions
import probatio
import pytest

from homeassistant.components import conversation
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    CONF_MAX_TOKENS,
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
    convert_chat_log_to_interactions_steps,
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
        stream=True,
    )

    assert request["model"] == "gemini-3.1-flash-lite"
    assert request["store"] is False
    assert request["stream"] is True
    assert request["system_instruction"] == "You are a helpful assistant."
    assert request["tools"] == tools
    assert request["response_format"] == response_format
    assert "safety_settings" not in request
    assert request["generation_config"] == {
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "max_output_tokens": 1500,
        "thinking_level": "high",
    }


def test_build_interaction_request_thinking_level_gemini_2_5() -> None:
    """Test thinking_level is omitted for Gemini 2.5 models."""
    request = build_interaction_request(
        model="models/gemini-2.5-flash",
        input_content="Hello",
        options={CONF_THINKING_LEVEL: "high"},
    )
    assert "thinking_level" not in request["generation_config"]


def test_build_interaction_request_thinking_level_gemini_3_pro_minimal() -> None:
    """Test minimal thinking_level is omitted for Gemini 3 Pro models."""
    request = build_interaction_request(
        model="models/gemini-3.1-pro-preview",
        input_content="Hello",
        options={CONF_THINKING_LEVEL: "minimal"},
    )
    assert "thinking_level" not in request["generation_config"]


def test_build_interaction_request_thinking_level_gemini_3_pro_supported() -> None:
    """Test supported thinking_levels are included for Gemini 3 Pro models."""
    request = build_interaction_request(
        model="models/gemini-3.1-pro-preview",
        input_content="Hello",
        options={CONF_THINKING_LEVEL: "low"},
    )
    assert request["generation_config"]["thinking_level"] == "low"


def test_build_interaction_request_thinking_level_gemini_3_flash_minimal() -> None:
    """Test minimal thinking_level is included for non-Pro Gemini 3 models."""
    request = build_interaction_request(
        model="models/gemini-3.1-flash-lite",
        input_content="Hello",
        options={CONF_THINKING_LEVEL: "minimal"},
    )
    assert request["generation_config"]["thinking_level"] == "minimal"


async def test_transform_interactions_stream_text() -> None:
    """Test streaming text events from Interactions API."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.ModelOutputStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.TextDelta(text="Hello, "),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.TextDelta(text="world!"),
            metadata=interactions.StepDeltaMetadata(
                total_usage=interactions.Usage(
                    total_input_tokens=10,
                    total_cached_tokens=0,
                    total_output_tokens=5,
                )
            ),
        )
        yield interactions.StepStop(index=0)
        yield interactions.InteractionCompletedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="int_1",
                status="completed",
                created="",
                model="gemini-2.5-flash",
                object="interaction",
                updated="",
            ),
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
        yield interactions.StepStart(
            index=0,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSummaryDelta(
                content=interactions.TextContent(text="Thinking deeply..."),
            ),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSignatureDelta(
                signature="dGVzdF9zaWdfMTIz",
            ),
        )
        yield interactions.StepStop(index=0)
        yield interactions.StepStart(
            index=1,
            step=interactions.ModelOutputStep(),
        )
        yield interactions.StepDelta(
            index=1,
            delta=interactions.TextDelta(text="Result."),
        )
        yield interactions.StepStop(index=1)

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
                    index=0,
                    length=18,
                    thought_signature="dGVzdF9zaWdfMTIz",
                )
            ]
        )
    }


async def test_transform_interactions_stream_thought_summary_nested_content() -> None:
    """Test streaming thought summary with nested content text."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSummaryDelta(
                content=interactions.TextContent(text="Summarized reasoning"),
            ),
        )
        yield interactions.StepStop(index=0)

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
        yield interactions.StepStart(
            index=0,
            step=interactions.FunctionCallStep(
                id="call_123",
                name="turn_on",
                arguments={},
            ),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ArgumentsDelta(
                arguments='{"entity_id": ',
            ),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ArgumentsDelta(
                arguments='"light.living_room"}',
            ),
        )
        yield interactions.StepStop(index=0)

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


async def test_transform_interactions_stream_prepopulated_tool_calls() -> None:
    """Test tool calls with pre-populated arguments from Interactions API."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.FunctionCallStep(
                id="call_456",
                name="turn_off",
                arguments={"entity_id": "switch.ac"},
            ),
        )
        yield interactions.StepStop(index=0)

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
        yield interactions.ErrorEvent(
            error=interactions.Error(message="Resource exhausted"),
        )

    with pytest.raises(HomeAssistantError, match="Resource exhausted"):
        async for _ in transform_interactions_stream(chat_log, mock_events()):
            pass


async def test_transform_interactions_stream_status_update_failed() -> None:
    """Test handling failed interaction.status_update event."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.InteractionStatusUpdate(
            interaction_id="int_123",
            status="failed",
        )

    with pytest.raises(HomeAssistantError, match="Status: failed"):
        async for _ in transform_interactions_stream(chat_log, mock_events()):
            pass


async def test_transform_interactions_stream_failed_interaction() -> None:
    """Test handling failed status in stream."""
    chat_log = MagicMock()

    async def mock_events():
        yield interactions.InteractionCompletedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="int_123",
                status="failed",
                created="",
                model="gemini-2.5-flash",
                object="interaction",
                updated="",
            ),
        )

    with pytest.raises(HomeAssistantError, match="Status: failed"):
        async for _ in transform_interactions_stream(chat_log, mock_events()):
            pass


async def test_transform_interactions_stream_gemini_3_flash_userland_tool(
    hass: HomeAssistant,
) -> None:
    """Test replaying recorded gemini-3.8-flash userland tool stream."""
    chat_log = conversation.ChatLog(hass, "test_conversation")
    chat_log.async_add_user_content(
        conversation.UserContent(content="What is the weather in Paris?")
    )

    thought_sig = "thought_sig_weather_123"

    async def mock_events():
        yield interactions.InteractionCreatedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="",
                status="in_progress",
                model="gemini-3.8-flash",
                object="interaction",
            )
        )
        yield interactions.InteractionStatusUpdate(
            interaction_id="",
            status="in_progress",
        )
        yield interactions.StepStart(
            index=0,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSignatureDelta(signature=thought_sig),
        )
        yield interactions.StepStop(index=0)
        yield interactions.StepStart(
            index=1,
            step=interactions.FunctionCallStep(
                arguments={},
                id="call_647382",
                name="get_weather",
            ),
        )
        yield interactions.StepDelta(
            index=1,
            delta=interactions.ArgumentsDelta(arguments='{"location":"Paris"}'),
        )
        yield interactions.StepStop(index=1)
        yield interactions.InteractionCompletedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="",
                status="requires_action",
                model="gemini-3.8-flash",
                object="interaction",
            )
        )

    chat_log.llm_api = MagicMock()
    chat_log.llm_api.async_call_tool = AsyncMock(
        return_value=llm.ToolResult(data={"temperature": "18°C"})
    )

    contents = [
        c
        async for c in chat_log.async_add_delta_content_stream(
            "test_agent", transform_interactions_stream(chat_log, mock_events())
        )
    ]

    assistant_content = next(
        c for c in contents if isinstance(c, conversation.AssistantContent)
    )
    assert assistant_content.tool_calls == [
        llm.ToolInput(
            tool_name="get_weather",
            tool_args={"location": "Paris"},
            id="call_647382",
        )
    ]
    assert assistant_content.native == ContentDetails(
        part_details=[
            PartDetails(
                part_type="thought",
                index=0,
                length=0,
                thought_signature=thought_sig,
            )
        ]
    )
    assert assistant_content.native.part_details[0].thought_signature == thought_sig


async def test_transform_interactions_stream_gemini_3_flash_google_search(
    hass: HomeAssistant,
) -> None:
    """Test replaying recorded gemini-3.8-flash Google Search stream."""
    chat_log = conversation.ChatLog(hass, "test_conversation")
    chat_log.async_add_user_content(
        conversation.UserContent(content="who won Super Bowl LX 2026?")
    )

    search_sig = "search_sig_superbowl_123"
    thought_sig = "thought_sig_superbowl_456"

    async def mock_events():
        yield interactions.InteractionCreatedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="",
                status="in_progress",
                model="gemini-3.8-flash",
                object="interaction",
            )
        )
        yield interactions.InteractionStatusUpdate(
            interaction_id="",
            status="in_progress",
        )
        yield interactions.StepStart(
            index=0,
            step=interactions.GoogleSearchCallStep(
                arguments=interactions.GoogleSearchCallArguments(queries=None),
                id="call_491782",
                signature="",
            ),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.GoogleSearchCallDelta(
                arguments=interactions.GoogleSearchCallArguments(
                    queries=[
                        "Super Bowl LX 2026 winner",
                        "Super Bowl LX date location",
                    ]
                ),
                signature=search_sig,
            ),
        )
        yield interactions.StepStop(index=0)
        yield interactions.StepStart(
            index=1,
            step=interactions.GoogleSearchResultStep(
                call_id="call_491782",
                result=[],
                signature="",
            ),
        )
        yield interactions.StepDelta(
            index=1,
            delta=interactions.GoogleSearchResultDelta(
                result=[interactions.GoogleSearchResult(search_suggestions="...")],
                signature="res_sig_abc",
            ),
        )
        yield interactions.StepStop(index=1)
        yield interactions.StepStart(
            index=2,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=2,
            delta=interactions.ThoughtSignatureDelta(signature=thought_sig),
        )
        yield interactions.StepStop(index=2)
        yield interactions.StepStart(
            index=3,
            step=interactions.ModelOutputStep(),
        )
        yield interactions.StepDelta(
            index=3,
            delta=interactions.TextDelta(
                text="The **Seattle Seahawks** won Super Bowl LX on February 8, 2026."
            ),
        )
        yield interactions.StepStop(index=3)
        yield interactions.InteractionCompletedEvent(
            interaction=interactions.InteractionSseEventInteraction(
                id="",
                status="completed",
                model="gemini-3.8-flash",
                object="interaction",
            )
        )

    contents = [
        c
        async for c in chat_log.async_add_delta_content_stream(
            "test_agent", transform_interactions_stream(chat_log, mock_events())
        )
    ]

    assistant_content = next(
        c for c in contents if isinstance(c, conversation.AssistantContent)
    )
    assert (
        assistant_content.content
        == "The **Seattle Seahawks** won Super Bowl LX on February 8, 2026."
    )
    assert assistant_content.tool_calls == [
        llm.ToolInput(
            tool_name="google_search",
            tool_args={
                "queries": [
                    "Super Bowl LX 2026 winner",
                    "Super Bowl LX date location",
                ]
            },
            id="call_491782",
            external=True,
        )
    ]
    assert assistant_content.native == ContentDetails(
        part_details=[
            PartDetails(
                part_type="google_search_call",
                index=0,
                length=0,
                thought_signature=search_sig,
            ),
            PartDetails(
                part_type="thought",
                index=0,
                length=0,
                thought_signature=thought_sig,
            ),
        ]
    )
    assert assistant_content.native.part_details[0].thought_signature == search_sig
    assert assistant_content.native.part_details[1].thought_signature == thought_sig


async def test_transform_interactions_stream_multi_search_and_thought(
    hass: HomeAssistant,
) -> None:
    """Test streaming multiple Google Searches and thoughts in a single turn."""
    chat_log = conversation.ChatLog(hass, "test_conversation")

    thought_1 = "First thought."
    thought_2 = "Second thought."
    sig_t1 = "sig_thought_1"
    sig_t2 = "sig_thought_2"
    sig_s1 = "sig_search_1"
    sig_s2 = "sig_search_2"

    async def mock_events():
        # Step 0: Thought 1
        yield interactions.StepStart(
            index=0,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSummaryDelta(
                content=interactions.TextContent(text=thought_1),
            ),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSignatureDelta(signature=sig_t1),
        )
        yield interactions.StepStop(index=0)

        # Step 1: Search 1
        yield interactions.StepStart(
            index=1,
            step=interactions.GoogleSearchCallStep(
                id="search_1",
                arguments=interactions.GoogleSearchCallArguments(queries=None),
            ),
        )
        yield interactions.StepDelta(
            index=1,
            delta=interactions.GoogleSearchCallDelta(
                signature=sig_s1,
                arguments=interactions.GoogleSearchCallArguments(queries=["query 1"]),
            ),
        )
        yield interactions.StepStop(index=1)

        # Step 2: Thought 2
        yield interactions.StepStart(
            index=2,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=2,
            delta=interactions.ThoughtSummaryDelta(
                content=interactions.TextContent(text=thought_2),
            ),
        )
        yield interactions.StepDelta(
            index=2,
            delta=interactions.ThoughtSignatureDelta(signature=sig_t2),
        )
        yield interactions.StepStop(index=2)

        # Step 3: Search 2
        yield interactions.StepStart(
            index=3,
            step=interactions.GoogleSearchCallStep(
                id="search_2",
                arguments=interactions.GoogleSearchCallArguments(queries=None),
            ),
        )
        yield interactions.StepDelta(
            index=3,
            delta=interactions.GoogleSearchCallDelta(
                signature=sig_s2,
                arguments=interactions.GoogleSearchCallArguments(queries=["query 2"]),
            ),
        )
        yield interactions.StepStop(index=3)

        # Step 4: Final text
        yield interactions.StepStart(
            index=4,
            step=interactions.ModelOutputStep(),
        )
        yield interactions.StepDelta(
            index=4,
            delta=interactions.TextDelta(text="Final answer."),
        )
        yield interactions.StepStop(index=4)

    contents = [
        c
        async for c in chat_log.async_add_delta_content_stream(
            "test_agent", transform_interactions_stream(chat_log, mock_events())
        )
    ]

    assistant_content = next(
        c for c in contents if isinstance(c, conversation.AssistantContent)
    )
    assert isinstance(assistant_content, conversation.AssistantContent)
    assert assistant_content.content == "Final answer."
    assert assistant_content.thinking_content == f"{thought_1}{thought_2}"
    assert len(assistant_content.tool_calls or []) == 2
    assert assistant_content.tool_calls[0].tool_args == {"queries": ["query 1"]}
    assert assistant_content.tool_calls[1].tool_args == {"queries": ["query 2"]}

    assert assistant_content.native == ContentDetails(
        part_details=[
            PartDetails(
                part_type="thought",
                index=0,
                length=len(thought_1),
                thought_signature=sig_t1,
            ),
            PartDetails(
                part_type="google_search_call",
                index=0,
                length=0,
                thought_signature=sig_s1,
            ),
            PartDetails(
                part_type="thought",
                index=len(thought_1),
                length=len(thought_2),
                thought_signature=sig_t2,
            ),
            PartDetails(
                part_type="google_search_call",
                index=1,
                length=0,
                thought_signature=sig_s2,
            ),
        ]
    )


async def test_convert_chat_log_to_interactions_steps_simple(
    hass: HomeAssistant,
) -> None:
    """Test converting basic user and assistant conversation history to steps."""
    chat_log = conversation.ChatLog(hass, "test_conversation")
    chat_log.async_add_user_content(conversation.UserContent(content="Hello"))
    chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(
            agent_id="test_agent",
            content="Hello there!",
        )
    )
    chat_log.async_add_user_content(conversation.UserContent(content="How are you?"))

    steps = convert_chat_log_to_interactions_steps(chat_log)

    assert len(steps) == 3
    assert steps[0] == interactions.UserInputStep(
        content=[interactions.TextContent(text="Hello")]
    )
    assert steps[1] == interactions.ModelOutputStep(
        content=[interactions.TextContent(text="Hello there!")]
    )
    assert steps[2] == interactions.UserInputStep(
        content=[interactions.TextContent(text="How are you?")]
    )


async def test_convert_chat_log_to_interactions_steps_google_search_multiturn(
    hass: HomeAssistant,
) -> None:
    """Test converting Google Search conversation turn to steps for multi-turn follow-up."""
    chat_log = conversation.ChatLog(hass, "test_conversation")
    chat_log.async_add_user_content(
        conversation.UserContent(content="who won Super Bowl LX 2026?")
    )

    search_sig = "search_sig_super_bowl_123"
    thought_sig = "thought_sig_super_bowl_456"

    chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(
            agent_id="test_agent",
            content="The **Seattle Seahawks** won Super Bowl LX on February 8, 2026.",
            tool_calls=[
                llm.ToolInput(
                    tool_name="google_search",
                    tool_args={
                        "queries": [
                            "Super Bowl LX 2026 winner",
                            "Super Bowl LX date location",
                        ]
                    },
                    id="call_491782",
                    external=True,
                )
            ],
            native=ContentDetails(
                part_details=[
                    PartDetails(
                        part_type="google_search_call",
                        index=0,
                        length=0,
                        thought_signature=search_sig,
                    ),
                    PartDetails(
                        part_type="thought",
                        index=0,
                        length=0,
                        thought_signature=thought_sig,
                    ),
                ]
            ),
        )
    )

    chat_log.async_add_user_content(
        conversation.UserContent(content="what is the score")
    )

    steps = convert_chat_log_to_interactions_steps(chat_log)

    assert len(steps) == 5
    assert steps[0] == interactions.UserInputStep(
        content=[interactions.TextContent(text="who won Super Bowl LX 2026?")]
    )
    assert steps[1] == interactions.GoogleSearchCallStep(
        arguments=interactions.GoogleSearchCallArguments(
            queries=[
                "Super Bowl LX 2026 winner",
                "Super Bowl LX date location",
            ]
        ),
        id="call_491782",
        signature=search_sig,
        search_type="web_search",
    )
    assert steps[2] == interactions.ThoughtStep(
        signature=thought_sig,
    )
    assert steps[3] == interactions.ModelOutputStep(
        content=[
            interactions.TextContent(
                text="The **Seattle Seahawks** won Super Bowl LX on February 8, 2026."
            )
        ]
    )
    assert steps[4] == interactions.UserInputStep(
        content=[interactions.TextContent(text="what is the score")]
    )

    request = build_interaction_request(
        model="gemini-3.8-flash",
        input_content=steps,
        stream=True,
        store=False,
    )
    assert request["input"] == steps
    assert request["model"] == "gemini-3.8-flash"
    assert request["store"] is False
    assert request["stream"] is True


async def test_convert_chat_log_to_interactions_steps_userland_tool_multiturn(
    hass: HomeAssistant,
) -> None:
    """Test converting userland tool call and result to steps."""
    chat_log = conversation.ChatLog(hass, "test_conversation")
    chat_log.async_add_user_content(
        conversation.UserContent(content="What is the weather in Paris?")
    )

    thought_sig_1 = "sig_weather_call_1"
    thought_sig_2 = "sig_weather_output_2"

    async def mock_tool_call_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSignatureDelta(signature=thought_sig_1),
        )
        yield interactions.StepStop(index=0)
        yield interactions.StepStart(
            index=1,
            step=interactions.FunctionCallStep(
                arguments={},
                id="call_647382",
                name="get_weather",
            ),
        )
        yield interactions.StepDelta(
            index=1,
            delta=interactions.ArgumentsDelta(arguments='{"location":"Paris"}'),
        )
        yield interactions.StepStop(index=1)

    chat_log.llm_api = MagicMock()
    chat_log.llm_api.async_call_tool = AsyncMock(
        return_value=llm.ToolResult(data={"temperature": "18°C", "condition": "Sunny"})
    )

    async for _ in chat_log.async_add_delta_content_stream(
        "test_agent", transform_interactions_stream(chat_log, mock_tool_call_events())
    ):
        pass

    async def mock_response_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.ThoughtStep(),
        )
        yield interactions.StepDelta(
            index=0,
            delta=interactions.ThoughtSignatureDelta(signature=thought_sig_2),
        )
        yield interactions.StepStop(index=0)
        yield interactions.StepStart(
            index=1,
            step=interactions.ModelOutputStep(),
        )
        yield interactions.StepDelta(
            index=1,
            delta=interactions.TextDelta(
                text="The weather in Paris is sunny and 18°C."
            ),
        )
        yield interactions.StepStop(index=1)

    async for _ in chat_log.async_add_delta_content_stream(
        "test_agent", transform_interactions_stream(chat_log, mock_response_events())
    ):
        pass

    chat_log.async_add_user_content(
        conversation.UserContent(content="What should I wear there?")
    )

    steps = convert_chat_log_to_interactions_steps(chat_log)

    assert len(steps) == 7
    assert steps[0] == interactions.UserInputStep(
        content=[interactions.TextContent(text="What is the weather in Paris?")]
    )
    assert steps[1] == interactions.ThoughtStep(signature=thought_sig_1)
    assert steps[2] == interactions.FunctionCallStep(
        arguments={"location": "Paris"},
        id="call_647382",
        name="get_weather",
    )
    assert steps[3] == interactions.FunctionResultStep(
        call_id="call_647382",
        name="get_weather",
        result={"temperature": "18°C", "condition": "Sunny"},
    )
    assert steps[4] == interactions.ThoughtStep(signature=thought_sig_2)
    assert steps[5] == interactions.ModelOutputStep(
        content=[
            interactions.TextContent(text="The weather in Paris is sunny and 18°C.")
        ]
    )
    assert steps[6] == interactions.UserInputStep(
        content=[interactions.TextContent(text="What should I wear there?")]
    )


async def test_convert_chat_log_to_interactions_steps_tool_error(
    hass: HomeAssistant,
) -> None:
    """Test converting tool error result to FunctionResultStep with is_error flag."""
    chat_log = conversation.ChatLog(hass, "test_conversation")
    chat_log.async_add_user_content(
        conversation.UserContent(content="Turn on the living room light")
    )

    async def mock_tool_call_events():
        yield interactions.StepStart(
            index=0,
            step=interactions.FunctionCallStep(
                arguments={"entity_id": "light.living_room"},
                id="call_999",
                name="turn_on",
            ),
        )
        yield interactions.StepStop(index=0)

    chat_log.llm_api = MagicMock()
    chat_log.llm_api.async_call_tool = AsyncMock(
        return_value=llm.ToolResult(data={"error": "Device unreachable"}, error=True)
    )

    async for _ in chat_log.async_add_delta_content_stream(
        "test_agent", transform_interactions_stream(chat_log, mock_tool_call_events())
    ):
        pass

    steps = convert_chat_log_to_interactions_steps(chat_log)

    assert len(steps) == 3
    assert steps[0] == interactions.UserInputStep(
        content=[interactions.TextContent(text="Turn on the living room light")]
    )
    assert steps[1] == interactions.FunctionCallStep(
        arguments={"entity_id": "light.living_room"},
        id="call_999",
        name="turn_on",
    )
    assert steps[2] == interactions.FunctionResultStep(
        call_id="call_999",
        name="turn_on",
        result={"error": "Device unreachable"},
        is_error=True,
    )


async def test_convert_chat_log_to_interactions_steps_thought_with_signature(
    hass: HomeAssistant,
) -> None:
    """Test converting thinking_content with thought signature to ThoughtStep."""
    chat_log = conversation.ChatLog(hass, "test_conversation")
    chat_log.async_add_user_content(conversation.UserContent(content="What is 2+2?"))

    thought_sig = "thought_sig_calc_123"

    chat_log.async_add_assistant_content_without_tools(
        conversation.AssistantContent(
            agent_id="test_agent",
            thinking_content="Calculating 2+2=4.",
            content="2 + 2 = 4.",
            native=ContentDetails(
                part_details=[
                    PartDetails(
                        part_type="thought",
                        index=0,
                        length=17,
                        thought_signature=thought_sig,
                    )
                ]
            ),
        )
    )

    chat_log.async_add_user_content(
        conversation.UserContent(content="And what is 4+4?")
    )

    steps = convert_chat_log_to_interactions_steps(chat_log)

    assert len(steps) == 4
    assert steps[0] == interactions.UserInputStep(
        content=[interactions.TextContent(text="What is 2+2?")]
    )
    assert steps[1] == interactions.ThoughtStep(
        signature=thought_sig,
        summary=[interactions.TextContent(text="Calculating 2+2=4.")],
    )
    assert steps[1].signature == thought_sig
    assert steps[2] == interactions.ModelOutputStep(
        content=[interactions.TextContent(text="2 + 2 = 4.")]
    )
    assert steps[3] == interactions.UserInputStep(
        content=[interactions.TextContent(text="And what is 4+4?")]
    )
