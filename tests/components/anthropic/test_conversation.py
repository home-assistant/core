"""Tests for the Anthropic integration."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from anthropic import RateLimitError
from anthropic.types import (
    CitationsDelta,
    InputJSONDelta,
    Message,
    MessageDeltaUsage,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStartEvent,
    RawMessageStopEvent,
    RawMessageStreamEvent,
    RedactedThinkingBlock,
    ServerToolUseBlock,
    SignatureDelta,
    TextBlock,
    TextDelta,
    ThinkingBlock,
    ThinkingDelta,
    ToolUseBlock,
    Usage,
    WebSearchResultBlock,
    WebSearchToolResultBlock,
)
from anthropic.types.raw_message_delta_event import Delta
from freezegun import freeze_time
from httpx import URL, Request, Response
import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.anthropic.const import (
    CONF_CHAT_MODEL,
    CONF_WEB_SEARCH,
    CONF_WEB_SEARCH_MAX_USES,
)
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session, intent, llm
from homeassistant.setup import async_setup_component
from homeassistant.util import ulid as ulid_util

from tests.common import MockConfigEntry


async def stream_generator(
    responses: list[RawMessageStreamEvent],
) -> AsyncGenerator[RawMessageStreamEvent]:
    """Generate a response from the assistant."""
    for msg in responses:
        yield msg


def create_messages(
    content_blocks: list[RawMessageStreamEvent], stop_reason="end_turn"
) -> list[RawMessageStreamEvent]:
    """Create a stream of messages with the specified content blocks."""
    return [
        RawMessageStartEvent(
            message=Message(
                type="message",
                id="msg_1234567890ABCDEFGHIJKLMN",
                content=[],
                role="assistant",
                model="claude-3-5-sonnet-20240620",
                usage=Usage(input_tokens=0, output_tokens=0),
            ),
            type="message_start",
        ),
        *content_blocks,
        RawMessageDeltaEvent(
            type="message_delta",
            delta=Delta(stop_reason=stop_reason, stop_sequence=""),
            usage=MessageDeltaUsage(output_tokens=0),
        ),
        RawMessageStopEvent(type="message_stop"),
    ]


def create_content_block(
    index: int, text_parts: list[str]
) -> list[RawMessageStreamEvent]:
    """Create a text content block with the specified deltas."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=TextBlock(text="", type="text"),
            index=index,
        ),
        *[
            RawContentBlockDeltaEvent(
                delta=TextDelta(text=text_part, type="text_delta"),
                index=index,
                type="content_block_delta",
            )
            for text_part in text_parts
        ],
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_thinking_block(
    index: int, thinking_parts: list[str]
) -> list[RawMessageStreamEvent]:
    """Create a thinking block with the specified deltas."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=ThinkingBlock(signature="", thinking="", type="thinking"),
            index=index,
        ),
        *[
            RawContentBlockDeltaEvent(
                delta=ThinkingDelta(thinking=thinking_part, type="thinking_delta"),
                index=index,
                type="content_block_delta",
            )
            for thinking_part in thinking_parts
        ],
        RawContentBlockDeltaEvent(
            delta=SignatureDelta(
                signature="ErUBCkYIARgCIkCYXaVNJShe3A86Hp7XUzh9YsCYBbJTbQsrklTAPtJ2sP/N"
                "oB6tSzpK/nTL6CjSo2R6n0KNBIg5MH6asM2R/kmaEgyB/X1FtZq5OQAC7jUaDEPWCdcwGQ"
                "4RaBy5wiIwmRxExIlDhoY6tILoVPnOExkC/0igZxHEwxK8RU/fmw0b+o+TwAarzUitwzbo"
                "21E5Kh3pa3I6yqVROf1t2F8rFocNUeCegsWV/ytwYV+ayA==",
                type="signature_delta",
            ),
            index=index,
            type="content_block_delta",
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_redacted_thinking_block(index: int) -> list[RawMessageStreamEvent]:
    """Create a redacted thinking block."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=RedactedThinkingBlock(
                data="EroBCkYIARgCKkBJDytPJhw//4vy3t7aE+LfIkxvkAh51cBPrAvBCo6AjgI57Zt9K"
                "WPnUVV50OQJ0KZzUFoGZG5sxg95zx4qMwkoEgz43Su3myJKckvj03waDBZLIBSeoAeRUeV"
                "sJCIwQ5edQN0sa+HNeB/KUBkoMUwV+IT0eIhcpFxnILdvxUAKM4R1o4KG3x+yO0eo/kyOK"
                "iKfrCPFQhvBVmTZPFhgA2Ow8L9gGDVipcz6x3Uu9YETGEny",
                type="redacted_thinking",
            ),
            index=index,
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_tool_use_block(
    index: int, tool_id: str, tool_name: str, json_parts: list[str]
) -> list[RawMessageStreamEvent]:
    """Create a tool use content block with the specified deltas."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=ToolUseBlock(
                id=tool_id, name=tool_name, input={}, type="tool_use"
            ),
            index=index,
        ),
        *[
            RawContentBlockDeltaEvent(
                delta=InputJSONDelta(partial_json=json_part, type="input_json_delta"),
                index=index,
                type="content_block_delta",
            )
            for json_part in json_parts
        ],
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_server_tool_use_block(
    index: int, tool_id: str, tool_name: str, json_parts: list[str]
) -> list[RawMessageStreamEvent]:
    """Create a server tool use content block (e.g., web search) with the specified deltas."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=ServerToolUseBlock(
                id=tool_id, name=tool_name, input={}, type="server_tool_use"
            ),
            index=index,
        ),
        *[
            RawContentBlockDeltaEvent(
                delta=InputJSONDelta(partial_json=json_part, type="input_json_delta"),
                index=index,
                type="content_block_delta",
            )
            for json_part in json_parts
        ],
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_web_search_result_block(
    index: int, tool_use_id: str, results: list[dict[str, Any]]
) -> list[RawMessageStreamEvent]:
    """Create a web search result content block."""
    return [
        RawContentBlockStartEvent(
            type="content_block_start",
            content_block=WebSearchToolResultBlock(
                type="web_search_tool_result",
                tool_use_id=tool_use_id,
                content=[
                    WebSearchResultBlock(
                        type="web_search_result",
                        **result,
                    )
                    for result in results
                ],
            ),
            index=index,
        ),
        RawContentBlockStopEvent(index=index, type="content_block_stop"),
    ]


def create_citations_delta(
    index: int, citations: list[dict[str, Any]]
) -> list[RawMessageStreamEvent]:
    """Create a citations delta event."""
    return [
        RawContentBlockDeltaEvent(
            delta=CitationsDelta(
                type="citations_delta",
                citations=citations,
            ),
            index=index,
            type="content_block_delta",
        ),
    ]


async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test entity properties."""
    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert state.attributes["supported_features"] == 0

    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_LLM_HASS_API: "assist",
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    state = hass.states.get("conversation.claude_conversation")
    assert state
    assert (
        state.attributes["supported_features"]
        == conversation.ConversationEntityFeature.CONTROL
    )


async def test_error_handling(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_init_component
) -> None:
    """Test that the default prompt works."""
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        side_effect=RateLimitError(
            message=None,
            response=Response(
                status_code=429, request=Request(method="POST", url=URL())
            ),
            body=None,
        ),
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == "unknown", result


async def test_template_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that template error handling works."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            "prompt": "talk like a {% if True %}smarthome{% else %}pirate please.",
        },
    )
    with (
        patch("anthropic.resources.models.AsyncModels.retrieve"),
        patch(
            "anthropic.resources.messages.AsyncMessages.create", new_callable=AsyncMock
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == "unknown", result


async def test_template_variables(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that template variables work."""
    context = Context(user_id="12345")
    mock_user = Mock()
    mock_user.id = "12345"
    mock_user.name = "Test User"

    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            "prompt": (
                "The user name is {{ user_name }}. "
                "The user id is {{ llm_context.context.user_id }}."
            ),
        },
    )
    with (
        patch("anthropic.resources.models.AsyncModels.retrieve"),
        patch(
            "anthropic.resources.messages.AsyncMessages.create", new_callable=AsyncMock
        ) as mock_create,
        patch("homeassistant.auth.AuthManager.async_get_user", return_value=mock_user),
    ):
        mock_create.return_value = stream_generator(
            create_messages(
                create_content_block(
                    0, ["Okay, let", " me take care of that for you", "."]
                )
            )
        )
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, context, agent_id="conversation.claude_conversation"
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"]
        == "Okay, let me take care of that for you."
    )
    assert "The user name is Test User." in mock_create.call_args.kwargs["system"]
    assert "The user id is 12345." in mock_create.call_args.kwargs["system"]


async def test_conversation_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test Anthropic Agent."""
    agent = conversation.agent_manager.async_get_agent(
        hass, "conversation.claude_conversation"
    )
    assert agent.supported_languages == "*"


@patch("homeassistant.components.anthropic.entity.llm.AssistAPI._async_get_tools")
@pytest.mark.parametrize(
    ("tool_call_json_parts", "expected_call_tool_args"),
    [
        (
            ['{"param1": "test_value"}'],
            {"param1": "test_value"},
        ),
        (
            ['{"para', 'm1": "test_valu', 'e"}'],
            {"param1": "test_value"},
        ),
        ([""], {}),
    ],
)
async def test_function_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    tool_call_json_parts: list[str],
    expected_call_tool_args: dict[str, Any],
) -> None:
    """Test function call from the assistant."""
    agent_id = "conversation.claude_conversation"
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.return_value = "Test response"

    mock_get_tools.return_value = [mock_tool]

    def completion_result(*args, messages, **kwargs):
        for message in messages:
            for content in message["content"]:
                if not isinstance(content, str) and content["type"] == "tool_use":
                    return stream_generator(
                        create_messages(
                            create_content_block(
                                0, ["I have ", "successfully called ", "the function"]
                            ),
                        )
                    )

        return stream_generator(
            create_messages(
                [
                    *create_content_block(0, ["Certainly, calling it now!"]),
                    *create_tool_use_block(
                        1,
                        "toolu_0123456789AbCdEfGhIjKlM",
                        "test_tool",
                        tool_call_json_parts,
                    ),
                ],
                stop_reason="tool_use",
            )
        )

    with (
        patch(
            "anthropic.resources.messages.AsyncMessages.create",
            new_callable=AsyncMock,
            side_effect=completion_result,
        ) as mock_create,
        freeze_time("2024-06-03 23:00:00"),
    ):
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
        )

    assert "Today's date is 2024-06-03." in mock_create.mock_calls[1][2]["system"]

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"]
        == "I have successfully called the function"
    )
    assert mock_create.mock_calls[1][2]["messages"][2] == {
        "role": "user",
        "content": [
            {
                "content": '"Test response"',
                "tool_use_id": "toolu_0123456789AbCdEfGhIjKlM",
                "type": "tool_result",
            }
        ],
    }
    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            id="toolu_0123456789AbCdEfGhIjKlM",
            tool_name="test_tool",
            tool_args=expected_call_tool_args,
        ),
        llm.LLMContext(
            platform="anthropic",
            context=context,
            language="en",
            assistant="conversation",
            device_id=None,
        ),
    )


@patch("homeassistant.components.anthropic.entity.llm.AssistAPI._async_get_tools")
async def test_function_exception(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test function call with exception."""
    agent_id = "conversation.claude_conversation"
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.side_effect = HomeAssistantError("Test tool exception")

    mock_get_tools.return_value = [mock_tool]

    def completion_result(*args, messages, **kwargs):
        for message in messages:
            for content in message["content"]:
                if not isinstance(content, str) and content["type"] == "tool_use":
                    return stream_generator(
                        create_messages(
                            create_content_block(
                                0,
                                ["There was an error calling the function"],
                            )
                        )
                    )

        return stream_generator(
            create_messages(
                [
                    *create_content_block(0, ["Certainly, calling it now!"]),
                    *create_tool_use_block(
                        1,
                        "toolu_0123456789AbCdEfGhIjKlM",
                        "test_tool",
                        ['{"param1": "test_value"}'],
                    ),
                ],
                stop_reason="tool_use",
            )
        )

    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        side_effect=completion_result,
    ) as mock_create:
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert (
        result.response.speech["plain"]["speech"]
        == "There was an error calling the function"
    )
    assert mock_create.mock_calls[1][2]["messages"][2] == {
        "role": "user",
        "content": [
            {
                "content": '{"error": "HomeAssistantError", "error_text": "Test tool exception"}',
                "tool_use_id": "toolu_0123456789AbCdEfGhIjKlM",
                "type": "tool_result",
            }
        ],
    }
    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            id="toolu_0123456789AbCdEfGhIjKlM",
            tool_name="test_tool",
            tool_args={"param1": "test_value"},
        ),
        llm.LLMContext(
            platform="anthropic",
            context=context,
            language="en",
            assistant="conversation",
            device_id=None,
        ),
    )


async def test_assist_api_tools_conversion(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test that we are able to convert actual tools from Assist API."""
    for component in (
        "intent",
        "todo",
        "light",
        "shopping_list",
        "humidifier",
        "climate",
        "media_player",
        "vacuum",
        "cover",
        "weather",
    ):
        assert await async_setup_component(hass, component, {})

    agent_id = "conversation.claude_conversation"
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                create_content_block(0, ["Hello, how can I help you?"]),
            ),
        ),
    ) as mock_create:
        await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=agent_id
        )

    tools = mock_create.mock_calls[0][2]["tools"]
    assert tools


async def test_unknown_hass_api(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    mock_init_component,
) -> None:
    """Test when we reference an API that no longer exists."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            **subentry.data,
            CONF_LLM_HASS_API: "non-existing",
        },
    )
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "hello", "1234", Context(), agent_id="conversation.claude_conversation"
    )

    assert result == snapshot


async def test_conversation_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test conversation ID is honored."""

    def create_stream_generator(*args, **kwargs) -> Any:
        return stream_generator(
            create_messages(
                create_content_block(0, ["Hello, how can I help you?"]),
            ),
        )

    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        side_effect=create_stream_generator,
    ):
        result = await conversation.async_converse(
            hass,
            "hello",
            "1234",
            Context(),
            agent_id="conversation.claude_conversation",
        )

        result = await conversation.async_converse(
            hass, "hello", None, None, agent_id="conversation.claude_conversation"
        )

        conversation_id = result.conversation_id

        result = await conversation.async_converse(
            hass,
            "hello",
            conversation_id,
            None,
            agent_id="conversation.claude_conversation",
        )

        assert result.conversation_id == conversation_id

        unknown_id = ulid_util.ulid()

        result = await conversation.async_converse(
            hass, "hello", unknown_id, None, agent_id="conversation.claude_conversation"
        )

        assert result.conversation_id != unknown_id

        result = await conversation.async_converse(
            hass, "hello", "koala", None, agent_id="conversation.claude_conversation"
        )

        assert result.conversation_id == "koala"


async def test_refusal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test refusal due to potential policy violation."""
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                [
                    *create_content_block(
                        0,
                        ["Certainly! To take over the world you need just a simple "],
                    ),
                ],
                stop_reason="refusal",
            ),
        ),
    ):
        result = await conversation.async_converse(
            hass,
            "ANTHROPIC_MAGIC_STRING_TRIGGER_REFUSAL_1FAEFB6177B4672DEE07F9D3AFC62588CCD"
            "2631EDCF22E8CCC1FB35B501C9C86",
            None,
            Context(),
            agent_id="conversation.claude_conversation",
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR
    assert result.response.error_code == "unknown"
    assert (
        result.response.speech["plain"]["speech"]
        == "Potential policy violation detected"
    )


async def test_extended_thinking(
    hass: HomeAssistant,
    mock_config_entry_with_extended_thinking: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test extended thinking support."""
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                [
                    *create_thinking_block(
                        0,
                        [
                            "The user has just",
                            ' greeted me with "Hi".',
                            " This is a simple greeting an",
                            "d doesn't require any Home Assistant function",
                            " calls. I should respond with",
                            " a friendly greeting and let them know I'm available",
                            " to help with their smart home.",
                        ],
                    ),
                    *create_content_block(1, ["Hello, how can I help you today?"]),
                ]
            ),
        ),
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
        )

    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(
        result.conversation_id
    )
    assert len(chat_log.content) == 3
    assert chat_log.content[1].content == "hello"
    assert chat_log.content[2].content == "Hello, how can I help you today?"


async def test_redacted_thinking(
    hass: HomeAssistant,
    mock_config_entry_with_extended_thinking: MockConfigEntry,
    mock_init_component,
    snapshot: SnapshotAssertion,
) -> None:
    """Test extended thinking with redacted thinking blocks."""
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                [
                    *create_redacted_thinking_block(0),
                    *create_redacted_thinking_block(1),
                    *create_redacted_thinking_block(2),
                    *create_content_block(3, ["How can I help you today?"]),
                ]
            ),
        ),
    ):
        result = await conversation.async_converse(
            hass,
            "ANTHROPIC_MAGIC_STRING_TRIGGER_REDACTED_THINKING_46C9A13E193C177646C7398A9"
            "8432ECCCE4C1253D5E2D82641AC0E52CC2876CB",
            None,
            Context(),
            agent_id="conversation.claude_conversation",
        )

    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(
        result.conversation_id
    )
    # Don't test the prompt because it's not deterministic
    assert chat_log.content[1:] == snapshot


@patch("homeassistant.components.anthropic.entity.llm.AssistAPI._async_get_tools")
async def test_extended_thinking_tool_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_extended_thinking: MockConfigEntry,
    mock_init_component,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that thinking blocks and their order are preserved in with tool calls."""
    agent_id = "conversation.claude_conversation"
    context = Context()

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.return_value = "Test response"

    mock_get_tools.return_value = [mock_tool]

    def completion_result(*args, messages, **kwargs):
        for message in messages:
            for content in message["content"]:
                if not isinstance(content, str) and content["type"] == "tool_use":
                    return stream_generator(
                        create_messages(
                            create_content_block(
                                0, ["I have ", "successfully called ", "the function"]
                            ),
                        )
                    )

        return stream_generator(
            create_messages(
                [
                    *create_thinking_block(
                        0,
                        [
                            "The user asked me to",
                            " call a test function.",
                            "Is it a test? What",
                            " would the function",
                            " do? Would it violate",
                            " any privacy or security",
                            " policies?",
                        ],
                    ),
                    *create_redacted_thinking_block(1),
                    *create_thinking_block(
                        2, ["Okay, let's give it a shot.", " Will I pass the test?"]
                    ),
                    *create_content_block(3, ["Certainly, calling it now!"]),
                    *create_tool_use_block(
                        1,
                        "toolu_0123456789AbCdEfGhIjKlM",
                        "test_tool",
                        ['{"para', 'm1": "test_valu', 'e"}'],
                    ),
                ],
                stop_reason="tool_use",
            )
        )

    with (
        patch(
            "anthropic.resources.messages.AsyncMessages.create",
            new_callable=AsyncMock,
            side_effect=completion_result,
        ) as mock_create,
        freeze_time("2024-06-03 23:00:00"),
    ):
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
        )

    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(
        result.conversation_id
    )

    assert chat_log.content == snapshot
    assert mock_create.mock_calls[1][2]["messages"] == snapshot


@pytest.mark.parametrize(
    "content",
    [
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
        ],
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
            conversation.chat_log.UserContent("What shape is a donut?"),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="A donut is a torus.",
            ),
        ],
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
            conversation.chat_log.UserContent("What shape is a donut?"),
            conversation.chat_log.UserContent("Can you tell me?"),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="A donut is a torus.",
            ),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation", content="Hope this helps."
            ),
        ],
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
            conversation.chat_log.UserContent("What shape is a donut?"),
            conversation.chat_log.UserContent("Can you tell me?"),
            conversation.chat_log.UserContent("Please?"),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="A donut is a torus.",
            ),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation", content="Hope this helps."
            ),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation", content="You are welcome."
            ),
        ],
        [
            conversation.chat_log.SystemContent("You are a helpful assistant."),
            conversation.chat_log.UserContent("Turn off the lights and make me coffee"),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="Sure.",
                tool_calls=[
                    llm.ToolInput(
                        id="mock-tool-call-id",
                        tool_name="HassTurnOff",
                        tool_args={"domain": "light"},
                    ),
                    llm.ToolInput(
                        id="mock-tool-call-id-2",
                        tool_name="MakeCoffee",
                        tool_args={},
                    ),
                ],
            ),
            conversation.chat_log.UserContent("Thank you"),
            conversation.chat_log.ToolResultContent(
                agent_id="conversation.claude_conversation",
                tool_call_id="mock-tool-call-id",
                tool_name="HassTurnOff",
                tool_result={"success": True, "response": "Lights are off."},
            ),
            conversation.chat_log.ToolResultContent(
                agent_id="conversation.claude_conversation",
                tool_call_id="mock-tool-call-id-2",
                tool_name="MakeCoffee",
                tool_result={"success": False, "response": "Not enough milk."},
            ),
            conversation.chat_log.AssistantContent(
                agent_id="conversation.claude_conversation",
                content="Should I add milk to the shopping list?",
            ),
        ],
    ],
)
async def test_history_conversion(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
    snapshot: SnapshotAssertion,
    content: list[conversation.chat_log.Content],
) -> None:
    """Test conversion of chat_log entries into API parameters."""
    conversation_id = "conversation_id"
    with (
        chat_session.async_get_chat_session(hass, conversation_id) as session,
        conversation.async_get_chat_log(hass, session) as chat_log,
        patch(
            "anthropic.resources.messages.AsyncMessages.create",
            new_callable=AsyncMock,
            return_value=stream_generator(
                create_messages(
                    [
                        *create_content_block(0, ["Yes, I am sure!"]),
                    ]
                ),
            ),
        ) as mock_create,
    ):
        chat_log.content = content

        await conversation.async_converse(
            hass,
            "Are you sure?",
            conversation_id,
            Context(),
            agent_id="conversation.claude_conversation",
        )

        assert mock_create.mock_calls[0][2]["messages"] == snapshot


async def test_web_search_tool_added_when_enabled(
    hass: HomeAssistant,
    mock_config_entry_with_web_search: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test that web search tool is added when enabled with supported model."""
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                create_content_block(0, ["Hello, I can search the web for you!"]),
            ),
        ),
    ) as mock_create:
        await conversation.async_converse(
            hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
        )

    # Check that the web search tool was included
    tools = mock_create.mock_calls[0][2]["tools"]
    web_search_tool = next(
        (tool for tool in tools if tool["name"] == "web_search"), None
    )
    assert web_search_tool is not None
    assert web_search_tool["type"] == "web_search_20250305"
    assert web_search_tool["max_uses"] == 5


async def test_web_search_tool_not_added_when_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test that web search tool is not added when disabled."""
    # Ensure web search is disabled (default behavior)
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_CHAT_MODEL: "claude-3-5-sonnet-latest",
            CONF_WEB_SEARCH: False,
            CONF_WEB_SEARCH_MAX_USES: 5,
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                create_content_block(0, ["Hello, how can I help you?"]),
            ),
        ),
    ) as mock_create:
        await conversation.async_converse(
            hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
        )

    # Check that no web search tool was included
    tools = mock_create.mock_calls[0][2].get("tools")
    if tools:
        web_search_tool = next(
            (tool for tool in tools if tool.get("name") == "web_search"), None
        )
        assert web_search_tool is None


async def test_web_search_tool_not_added_with_unsupported_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test that web search tool is not added with unsupported model."""
    # Set unsupported model with web search enabled
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_CHAT_MODEL: "claude-3-haiku-20240307",  # Unsupported model
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_MAX_USES: 5,
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                create_content_block(0, ["Hello, how can I help you?"]),
            ),
        ),
    ) as mock_create:
        await conversation.async_converse(
            hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
        )

    # Check that no web search tool was included
    tools = mock_create.mock_calls[0][2].get("tools")
    if tools:
        web_search_tool = next(
            (tool for tool in tools if tool.get("name") == "web_search"), None
        )
        assert web_search_tool is None


async def test_web_search_custom_max_uses(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test that web search tool respects custom max_uses setting."""
    # Set custom max_uses value
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_CHAT_MODEL: "claude-3-5-sonnet-latest",
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_MAX_USES: 15,  # Custom value
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                create_content_block(0, ["I can search extensively for you!"]),
            ),
        ),
    ) as mock_create:
        await conversation.async_converse(
            hass, "hello", None, Context(), agent_id="conversation.claude_conversation"
        )

    # Check that the web search tool has the correct max_uses
    tools = mock_create.mock_calls[0][2]["tools"]
    web_search_tool = next(
        (tool for tool in tools if tool["name"] == "web_search"), None
    )
    assert web_search_tool is not None
    assert web_search_tool["max_uses"] == 15


async def test_web_search_tool_marked_as_external(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test that web search tools are marked as external for chat log support."""
    # Enable web search
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_CHAT_MODEL: "claude-3-5-sonnet-latest",
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_MAX_USES: 5,
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                [
                    *create_content_block(0, ["I'll search for that information."]),
                    *create_server_tool_use_block(
                        1,
                        "toolu_web_search_123",
                        "web_search",
                        ['{"query": "test search"}'],
                    ),
                ],
                stop_reason="tool_use",
            )
        ),
    ):
        result = await conversation.async_converse(
            hass,
            "Search for information",
            None,
            Context(),
            agent_id="conversation.claude_conversation",
        )

    # Verify the web search tool call was marked as external
    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(
        result.conversation_id
    )
    assert chat_log is not None

    # Find the assistant content with tool calls
    assistant_content = None
    for content in chat_log.content:
        if isinstance(content, conversation.AssistantContent) and content.tool_calls:
            assistant_content = content
            break

    assert assistant_content is not None
    assert len(assistant_content.tool_calls) == 1

    tool_call = assistant_content.tool_calls[0]
    assert tool_call.tool_name == "web_search"
    assert tool_call.external is True  # This is the key assertion for chat log support


async def test_web_search_chat_log_persistence(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test that external web search tool calls persist across conversation turns."""
    # Enable web search
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_CHAT_MODEL: "claude-3-5-sonnet-latest",
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_MAX_USES: 5,
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    # First conversation turn with web search
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                [
                    *create_content_block(0, ["I found some information for you."]),
                    *create_server_tool_use_block(
                        1,
                        "toolu_web_search_123",
                        "web_search",
                        ['{"query": "weather today"}'],
                    ),
                ],
                stop_reason="tool_use",
            )
        ),
    ):
        result1 = await conversation.async_converse(
            hass,
            "What's the weather today?",
            None,
            Context(),
            agent_id="conversation.claude_conversation",
        )

    conversation_id = result1.conversation_id

    # Second conversation turn - should include the previous web search in context
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                create_content_block(0, ["Based on my previous search, it's sunny."]),
            )
        ),
    ) as mock_create:
        await conversation.async_converse(
            hass,
            "What did you find?",
            conversation_id,
            Context(),
            agent_id="conversation.claude_conversation",
        )

    # Verify that the second call included the web search from the first turn
    messages = mock_create.call_args.kwargs["messages"]

    # Look for the assistant message with tool use from the first turn
    found_web_search = False
    for message in messages:
        if message["role"] == "assistant":
            for content_block in message["content"]:
                if (
                    isinstance(content_block, dict)
                    and content_block.get("type") == "server_tool_use"
                    and content_block.get("name") == "web_search"
                ):
                    found_web_search = True
                    assert content_block["input"]["query"] == "weather today"
                    break

    assert found_web_search, (
        "Web search tool call from previous turn should be included in conversation history"
    )


async def test_web_search_multi_turn_with_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
    snapshot: SnapshotAssertion,
) -> None:
    """Test comprehensive web search behavior across multiple turns using snapshots."""
    # Enable web search
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_CHAT_MODEL: "claude-3-5-sonnet-latest",
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_MAX_USES: 10,
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    # First turn: User asks a question that triggers web search
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                [
                    *create_content_block(
                        0, ["I'll search for current weather information."]
                    ),
                    *create_server_tool_use_block(
                        1,
                        "toolu_web_search_001",
                        "web_search",
                        ['{"query": "current weather forecast today"}'],
                    ),
                ],
                stop_reason="tool_use",
            )
        ),
    ):
        result1 = await conversation.async_converse(
            hass,
            "What's the weather like today?",
            None,
            Context(),
            agent_id="conversation.claude_conversation",
        )

    conversation_id = result1.conversation_id

    # Verify the chat log contains the external tool call
    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(conversation_id)
    assert chat_log is not None

    # Find the assistant content with external tool calls
    external_tool_content = None
    for content in chat_log.content:
        if isinstance(content, conversation.AssistantContent) and content.tool_calls:
            if any(tool_call.external for tool_call in content.tool_calls):
                external_tool_content = content
                break

    assert external_tool_content is not None
    assert len(external_tool_content.tool_calls) == 1
    assert external_tool_content.tool_calls[0].external is True
    assert external_tool_content.tool_calls[0].tool_name == "web_search"

    # Test the chat log content matches expected structure
    # Skip the system message for snapshot comparison
    assert chat_log.content[1:] == snapshot

    # Second turn: Follow up question should include previous search context
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                create_content_block(
                    0, ["Based on my previous search, it looks sunny with 75°F."]
                ),
            )
        ),
    ) as mock_create_2:
        await conversation.async_converse(
            hass,
            "What temperature will it be?",
            conversation_id,
            Context(),
            agent_id="conversation.claude_conversation",
        )

    # Verify the second API call included the external tool from first turn
    messages_sent = mock_create_2.call_args.kwargs["messages"]
    assert messages_sent == snapshot


async def test_server_tool_use_block_streaming(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test ServerToolUseBlock streaming (web search tools)."""
    # Enable web search
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_CHAT_MODEL: "claude-3-5-sonnet-latest",
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_MAX_USES: 5,
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                [
                    *create_content_block(0, ["Let me search for that."]),
                    *create_server_tool_use_block(
                        1,
                        "srvtoolu_web_search_456",
                        "web_search",
                        ['{"query": "test query"}'],
                    ),
                ],
                stop_reason="tool_use",
            )
        ),
    ):
        result = await conversation.async_converse(
            hass,
            "Search for something",
            None,
            Context(),
            agent_id="conversation.claude_conversation",
        )

    # Verify the server tool call was marked as external
    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(
        result.conversation_id
    )
    assert chat_log is not None

    # Find the assistant content with tool calls
    assistant_content = None
    for content in chat_log.content:
        if isinstance(content, conversation.AssistantContent) and content.tool_calls:
            assistant_content = content
            break

    assert assistant_content is not None
    assert len(assistant_content.tool_calls) == 1
    tool_call = assistant_content.tool_calls[0]
    assert tool_call.tool_name == "web_search"
    assert tool_call.external is True
    assert tool_call.tool_args == {"query": "test query"}


async def test_web_search_result_block_streaming(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test that WebSearchToolResultBlock is properly handled in streaming."""
    # Enable web search
    subentry = next(iter(mock_config_entry.subentries.values()))
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={
            CONF_CHAT_MODEL: "claude-3-5-sonnet-latest",
            CONF_WEB_SEARCH: True,
            CONF_WEB_SEARCH_MAX_USES: 5,
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    # First conversation: Web search is performed and results are returned
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                [
                    *create_content_block(0, ["Let me search for that information."]),
                    *create_server_tool_use_block(
                        1,
                        "srvtoolu_web_search_123",
                        "web_search",
                        ['{"query": "current weather"}'],
                    ),
                    *create_web_search_result_block(
                        2,
                        "srvtoolu_web_search_123",
                        [
                            {
                                "url": "https://weather.example.com",
                                "title": "Weather Forecast",
                                "encrypted_content": "encrypted_search_result_data",
                            }
                        ],
                    ),
                    *create_content_block(
                        3, ["Based on my search, the weather is sunny today."]
                    ),
                ],
            )
        ),
    ):
        result = await conversation.async_converse(
            hass,
            "What's the weather?",
            None,
            Context(),
            agent_id="conversation.claude_conversation",
        )

    conversation_id = result.conversation_id

    # Verify the chat log contains both the tool call and the result
    chat_log = hass.data.get(conversation.chat_log.DATA_CHAT_LOGS).get(conversation_id)
    assert chat_log is not None

    # Find the assistant content with web search
    assistant_content = None
    for content in chat_log.content:
        if isinstance(content, conversation.AssistantContent) and content.tool_calls:
            if any(tool_call.external for tool_call in content.tool_calls):
                assistant_content = content
                break

    assert assistant_content is not None
    assert len(assistant_content.tool_calls) == 1
    assert assistant_content.tool_calls[0].external is True
    assert assistant_content.tool_calls[0].id == "srvtoolu_web_search_123"
    assert isinstance(assistant_content.native, WebSearchToolResultBlock)
    assert assistant_content.native.tool_use_id == "srvtoolu_web_search_123"

    # Second conversation: Follow-up question should include the complete web search history
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                create_content_block(0, ["The temperature is 75 degrees Fahrenheit."]),
            )
        ),
    ) as mock_create:
        await conversation.async_converse(
            hass,
            "What's the temperature?",
            conversation_id,
            Context(),
            agent_id="conversation.claude_conversation",
        )

    # Verify that the second call properly reconstructed the web search with both blocks
    messages = mock_create.call_args.kwargs["messages"]

    # Find the assistant message with web search from the first turn
    found_server_tool_use = False
    found_web_search_result = False
    server_tool_use_index = -1
    web_search_result_index = -1

    for message in messages:
        if message["role"] == "assistant":
            for j, content_block in enumerate(message["content"]):
                if isinstance(content_block, dict):
                    if (
                        content_block.get("type") == "server_tool_use"
                        and content_block.get("name") == "web_search"
                        and content_block.get("id") == "srvtoolu_web_search_123"
                    ):
                        found_server_tool_use = True
                        server_tool_use_index = j
                elif isinstance(content_block, WebSearchToolResultBlock):
                    if content_block.tool_use_id == "srvtoolu_web_search_123":
                        found_web_search_result = True
                        web_search_result_index = j

    assert found_server_tool_use, (
        "ServerToolUseBlock should be included in reconstructed history"
    )
    assert found_web_search_result, (
        "WebSearchToolResultBlock should be included in reconstructed history"
    )
    assert server_tool_use_index < web_search_result_index, (
        "ServerToolUseBlock must precede WebSearchToolResultBlock "
        "(got server_tool_use at index {server_tool_use_index}, "
        "web_search_result at index {web_search_result_index})"
    )
