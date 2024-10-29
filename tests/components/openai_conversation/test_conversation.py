"""Tests for the OpenAI integration."""

from unittest.mock import AsyncMock, Mock, patch

from freezegun import freeze_time
from httpx import Response
from openai import RateLimitError
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_tool_call import (
    ChatCompletionMessageToolCall,
    Function,
)
from openai.types.completion_usage import CompletionUsage
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
    state = hass.states.get("conversation.openai")
    assert state
    assert state.attributes["supported_features"] == 0

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={
            **mock_config_entry.options,
            CONF_LLM_HASS_API: "assist",
        },
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)

    state = hass.states.get("conversation.openai")
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
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        side_effect=RateLimitError(
            response=Response(status_code=None, request=""), body=None, message=None
        ),
    ):
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
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
        patch(
            "openai.resources.models.AsyncModels.list",
        ),
        patch(
            "openai.resources.chat.completions.AsyncCompletions.create",
            new_callable=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
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
            "openai.resources.models.AsyncModels.list",
        ),
        patch(
            "openai.resources.chat.completions.AsyncCompletions.create",
            new_callable=AsyncMock,
        ) as mock_create,
        patch("homeassistant.auth.AuthManager.async_get_user", return_value=mock_user),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        result = await conversation.async_converse(
            hass, "hello", None, context, agent_id=mock_config_entry.entry_id
        )

    assert (
        result.response.response_type == intent.IntentResponseType.ACTION_DONE
    ), result
    assert (
        "The user name is Test User."
        in mock_create.mock_calls[0][2]["messages"][0]["content"]
    )
    assert (
        "The user id is 12345."
        in mock_create.mock_calls[0][2]["messages"][0]["content"]
    )


async def test_conversation_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test OpenAIAgent."""
    agent = conversation.get_agent_manager(hass).async_get_agent(
        mock_config_entry.entry_id
    )
    assert agent.supported_languages == "*"


@patch(
    "homeassistant.components.openai_conversation.conversation.llm.AssistAPI._async_get_tools"
)
async def test_function_call(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test function call from the assistant."""
    agent_id = mock_config_entry_with_assist.entry_id
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
            role = message["role"] if isinstance(message, dict) else message.role
            if role == "tool":
                return ChatCompletion(
                    id="chatcmpl-1234567890ZYXWVUTSRQPONMLKJIH",
                    choices=[
                        Choice(
                            finish_reason="stop",
                            index=0,
                            message=ChatCompletionMessage(
                                content="I have successfully called the function",
                                role="assistant",
                                function_call=None,
                                tool_calls=None,
                            ),
                        )
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion",
                    system_fingerprint=None,
                    usage=CompletionUsage(
                        completion_tokens=9, prompt_tokens=8, total_tokens=17
                    ),
                )

        return ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="tool_calls",
                    index=0,
                    message=ChatCompletionMessage(
                        content=None,
                        role="assistant",
                        function_call=None,
                        tool_calls=[
                            ChatCompletionMessageToolCall(
                                id="call_AbCdEfGhIjKlMnOpQrStUvWx",
                                function=Function(
                                    arguments='{"param1":"test_value"}',
                                    name="test_tool",
                                ),
                                type="function",
                            )
                        ],
                    ),
                )
            ],
            created=1700000000,
            model="gpt-4-1106-preview",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        )

    with (
        patch(
            "openai.resources.chat.completions.AsyncCompletions.create",
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

    assert (
        "Today's date is 2024-06-03."
        in mock_create.mock_calls[1][2]["messages"][0]["content"]
    )

    assert result.response.response_type == intent.IntentResponseType.ACTION_DONE
    assert mock_create.mock_calls[1][2]["messages"][3] == {
        "role": "tool",
        "tool_call_id": "call_AbCdEfGhIjKlMnOpQrStUvWx",
        "content": '"Test response"',
    }
    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            tool_name="test_tool",
            tool_args={"param1": "test_value"},
        ),
        llm.LLMContext(
            platform="openai_conversation",
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
    assert "Answer in plain text" in detail_event["data"]["messages"][0]["content"]
    assert (
        "Today's date is 2024-06-03."
        in trace_events[1]["data"]["messages"][0]["content"]
    )
    assert [t.name for t in detail_event["data"]["tools"]] == ["test_tool"]

    # Call it again, make sure we have updated prompt
    with (
        patch(
            "openai.resources.chat.completions.AsyncCompletions.create",
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

    assert (
        "Today's date is 2024-06-04."
        in mock_create.mock_calls[1][2]["messages"][0]["content"]
    )
    # Test old assert message not updated
    assert (
        "Today's date is 2024-06-03."
        in trace_events[1]["data"]["messages"][0]["content"]
    )


@patch(
    "homeassistant.components.openai_conversation.conversation.llm.AssistAPI._async_get_tools"
)
async def test_function_exception(
    mock_get_tools,
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test function call with exception."""
    agent_id = mock_config_entry_with_assist.entry_id
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
            role = message["role"] if isinstance(message, dict) else message.role
            if role == "tool":
                return ChatCompletion(
                    id="chatcmpl-1234567890ZYXWVUTSRQPONMLKJIH",
                    choices=[
                        Choice(
                            finish_reason="stop",
                            index=0,
                            message=ChatCompletionMessage(
                                content="There was an error calling the function",
                                role="assistant",
                                function_call=None,
                                tool_calls=None,
                            ),
                        )
                    ],
                    created=1700000000,
                    model="gpt-4-1106-preview",
                    object="chat.completion",
                    system_fingerprint=None,
                    usage=CompletionUsage(
                        completion_tokens=9, prompt_tokens=8, total_tokens=17
                    ),
                )

        return ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="tool_calls",
                    index=0,
                    message=ChatCompletionMessage(
                        content=None,
                        role="assistant",
                        function_call=None,
                        tool_calls=[
                            ChatCompletionMessageToolCall(
                                id="call_AbCdEfGhIjKlMnOpQrStUvWx",
                                function=Function(
                                    arguments='{"param1":"test_value"}',
                                    name="test_tool",
                                ),
                                type="function",
                            )
                        ],
                    ),
                )
            ],
            created=1700000000,
            model="gpt-4-1106-preview",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
            ),
        )

    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
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
    assert mock_create.mock_calls[1][2]["messages"][3] == {
        "role": "tool",
        "tool_call_id": "call_AbCdEfGhIjKlMnOpQrStUvWx",
        "content": '{"error": "HomeAssistantError", "error_text": "Test tool exception"}',
    }
    mock_tool.async_call.assert_awaited_once_with(
        hass,
        llm.ToolInput(
            tool_name="test_tool",
            tool_args={"param1": "test_value"},
        ),
        llm.LLMContext(
            platform="openai_conversation",
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

    agent_id = mock_config_entry_with_assist.entry_id
    with patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=AsyncMock,
        return_value=ChatCompletion(
            id="chatcmpl-1234567890ABCDEFGHIJKLMNOPQRS",
            choices=[
                Choice(
                    finish_reason="stop",
                    index=0,
                    message=ChatCompletionMessage(
                        content="Hello, how can I help you?",
                        role="assistant",
                        function_call=None,
                        tool_calls=None,
                    ),
                )
            ],
            created=1700000000,
            model="gpt-3.5-turbo-0613",
            object="chat.completion",
            system_fingerprint=None,
            usage=CompletionUsage(
                completion_tokens=9, prompt_tokens=8, total_tokens=17
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
        hass, "hello", None, Context(), agent_id=mock_config_entry.entry_id
    )

    assert result == snapshot


@patch(
    "openai.resources.chat.completions.AsyncCompletions.create",
    new_callable=AsyncMock,
)
async def test_conversation_id(
    mock_create,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component,
) -> None:
    """Test conversation ID is honored."""
    result = await conversation.async_converse(
        hass, "hello", None, None, agent_id=mock_config_entry.entry_id
    )

    conversation_id = result.conversation_id

    result = await conversation.async_converse(
        hass, "hello", conversation_id, None, agent_id=mock_config_entry.entry_id
    )

    assert result.conversation_id == conversation_id

    unknown_id = ulid.ulid()

    result = await conversation.async_converse(
        hass, "hello", unknown_id, None, agent_id=mock_config_entry.entry_id
    )

    assert result.conversation_id != unknown_id

    result = await conversation.async_converse(
        hass, "hello", "koala", None, agent_id=mock_config_entry.entry_id
    )

    assert result.conversation_id == "koala"
