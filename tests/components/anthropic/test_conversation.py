"""Tests for the Anthropic integration."""

from unittest.mock import AsyncMock, Mock, patch

from anthropic import RateLimitError
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage
from freezegun import freeze_time
from httpx import URL, Request, Response
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.conversation import trace
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent, llm
from homeassistant.setup import async_setup_component
from homeassistant.util import ulid

from tests.common import MockConfigEntry


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
    with patch(
        "anthropic.resources.messages.AsyncMessages.create", new_callable=AsyncMock
    ):
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
    with patch(
        "anthropic.resources.messages.AsyncMessages.create", new_callable=AsyncMock
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
        patch(
            "anthropic.resources.messages.AsyncMessages.create", new_callable=AsyncMock
        ) as mock_create,
        patch("homeassistant.auth.AuthManager.async_get_user", return_value=mock_user),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, context, agent_id="conversation.claude"
        )

    assert (
        result.response.response_type == intent.IntentResponseType.ACTION_DONE
    ), result
    assert "The user name is Test User." in mock_create.mock_calls[1][2]["system"]
    assert "The user id is 12345." in mock_create.mock_calls[1][2]["system"]


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
                    return Message(
                        type="message",
                        id="msg_1234567890ABCDEFGHIJKLMN",
                        content=[
                            TextBlock(
                                type="text",
                                text="I have successfully called the function",
                            )
                        ],
                        model="claude-3-5-sonnet-20240620",
                        role="assistant",
                        stop_reason="end_turn",
                        stop_sequence=None,
                        usage=Usage(input_tokens=8, output_tokens=12),
                    )

        return Message(
            type="message",
            id="msg_1234567890ABCDEFGHIJKLMN",
            content=[
                TextBlock(type="text", text="Certainly, calling it now!"),
                ToolUseBlock(
                    type="tool_use",
                    id="toolu_0123456789AbCdEfGhIjKlM",
                    name="test_tool",
                    input={"param1": "test_value"},
                ),
            ],
            model="claude-3-5-sonnet-20240620",
            role="assistant",
            stop_reason="tool_use",
            stop_sequence=None,
            usage=Usage(input_tokens=8, output_tokens=12),
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

    # Test Conversation tracing
    traces = trace.async_get_traces()
    assert traces
    last_trace = traces[-1].as_dict()
    trace_events = last_trace.get("events", [])
    assert [event["event_type"] for event in trace_events] == [
        trace.ConversationTraceEventType.ASYNC_PROCESS,
        trace.ConversationTraceEventType.AGENT_DETAIL,
        trace.ConversationTraceEventType.TOOL_CALL,
    ]
    # AGENT_DETAIL event contains the raw prompt passed to the model
    detail_event = trace_events[1]
    assert "Answer in plain text" in detail_event["data"]["system"]
    assert "Today's date is 2024-06-03." in trace_events[1]["data"]["system"]

    # Call it again, make sure we have updated prompt
    with (
        patch(
            "anthropic.resources.messages.AsyncMessages.create",
            new_callable=AsyncMock,
            side_effect=completion_result,
        ) as mock_create,
        freeze_time("2024-06-04 23:00:00"),
    ):
        result = await conversation.async_converse(
            hass,
            "Please call the test function",
            None,
            context,
            agent_id=agent_id,
        )

    assert "Today's date is 2024-06-04." in mock_create.mock_calls[1][2]["system"]
    # Test old assert message not updated
    assert "Today's date is 2024-06-03." in trace_events[1]["data"]["system"]


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
                    return Message(
                        type="message",
                        id="msg_1234567890ABCDEFGHIJKLMN",
                        content=[
                            TextBlock(
                                type="text",
                                text="There was an error calling the function",
                            )
                        ],
                        model="claude-3-5-sonnet-20240620",
                        role="assistant",
                        stop_reason="end_turn",
                        stop_sequence=None,
                        usage=Usage(input_tokens=8, output_tokens=12),
                    )

        return Message(
            type="message",
            id="msg_1234567890ABCDEFGHIJKLMN",
            content=[
                TextBlock(type="text", text="Certainly, calling it now!"),
                ToolUseBlock(
                    type="tool_use",
                    id="toolu_0123456789AbCdEfGhIjKlM",
                    name="test_tool",
                    input={"param1": "test_value"},
                ),
            ],
            model="claude-3-5-sonnet-20240620",
            role="assistant",
            stop_reason="tool_use",
            stop_sequence=None,
            usage=Usage(input_tokens=8, output_tokens=12),
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
        return_value=Message(
            type="message",
            id="msg_1234567890ABCDEFGHIJKLMN",
            content=[TextBlock(type="text", text="Hello, how can I help you?")],
            model="claude-3-5-sonnet-20240620",
            role="assistant",
            stop_reason="end_turn",
            stop_sequence=None,
            usage=Usage(input_tokens=8, output_tokens=12),
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

    result = await conversation.async_converse(
        hass, "hello", None, Context(), agent_id="conversation.claude"
    )

    assert result == snapshot


@patch("anthropic.resources.messages.AsyncMessages.create", new_callable=AsyncMock)
async def test_conversation_id(
    mock_create,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test conversation ID is honored."""
    result = await conversation.async_converse(
        hass, "hello", None, None, agent_id="conversation.claude"
    )

    conversation_id = result.conversation_id

    result = await conversation.async_converse(
        hass, "hello", conversation_id, None, agent_id="conversation.claude"
    )

    assert result.conversation_id == conversation_id

    unknown_id = ulid.ulid()

    result = await conversation.async_converse(
        hass, "hello", unknown_id, None, agent_id="conversation.claude"
    )

    assert result.conversation_id != unknown_id

    result = await conversation.async_converse(
        hass, "hello", "koala", None, agent_id="conversation.claude"
    )

    assert result.conversation_id == "koala"
