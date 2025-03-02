"""Tests for the Anthropic integration."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from anthropic import RateLimitError
from anthropic.types import (
    InputJSONDelta,
    Message,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageStartEvent,
    RawMessageStopEvent,
    RawMessageStreamEvent,
    TextBlock,
    TextDelta,
    ToolUseBlock,
    Usage,
)
from freezegun import freeze_time
from httpx import URL, Request, Response
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent, llm
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
    content_blocks: list[RawMessageStreamEvent],
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


async def test_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test entity properties."""
    state = hass.states.get("conversation.claude")
    assert state
    assert state.attributes["supported_features"] == 0

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_LLM_HASS_API: "assist",
        },
    )
    with patch("anthropic.resources.models.AsyncModels.retrieve"):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)

    state = hass.states.get("conversation.claude")
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
            hass, "hello", None, Context(), agent_id="conversation.claude"
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_template_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that template error handling works."""
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
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
            hass, "hello", None, Context(), agent_id="conversation.claude"
        )

    assert result.response.response_type == intent.IntentResponseType.ERROR, result
    assert result.response.error_code == "unknown", result


async def test_template_variables(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that template variables work."""
    context = Context(user_id="12345")
    mock_user = Mock()
    mock_user.id = "12345"
    mock_user.name = "Test User"

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
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
            hass, "hello", None, context, agent_id="conversation.claude"
        )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE, (
        result
    )
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
    agent = conversation.agent_manager.async_get_agent(hass, "conversation.claude")
    assert agent.supported_languages == "*"


@patch("homeassistant.components.anthropic.conversation.llm.AssistAPI._async_get_tools")
async def test_function_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test function call from the assistant."""
    agent_id = "conversation.claude"
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
                        ['{"para', 'm1": "test_valu', 'e"}'],
                    ),
                ]
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
            tool_args={"param1": "test_value"},
        ),
        llm.LLMContext(
            platform="anthropic",
            context=context,
            user_prompt="Please call the test function",
            language="en",
            assistant="conversation",
            device_id=None,
        ),
    )


@patch("homeassistant.components.anthropic.conversation.llm.AssistAPI._async_get_tools")
async def test_function_exception(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test function call with exception."""
    agent_id = "conversation.claude"
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
                    *create_content_block(0, "Certainly, calling it now!"),
                    *create_tool_use_block(
                        1,
                        "toolu_0123456789AbCdEfGhIjKlM",
                        "test_tool",
                        ['{"param1": "test_value"}'],
                    ),
                ]
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
            user_prompt="Please call the test function",
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

    agent_id = "conversation.claude"
    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        return_value=stream_generator(
            create_messages(
                create_content_block(0, "Hello, how can I help you?"),
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
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_LLM_HASS_API: "non-existing",
        },
    )
    await hass.async_block_till_done()

    result = await conversation.async_converse(
        hass, "hello", "1234", Context(), agent_id="conversation.claude"
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
                create_content_block(0, "Hello, how can I help you?"),
            ),
        )

    with patch(
        "anthropic.resources.messages.AsyncMessages.create",
        new_callable=AsyncMock,
        side_effect=create_stream_generator,
    ):
        result = await conversation.async_converse(
            hass, "hello", "1234", Context(), agent_id="conversation.claude"
        )

        result = await conversation.async_converse(
            hass, "hello", None, None, agent_id="conversation.claude"
        )

        conversation_id = result.conversation_id

        result = await conversation.async_converse(
            hass, "hello", conversation_id, None, agent_id="conversation.claude"
        )

        assert result.conversation_id == conversation_id

        unknown_id = ulid_util.ulid()

        result = await conversation.async_converse(
            hass, "hello", unknown_id, None, agent_id="conversation.claude"
        )

        assert result.conversation_id != unknown_id

        result = await conversation.async_converse(
            hass, "hello", "koala", None, agent_id="conversation.claude"
        )

        assert result.conversation_id == "koala"
